import sys
import os
print("Python started", flush=True)
try:
    path = os.path.join(os.getcwd(), 'hello3.txt')
    with open(path,'w') as f:
        f.write('hello world\n')
    print(f"File written to: {path}", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
    import traceback
    traceback.print_exc()
