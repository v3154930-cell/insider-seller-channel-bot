import os
cwd = os.getcwd()
print("Current working directory:", cwd)
files = os.listdir(cwd)
print("Files in CWD:", files)
with open("verify_test.txt", "w") as f:
    f.write("Verification successful")
print("Done")
