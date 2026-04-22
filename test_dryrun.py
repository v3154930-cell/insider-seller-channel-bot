import sys
import os
sys.path.insert(0, os.getcwd())

rss_items = [{'title': 'test', 'link': 'http://x.com'}]
from exa_digest_adapter import get_digest_preview
result = get_digest_preview(rss_items, with_exa=False)

output_file = os.path.join(os.getcwd(), 'dryrun_test.txt')
print(f"Writing to: {output_file}")
with open(output_file, 'w', encoding='utf-8') as f:
    f.write("Result type: ")
    f.write(str(type(result)))
    f.write("\n")
    f.write("Content: ")
    f.write(str(result))
print("Done")
