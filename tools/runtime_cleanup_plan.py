#!/usr/bin/env python3
import argparse, json, shutil
from datetime import datetime
from pathlib import Path
PROTECTED={' .env','.env','news_queue.db','PROJECT_PASSPORT.md','stable_publisher_v3.py','run_stable_publisher_v3.sh','run_channel_status_check.sh','collector_v2.py','scoring.py','publisher_v2.py'}
PATTERNS=['patch_*.py','*.bak*','*.before_*','*.before_cleaner','_legacy_*','_archive_*','audio_digest/*.mp3','audio_digest/*.wav','audio_digest/scripts/*.before_cleaner']

def main():
 p=argparse.ArgumentParser(); p.add_argument('--root',default='/opt/newsbot_v2'); p.add_argument('--apply-archive',action='store_true'); a=p.parse_args(); root=Path(a.root)
 c=[]
 for pat in PATTERNS:
  for x in root.glob(pat):
   if x.name not in PROTECTED: c.append(x)
 print(f'scan_root={root}\nmode={'apply_archive' if a.apply_archive else 'read_only'}\ncandidates={len(c)}')
 if not a.apply_archive: return 0
 arc=root/f"_archive_runtime_{datetime.now().strftime('%Y%m%d_%H%M%S')}"; arc.mkdir(exist_ok=True)
 manifest=[str(x.relative_to(root)) for x in c]
 (arc/'archive_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 (arc/'archive_manifest.md').write_text('\n'.join(['- '+m for m in manifest]),encoding='utf-8')
 for x in c: 
  t=arc/x.relative_to(root); t.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(x),str(t))
 return 0
if __name__=='__main__': raise SystemExit(main())
