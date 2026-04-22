import sys
import subprocess

# Check Python version
print(f"Python: {sys.version}")

# Check if requests is installed
try:
    import requests
    print(f"requests: {requests.__version__}")
except ImportError:
    print("requests NOT installed")

# List installed packages
result = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True)
print("Installed packages:")
print(result.stdout[:2000])
