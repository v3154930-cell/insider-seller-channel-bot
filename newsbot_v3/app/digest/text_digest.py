def dry_run_text_digest(mode:str="morning",items:list|None=None)->dict:
    items=items or []
    return {"digest_mode":mode,"items":len(items),"post_preview":"dry-run digest","send_status":"dry_run"}
