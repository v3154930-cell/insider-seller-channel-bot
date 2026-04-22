#!/usr/bin/env python
"""Simple test runner - runs tests and outputs results to file."""
import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

results = []

def run_test_class(module_name, class_name):
    module = __import__(module_name, fromlist=[class_name])
    cls = getattr(module, class_name)
    instance = cls()
    
    test_methods = [m for m in dir(instance) if m.startswith('test_')]
    
    for method_name in test_methods:
        method = getattr(instance, method_name)
        try:
            if hasattr(instance, '__dict__'):
                pass
            method()
            results.append(f"PASS: {class_name}.{method_name}")
        except Exception as e:
            results.append(f"FAIL: {class_name}.{method_name} - {type(e).__name__}: {str(e)[:100]}")
        except:
            results.append(f"ERROR: {class_name}.{method_name}")

print("Running tests...", flush=True)

print("test_filters.py...", flush=True)
run_test_class('tests.test_filters', 'TestFilters')
print("test_scoring.py...", flush=True)  
run_test_class('tests.test_scoring', 'TestScoring')
print("test_formatters.py...", flush=True)
run_test_class('tests.test_formatters', 'TestFormatters')
print("test_preview_gate.py...", flush=True)
run_test_class('tests.test_preview_gate', 'TestEvaluateItemRelevance')
run_test_class('tests.test_preview_gate', 'TestFailClosed')
print("test_preview_debug.py...", flush=True)
run_test_class('tests.test_preview_debug', 'TestPreviewDebugOutput')

with open('test_results.txt', 'w', encoding='utf-8') as f:
    f.write("=" * 60 + "\n")
    f.write("TEST RESULTS\n")
    f.write("=" * 60 + "\n\n")
    
    passed = sum(1 for r in results if r.startswith('PASS'))
    failed = sum(1 for r in results if r.startswith('FAIL'))
    error = sum(1 for r in results if r.startswith('ERROR'))
    
    for r in results:
        f.write(r + "\n")
    
    f.write("\n" + "=" * 60 + "\n")
    f.write(f"SUMMARY: {passed} passed, {failed} failed, {error} errors\n")
    f.write("=" * 60 + "\n")

print("Done! Results written to test_results.txt", flush=True)
