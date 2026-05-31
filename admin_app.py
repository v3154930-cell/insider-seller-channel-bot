import os
import shutil
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime, date, timedelta

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from db import init_db, _fetch_all
import sqlite3

BASE_DIR = Path("/opt/newsbot_v2")
INBOX_DIR = BASE_DIR / "rules_docs" / "inbox"
LOG_DIR = BASE_DIR / "logs"

ALLOWED_MARKETPLACES = {
    "ozon": "Ozon",
    "wildberries": "Wildberries",
    "yandex_market": "Яндекс Маркет",
    "unknown": "Не определено",
}

ALLOWED_EXTENSIONS = {".xlsx", ".csv", ".pdf", ".txt"}

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
ADMIN_PORT = int(os.getenv("ADMIN_PORT") or "8088")

app = FastAPI(title="Newsbot Admin")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_token(request: Request):
    token = request.query_params.get("token") or ""
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")


def shell_run(cmd, timeout=300):
    result = subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    return result.stdout


def shell_start_background(cmd, log_file):
    log_path = LOG_DIR / log_file
    full_cmd = f"cd {BASE_DIR} && nohup {cmd} >> {log_path} 2>&1 & echo $!"
    result = subprocess.run(
        full_cmd,
        cwd=str(BASE_DIR),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=10,
    )
    return result.stdout.strip(), str(log_path)


def ensure_dirs():
    for key in ALLOWED_MARKETPLACES:
        (INBOX_DIR / key).mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)



def mask_secret(value):
    if not value:
        return "нет"
    if len(value) <= 8:
        return "задан"
    return value[:4] + "..." + value[-4:]


def key_expiry_info(prefix):
    key_name = f"{prefix}_API_KEY"
    if prefix == "OZON":
        exists = bool(os.getenv("OZON_API_KEY")) and bool(os.getenv("OZON_CLIENT_ID"))
    else:
        exists = bool(os.getenv(key_name))

    issued_raw = os.getenv(f"{prefix}_API_KEY_ISSUED_AT", "")
    valid_days_raw = os.getenv(f"{prefix}_API_KEY_VALID_DAYS", "")

    result = {
        "exists": exists,
        "issued_at": issued_raw or "не указано",
        "valid_days": valid_days_raw or "не указано",
        "expires_at": "не указано",
        "days_left": "не указано",
        "status": "ключ не задан",
    }

    if not exists:
        return result

    result["status"] = "ключ задан"

    try:
        issued = datetime.strptime(issued_raw, "%Y-%m-%d").date()
        valid_days = int(valid_days_raw)
        expires = issued + timedelta(days=valid_days)
        days_left = (expires - date.today()).days

        result["expires_at"] = expires.isoformat()
        result["days_left"] = str(days_left)

        if days_left < 0:
            result["status"] = "истёк"
        elif days_left <= 14:
            result["status"] = "скоро истечёт"
        else:
            result["status"] = "активен"

    except (TypeError, ValueError):
        pass

    return result


def api_keys_status():
    return {
        "wb": key_expiry_info("WB"),
        "ozon": key_expiry_info("OZON"),
        "yandex": {
            "exists": bool(os.getenv("YANDEX_MARKET_TOKEN")),
            "issued_at": "не указано",
            "valid_days": "не указано",
            "expires_at": "не указано",
            "days_left": "не указано",
            "status": "ключ задан" if os.getenv("YANDEX_MARKET_TOKEN") else "ключ не задан",
        }
    }


def update_env_values(values):
    env_path = BASE_DIR / ".env"
    lines = env_path.read_text().splitlines()

    keys = set(values.keys())
    out = []

    for line in lines:
        if "=" in line:
            name = line.split("=", 1)[0]
            if name in keys:
                continue
        out.append(line)

    for key, value in values.items():
        if value is not None and str(value).strip() != "":
            out.append(f"{key}={str(value).strip()}")

    env_path.write_text("\n".join(out) + "\n")

def get_counts():
    init_db()

    result = {
        "rules_documents": 0,
        "rules_signals": 0,
        "rules_checks": 0,
        "confirmed_by_docs": 0,
        "signal_only": 0,
    }

    queries = {
        "rules_documents": "SELECT COUNT(*) FROM rules_documents",
        "rules_signals": "SELECT COUNT(*) FROM rules_signals",
        "rules_checks": "SELECT COUNT(*) FROM rules_checks",
        "confirmed_by_docs": "SELECT COUNT(*) FROM rules_checks WHERE confirmation_level='confirmed_by_docs'",
        "signal_only": "SELECT COUNT(*) FROM rules_checks WHERE confirmation_level='signal_only'",
    }

    for key, query in queries.items():
        try:
            rows = _fetch_all(query)
            result[key] = rows[0][0]
        except Exception:
            result[key] = 0

    return result



def _admin_table_exists(cur, table_name):
    row = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _admin_h(value):
    value = "" if value is None else str(value)
    return (
        value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def get_official_sources_freshness():
    """
    Административный индикатор свежести официальных источников.

    Важно:
    - WB и Яндекс могут обновляться через API/официальные страницы.
    - Ozon требует ручной загрузки официальных Excel/PDF.
    - Ozon Select не должен считаться боевым источником комиссий.
    """
    news_db = BASE_DIR / "news_queue.db"
    tariff_db = BASE_DIR / "data" / "unified_tariffs.db"

    result = {
        "ozon_status": "red",
        "ozon_status_label": "нужна проверка",
        "ozon_source_file": "не найден",
        "ozon_source_status": "не указан",
        "ozon_source_role": "не указан",
        "ozon_valid_from": "",
        "ozon_rows": 0,
        "ozon_created_at": "",
        "ozon_age_days": "",
        "ozon_signals_after_source": 0,
        "ozon_select_status": "не найден",
        "official_today_rows": 0,
        "official_today_docs": [],
    }

    try:
        conn = sqlite3.connect(tariff_db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if _admin_table_exists(cur, "tariff_source_quality"):
            row = cur.execute("""
                SELECT source_file, source_status, source_role, created_at
                FROM tariff_source_quality
                WHERE marketplace = 'ozon'
                  AND source_role = 'standard_marketplace_service_rate'
                ORDER BY created_at DESC
                LIMIT 1
            """).fetchone()

            if row:
                result["ozon_source_file"] = row["source_file"] or "не найден"
                result["ozon_source_status"] = row["source_status"] or "не указан"
                result["ozon_source_role"] = row["source_role"] or "не указан"
                result["ozon_created_at"] = row["created_at"] or ""

            select_row = cur.execute("""
                SELECT source_status
                FROM tariff_source_quality
                WHERE marketplace = 'ozon'
                  AND (
                    lower(source_file) LIKE '%select%'
                    OR lower(source_note) LIKE '%select%'
                    OR lower(comment) LIKE '%select%'
                    OR source_file LIKE '%Селект%'
                    OR source_note LIKE '%Селект%'
                    OR comment LIKE '%Селект%'
                  )
                ORDER BY created_at DESC
                LIMIT 1
            """).fetchone()

            if select_row:
                result["ozon_select_status"] = select_row["source_status"] or "найден"

        if _admin_table_exists(cur, "clean_commissions"):
            row = cur.execute("""
                SELECT COUNT(*) AS rows_count, MAX(valid_from) AS valid_from
                FROM clean_commissions
                WHERE marketplace = 'ozon'
                  AND fee_type = 'marketplace_service_rate'
            """).fetchone()

            if row:
                result["ozon_rows"] = int(row["rows_count"] or 0)
                result["ozon_valid_from"] = row["valid_from"] or ""

        conn.close()

    except Exception as e:
        result["ozon_status"] = "red"
        result["ozon_status_label"] = f"ошибка чтения тарифной базы: {e}"
        return result

    if result["ozon_valid_from"]:
        try:
            valid_dt = datetime.strptime(result["ozon_valid_from"], "%Y-%m-%d")
            result["ozon_age_days"] = (datetime.now() - valid_dt).days
        except Exception:
            result["ozon_age_days"] = ""

    since = (
        (result["ozon_created_at"] or "")[:10]
        or result["ozon_valid_from"]
        or ""
    )

    try:
        conn = sqlite3.connect(news_db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if since and _admin_table_exists(cur, "tariff_signals"):
            row = cur.execute("""
                SELECT COUNT(*)
                FROM tariff_signals
                WHERE marketplace = 'ozon'
                  AND substr(detected_at, 1, 10) > ?
                  AND signal_level IN ('high', 'medium')
                  AND signal_type IN (
                    'tariff',
                    'logistics',
                    'returns',
                    'offer',
                    'payouts',
                    'penalties',
                    'api'
                  )
            """, (since,)).fetchone()

            result["ozon_signals_after_source"] = int(row[0] or 0) if row else 0

        today = datetime.now().strftime("%Y-%m-%d")

        if _admin_table_exists(cur, "rules_documents"):
            row = cur.execute("""
                SELECT COUNT(*)
                FROM rules_documents
                WHERE substr(loaded_at, 1, 10) = ?
            """, (today,)).fetchone()

            result["official_today_rows"] = int(row[0] or 0) if row else 0

            rows = cur.execute("""
                SELECT marketplace, document_name, COUNT(*) AS rows_loaded
                FROM rules_documents
                WHERE substr(loaded_at, 1, 10) = ?
                GROUP BY marketplace, document_name
                ORDER BY rows_loaded DESC
                LIMIT 6
            """, (today,)).fetchall()

            result["official_today_docs"] = [dict(r) for r in rows]

        conn.close()

    except Exception:
        pass

    if result["ozon_rows"] <= 0 or result["ozon_source_file"] == "не найден":
        result["ozon_status"] = "red"
        result["ozon_status_label"] = "нужна ручная загрузка Ozon"
    elif result["ozon_source_status"] != "usable":
        result["ozon_status"] = "red"
        result["ozon_status_label"] = "боевой Ozon-источник не usable"
    elif result["ozon_signals_after_source"] > 0:
        result["ozon_status"] = "yellow"
        result["ozon_status_label"] = "есть Ozon-сигналы после загрузки"
    elif isinstance(result["ozon_age_days"], int) and result["ozon_age_days"] > 30:
        result["ozon_status"] = "yellow"
        result["ozon_status_label"] = "проверь свежесть Ozon-файла"
    else:
        result["ozon_status"] = "green"
        result["ozon_status_label"] = "Ozon-источник свежий"

    return result


def render_official_sources_card():
    s = get_official_sources_freshness()

    status_styles = {
        "green": "background:#e7f8ee;color:#146c2e;border:1px solid #b7e3c4;",
        "yellow": "background:#fff7df;color:#8a5a00;border:1px solid #f0d58a;",
        "red": "background:#fdecec;color:#9f1d1d;border:1px solid #efb1b1;",
    }

    style = status_styles.get(s["ozon_status"], status_styles["red"])

    official_docs = ""
    if s["official_today_docs"]:
        rows = []
        for d in s["official_today_docs"]:
            rows.append(
                "<tr>"
                f"<td>{_admin_h(d.get('marketplace'))}</td>"
                f"<td>{_admin_h(d.get('document_name'))}</td>"
                f"<td>{_admin_h(d.get('rows_loaded'))}</td>"
                "</tr>"
            )

        official_docs = f"""
        <h3>Официальный слой сегодня</h3>
        <table>
          <tr><th>Маркетплейс</th><th>Документ</th><th>Строк</th></tr>
          {''.join(rows)}
        </table>
        """
    else:
        official_docs = """
        <h3>Официальный слой сегодня</h3>
        <p class="muted">Сегодня новых загрузок официальных документов и тарифных строк не обнаружено.</p>
        """

    return f"""
    <div class="card">
      <h2>Свежесть официальных источников</h2>
      <p style="margin-top:14px;">
        <a href="/ozon-diagnostics" onclick="this.href='/ozon-diagnostics'+window.location.search">
          Открыть подробную Ozon-диагностику: что проверить и какие файлы подгрузить
        </a>
      </p>


      <p>
        <span style="display:inline-block;padding:6px 10px;border-radius:999px;font-weight:700;{style}">
          Ozon: {_admin_h(s["ozon_status_label"])}
        </span>
      </p>

      <table>
        <tr><th>Показатель</th><th>Значение</th></tr>
        <tr><td>Боевой файл Ozon</td><td>{_admin_h(s["ozon_source_file"])}</td></tr>
        <tr><td>Статус источника</td><td>{_admin_h(s["ozon_source_status"])}</td></tr>
        <tr><td>Роль источника</td><td>{_admin_h(s["ozon_source_role"])}</td></tr>
        <tr><td>valid_from</td><td>{_admin_h(s["ozon_valid_from"] or "не указано")}</td></tr>
        <tr><td>Строк marketplace_service_rate</td><td>{_admin_h(s["ozon_rows"])}</td></tr>
        <tr><td>Возраст файла, дней</td><td>{_admin_h(s["ozon_age_days"] if s["ozon_age_days"] != "" else "не определён")}</td></tr>
        <tr><td>Ozon-сигналы после загрузки</td><td>{_admin_h(s["ozon_signals_after_source"])}</td></tr>
        <tr><td>Ozon Select</td><td>{_admin_h(s["ozon_select_status"])} · не использовать как боевой источник</td></tr>
      </table>

      <p class="muted">
        WB и Яндекс могут проверяться через API/официальные страницы. 
        Ozon требует ручной загрузки официального Excel/PDF, поэтому здесь отдельный административный светофор.
      </p>

      {official_docs}
    </div>
    """

def list_files():
    ensure_dirs()
    files = []

    for marketplace in ALLOWED_MARKETPLACES:
        folder = INBOX_DIR / marketplace
        for path in sorted(folder.glob("*")):
            if path.is_file():
                files.append({
                    "marketplace": marketplace,
                    "marketplace_label": ALLOWED_MARKETPLACES.get(marketplace, marketplace),
                    "name": path.name,
                    "size": path.stat().st_size,
                    "mtime": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                })

    return files


def last_rows(table, limit=10):
    try:
        if table == "rules_imported_files":
            return _fetch_all("""
                SELECT file_path, rows_imported, imported_at
                FROM rules_imported_files
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))

        if table == "rules_checks":
            return _fetch_all("""
                SELECT rc.confirmation_level, rc.match_score, rc.marketplace, rs.title
                FROM rules_checks rc
                LEFT JOIN rules_signals rs ON rs.id = rc.signal_id
                ORDER BY rc.id DESC
                LIMIT ?
            """, (limit,))

    except Exception:
        return []

    return []


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    require_token(request)
    ensure_dirs()

    counts = get_counts()
    api_status = api_keys_status()
    files = list_files()
    imports = last_rows("rules_imported_files", 10)
    checks = last_rows("rules_checks", 10)
    official_sources_card = render_official_sources_card()

    token = request.query_params.get("token")

    html = f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Newsbot Admin</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      background: #f6f7f9;
      color: #222;
      margin: 0;
      padding: 28px;
    }}
    .wrap {{
      max-width: 1180px;
      margin: 0 auto;
    }}
    h1 {{
      margin-top: 0;
      font-size: 28px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }}
    .card {{
      background: white;
      border-radius: 16px;
      padding: 20px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.06);
      margin-bottom: 18px;
    }}
    label {{
      display: block;
      margin: 12px 0 6px;
      font-weight: 600;
    }}
    input, select, button {{
      font-size: 15px;
      padding: 10px;
      border-radius: 10px;
      border: 1px solid #d0d5dd;
    }}
    button {{
      background: #111827;
      color: white;
      cursor: pointer;
      border: none;
      margin-top: 12px;
    }}
    button.secondary {{
      background: #374151;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid #eee;
      padding: 8px;
      text-align: left;
      vertical-align: top;
    }}
    .muted {{
      color: #666;
      font-size: 13px;
    }}
    .ok {{
      color: #067647;
      font-weight: 700;
    }}
    .warn {{
      color: #b54708;
      font-weight: 700;
    }}
    pre {{
      white-space: pre-wrap;
      background: #111827;
      color: #e5e7eb;
      padding: 14px;
      border-radius: 12px;
      max-height: 420px;
      overflow: auto;
    }}
  </style>
</head>
<body>
<div class="wrap">
  <h1>Newsbot Admin</h1>
  <p class="muted">Админка для загрузки документов маркетплейсов и запуска сверки сигналов.</p>

  <div class="grid">
    <div class="card">
      <h2>Загрузка документа</h2>
      <form action="/upload?token={token}" method="post" enctype="multipart/form-data">
        <label>Маркетплейс</label>
        <select name="marketplace">
          <option value="ozon">Ozon</option>
          <option value="wildberries">Wildberries</option>
          <option value="yandex_market">Яндекс Маркет</option>
          <option value="unknown">Не определено</option>
        </select>

        <label>Файл</label>
        <input type="file" name="file" required>

        <br>
        <button type="submit">Загрузить файл</button>
      </form>
      <p class="muted">Поддерживаются: .xlsx, .csv, .pdf, .txt</p>
    </div>

    <div class="card">
      <h2>Действия</h2>
      <form action="/run-import?token={token}" method="post">
        <button type="submit">Импортировать новые документы</button>
      </form>

      <form action="/run-check?token={token}" method="post">
        <button class="secondary" type="submit">Запустить сверку сигналов</button>
      </form>

      <form action="/run-full?token={token}" method="post">
        <button class="secondary" type="submit">Импорт + сверка + preview</button>
      </form>
    </div>
  </div>

  <div class="card">
    <h2>Статус базы</h2>
    <table>
      <tr><th>Показатель</th><th>Значение</th></tr>
      <tr><td>Документов в базе rules_documents</td><td>{counts["rules_documents"]}</td></tr>
      <tr><td>Сигналов rules_signals</td><td>{counts["rules_signals"]}</td></tr>
      <tr><td>Проверок rules_checks</td><td>{counts["rules_checks"]}</td></tr>
      <tr><td>Подтверждено документами</td><td class="ok">{counts["confirmed_by_docs"]}</td></tr>
      <tr><td>Только сигнал, без подтверждения</td><td class="warn">{counts["signal_only"]}</td></tr>
    </table>
  </div>

  {official_sources_card}

  <div class="card">
    <h2>API-ключи и сроки действия</h2>
    <table>
      <tr><th>Сервис</th><th>Статус</th><th>Дата выпуска</th><th>Действует дней</th><th>Истекает</th><th>Осталось дней</th></tr>
      <tr>
        <td>Wildberries</td>
        <td>{api_status["wb"]["status"]}</td>
        <td>{api_status["wb"]["issued_at"]}</td>
        <td>{api_status["wb"]["valid_days"]}</td>
        <td>{api_status["wb"]["expires_at"]}</td>
        <td>{api_status["wb"]["days_left"]}</td>
      </tr>
      <tr>
        <td>Ozon</td>
        <td>{api_status["ozon"]["status"]}</td>
        <td>{api_status["ozon"]["issued_at"]}</td>
        <td>{api_status["ozon"]["valid_days"]}</td>
        <td>{api_status["ozon"]["expires_at"]}</td>
        <td>{api_status["ozon"]["days_left"]}</td>
      </tr>
      <tr>
        <td>Яндекс Маркет</td>
        <td>{api_status["yandex"]["status"]}</td>
        <td>{api_status["yandex"]["issued_at"]}</td>
        <td>{api_status["yandex"]["valid_days"]}</td>
        <td>{api_status["yandex"]["expires_at"]}</td>
        <td>{api_status["yandex"]["days_left"]}</td>
      </tr>
    </table>

    <h3>Обновить ключ</h3>
    <form action="/update-api-key?token={token}" method="post">
      <label>Сервис</label>
      <select name="service">
        <option value="wb">Wildberries</option>
        <option value="ozon">Ozon</option>
        <option value="yandex">Яндекс Маркет</option>
      </select>

      <label>Новый API-ключ / токен</label>
      <input type="password" name="api_key" placeholder="Вставить новый ключ">

      <label>Ozon Client ID, только для Ozon</label>
      <input type="text" name="client_id" placeholder="Ozon Client ID, если обновляешь Ozon">

      <label>Дата выпуска ключа</label>
      <input type="date" name="issued_at" value="2026-04-21">

      <label>Срок действия, дней</label>
      <input type="number" name="valid_days" value="180">

      <br>
      <button type="submit">Обновить ключ</button>
    </form>
    <p class="muted">Ключи не отображаются в админке. Здесь показывается только статус и срок действия.</p>
  </div>

  <div class="card">
    <h2>Файлы в inbox</h2>
    <table>
      <tr><th>Маркетплейс</th><th>Файл</th><th>Размер</th><th>Дата</th></tr>
      {''.join(f"<tr><td>{x['marketplace_label']}</td><td>{x['name']}</td><td>{x['size']}</td><td>{x['mtime']}</td></tr>" for x in files)}
    </table>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Последние импорты</h2>
      <table>
        <tr><th>Файл</th><th>Строк</th><th>Дата</th></tr>
        {''.join(f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td></tr>" for r in imports)}
      </table>
    </div>

    <div class="card">
      <h2>Последние сверки</h2>
      <table>
        <tr><th>Статус</th><th>Score</th><th>Маркетплейс</th><th>Сигнал</th></tr>
        {''.join(f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{str(r[3])[:120]}</td></tr>" for r in checks)}
      </table>
    </div>
  </div>
</div>
</body>
</html>
"""
    return HTMLResponse(html)



def sha256_file(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def duplicate_exists(target_dir: Path, candidate_path: Path):
    candidate_hash = sha256_file(candidate_path)

    for existing in target_dir.glob("*"):
        if not existing.is_file():
            continue
        try:
            if sha256_file(existing) == candidate_hash:
                return True, existing.name
        except Exception:
            continue

    return False, None


@app.post("/upload")
async def upload(request: Request, marketplace: str = Form(...), file: UploadFile = File(...)):
    require_token(request)
    ensure_dirs()

    if marketplace not in ALLOWED_MARKETPLACES:
        raise HTTPException(status_code=400, detail="Unknown marketplace")

    original_name = Path(file.filename or "uploaded_file").name
    ext = Path(original_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension: {ext}")

    target_dir = INBOX_DIR / marketplace
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = original_name.replace("/", "_").replace("\\", "_")
    target_path = target_dir / f"{timestamp}_{safe_name}"
    tmp_path = target_dir / f".tmp_{timestamp}_{safe_name}"

    with tmp_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    is_duplicate, existing_name = duplicate_exists(target_dir, tmp_path)

    if is_duplicate:
        tmp_path.unlink(missing_ok=True)
    else:
        tmp_path.rename(target_path)

    token = request.query_params.get("token")
    return RedirectResponse(url=f"/?token={token}", status_code=303)



@app.post("/update-api-key")
async def update_api_key(
    request: Request,
    service: str = Form(...),
    api_key: str = Form(""),
    client_id: str = Form(""),
    issued_at: str = Form(""),
    valid_days: str = Form("180"),
):
    require_token(request)
    token = request.query_params.get("token")

    values = {}

    if service == "wb":
        values["WB_API_KEY"] = api_key
        values["WB_API_KEY_ISSUED_AT"] = issued_at
        values["WB_API_KEY_VALID_DAYS"] = valid_days

    elif service == "ozon":
        values["OZON_API_KEY"] = api_key
        if client_id.strip():
            values["OZON_CLIENT_ID"] = client_id
        values["OZON_API_KEY_ISSUED_AT"] = issued_at
        values["OZON_API_KEY_VALID_DAYS"] = valid_days

    elif service == "yandex":
        values["YANDEX_MARKET_TOKEN"] = api_key

    else:
        raise HTTPException(status_code=400, detail="Unknown service")

    update_env_values(values)

    return RedirectResponse(url=f"/?token={token}", status_code=303)


@app.post("/run-import", response_class=HTMLResponse)
async def run_import(request: Request):
    require_token(request)
    token = request.query_params.get("token")
    pid, log_path = shell_start_background(
        "/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/import_rules_docs_bulk_v2.py",
        "rules_import.log"
    )
    return HTMLResponse(f"""
        <h1>Импорт документов запущен в фоне</h1>
        <p>PID: <b>{pid}</b></p>
        <p>Лог: <code>{log_path}</code></p>
        <p>Проверь прогресс командой:</p>
        <pre>tail -f {log_path}</pre>
        <p><a href='/?token={token}'>Назад в админку</a></p>
    """)


@app.post("/run-check", response_class=HTMLResponse)
async def run_check(request: Request):
    require_token(request)
    token = request.query_params.get("token")
    output = shell_run("/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/rules_auto_check_v2.py")
    return HTMLResponse(f"<h1>Сверка сигналов</h1><pre>{output}</pre><p><a href='/?token={token}'>Назад</a></p>")


@app.post("/run-full", response_class=HTMLResponse)
async def run_full(request: Request):
    require_token(request)
    token = request.query_params.get("token")

    cmd = (
        "/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/import_rules_docs_bulk_v2.py && "
        "/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/rules_monitor_v2.py && "
        "/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/classify_rules_signals_v2.py && "
        "/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/rules_auto_check_v2.py && "
        "/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/rules_digest_preview_v2.py"
    )

    pid, log_path = shell_start_background(cmd, "rules_full_run.log")

    return HTMLResponse(f"""
        <h1>Полный прогон запущен в фоне</h1>
        <p>PID: <b>{pid}</b></p>
        <p>Лог: <code>{log_path}</code></p>
        <p>Проверь прогресс командой:</p>
        <pre>tail -f {log_path}</pre>
        <p><a href='/?token={token}'>Назад в админку</a></p>
    """)


@app.get("/ozon-diagnostics", response_class=HTMLResponse)
async def ozon_diagnostics_page(request: Request):
    require_token(request)
    token = request.query_params.get("token", "")

    import html as _html

    cmd = "/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/ozon_source_diagnostics.py"
    output = shell_run(cmd)

    return HTMLResponse(f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Ozon диагностика источников</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      background: #f6f7f9;
      padding: 24px;
      color: #111827;
    }}
    .card {{
      max-width: 1180px;
      margin: 0 auto;
      background: #fff;
      border-radius: 16px;
      padding: 24px;
      box-shadow: 0 4px 18px rgba(0,0,0,.06);
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: #111827;
      color: #e5e7eb;
      padding: 16px;
      border-radius: 12px;
      font-size: 13px;
      line-height: 1.45;
    }}
    a {{
      color: #2563eb;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Ozon: диагностика свежести источников</h1>
    <p><a href="/?token={_html.escape(token)}">← Назад в админку</a></p>
    <pre>{_html.escape(output)}</pre>
    <p><a href="/?token={_html.escape(token)}">← Назад в админку</a></p>
  </div>
</body>
</html>
    """)
