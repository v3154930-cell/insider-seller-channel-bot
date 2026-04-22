import os
print("CWD:", os.getcwd())
output = os.path.join(os.getcwd(), "verify_test.txt")
with open(output, "w") as f:
    f.write("Verification successful")
print("Done - file should exist")
