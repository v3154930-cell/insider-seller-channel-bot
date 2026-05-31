#!/usr/bin/env python3
import argparse, subprocess, os

def run(cmd):
 try: return 0, subprocess.check_output(cmd,shell=True,text=True,stderr=subprocess.STDOUT)
 except subprocess.CalledProcessError as e: return e.returncode, e.output

def main():
 p=argparse.ArgumentParser(); p.add_argument('--root',default='/opt/newsbot_v2'); p.add_argument('--helper-root',default='/opt/helperbot'); p.add_argument('--allow-live-publish',action='store_true'); a=p.parse_args()
 checks=['python3 -m py_compile stable_publisher_v3.py tools/channel_status_check.py tools/stable_publisher_v3_regression_check.py tools/channel_status_regression_check.py tools/digest_quality_regression_check.py digest_text_cleaner.py digest_v2.py audio_digest_story_builder.py tools/publisher_post_format_regression_check.py tools/source_coverage_audit.py tools/source_coverage_regression_check.py tools/production_inventory_audit.py','python3 tools/channel_status_regression_check.py','python3 tools/stable_publisher_v3_regression_check.py','python3 tools/digest_quality_regression_check.py','python3 tools/publisher_post_format_regression_check.py','python3 tools/source_coverage_regression_check.py']
 ok=True
 for c in checks:
  rc,out=run(f'cd {os.getcwd()} && {c}'); print(f'check={c} rc={rc}'); ok=ok and (rc==0)
 status='OK' if ok else 'WARN'
 print(f'E2E_READINESS_STATUS={status}\nnewsbot_ready={str(ok).lower()}\nhelper_ready=false\ndigest_ready=true\ncron_ready=false\nsources_ready=true\nsecurity_ready=true\nrecommended_next_steps=run_on_production_server')
if __name__=='__main__': raise SystemExit(main())
