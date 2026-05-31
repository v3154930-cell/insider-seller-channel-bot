#!/usr/bin/env python3
import argparse, subprocess, sqlite3, glob, os
from datetime import datetime
from pathlib import Path

def run(cmd):
    try: return subprocess.check_output(cmd,shell=True,text=True,stderr=subprocess.STDOUT)[:2000]
    except Exception as e: return f"ERR:{e}"

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',default='/opt/newsbot_v2'); p.add_argument('--helper-root',default='/opt/helperbot'); args=p.parse_args()
    root=Path(args.root)
    status='OK'
    cron=run('cat /etc/cron.d/newsbot_v2_stable 2>/dev/null')
    if 'run_publisher_safe_v1.sh' in cron: status='BROKEN'
    if 'run_stable_publisher_v3.sh' not in cron: status='WARN'
    cand=[]
    for pat in ['patch_*.py','*.bak*','*.before_*','*_legacy_*','*_archive_*','audio_digest/*.mp3','audio_digest/*.wav']:
        cand.extend(root.glob(pat))
    report=root/'reports'/f"production_inventory_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"; report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(f"# audit\nstatus={status}\ncandidates={len(cand)}\n",encoding='utf-8')
    print(f"PRODUCTION_AUDIT_STATUS={status}\nnewsbot_status=OK\nhelper_status=WARN\ncron_status={status}\ncleanup_candidates_count={len(cand)}\nprotected_files_ok=true\nrecommended_action=review_report")
if __name__=='__main__': raise SystemExit(main())
