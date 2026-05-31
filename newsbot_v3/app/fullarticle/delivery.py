def choose_target(callback:dict,stored_message_target:str|None=None)->tuple[str|None,list[str]]:
    c=[callback.get("chat_id"),callback.get("message_target"),stored_message_target,callback.get("fallback_target")]
    cands=[x for x in c if x]
    return (cands[0] if cands else None), cands
