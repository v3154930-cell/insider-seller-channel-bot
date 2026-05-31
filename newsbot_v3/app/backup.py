from datetime import datetime

def build_backup_manifest()->dict:
    return {"status":"dry_run","created_at":datetime.utcnow().isoformat(),"includes":["db","config","source_registry","digest_history","published_history","admin_actions"]}
