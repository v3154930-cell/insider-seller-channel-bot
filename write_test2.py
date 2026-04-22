import sys
print("Python started", flush=True)
try:
    open('hello2.txt','w').write('hello world\n')
    print("File written", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
    import traceback
    traceback.print_exc()
