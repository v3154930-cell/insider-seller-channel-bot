import sys
sys.path.insert(0, ".")
try:
    import formatters
    print("SUCCESS: formatters loaded")
    funcs = [x for x in dir(formatters) if not x.startswith('_')]
    print("Functions:", funcs)
    if 'get_source_link' in funcs:
        print("FOUND: get_source_link")
    else:
        print("NOT FOUND: get_source_link")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()