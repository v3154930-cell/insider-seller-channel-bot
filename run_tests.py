"""Simple test runner that outputs results to a file."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
import io

class OutputCapture:
    def __init__(self):
        self.output = io.StringIO()
        
    def write(self, text):
        self.output.write(text)
        
    def getvalue(self):
        return self.output.getvalue()

def run_tests():
    args = ['tests/', '-v', '--tb=short', '--no-header']
    
    capture = OutputCapture()
    old_stdout = sys.stdout
    sys.stdout = capture
    
    try:
        result = pytest.main(args)
    finally:
        sys.stdout = old_stdout
    
    output = capture.getvalue()
    
    with open('test_results.txt', 'w', encoding='utf-8') as f:
        f.write(output)
        f.write(f"\n\nExit code: {result}\n")
    
    return result

if __name__ == "__main__":
    run_tests()
