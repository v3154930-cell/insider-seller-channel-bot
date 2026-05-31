#!/usr/bin/env python3
from __future__ import annotations

import argparse

from app.db import dry_run_create_plan, get_v3_db_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default=str(get_v3_db_path()))
    args = parser.parse_args()

    plan = dry_run_create_plan(args.db_path)
    status = "OK" if plan["schema_sql_valid"] else "FAIL"

    print(f"V3_DB_SCHEMA_DRY_RUN_STATUS={status}")
    print("production_mutation=false")
    print(f"schema_tables={','.join(plan['schema_tables'])}")
    print(f"schema_table_count={plan['schema_table_count']}")
    print(f"schema_sql_valid={'true' if plan['schema_sql_valid'] else 'false'}")
    print(f"runtime_db_path={plan['runtime_db_path']}")
    print(f"would_create_db={'true' if plan['would_create_db'] else 'false'}")
    print("recommended_next_steps=dry-run first; backup before real migration; explicit operator command for real migration")
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
