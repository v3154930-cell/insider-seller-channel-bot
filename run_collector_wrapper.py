import os
import sys

os.chdir(r"D:\LLM code\insider-seller-channel-bot")
sys.path.insert(0, r"D:\LLM code\insider-seller-channel-bot")

os.environ["STAGING_MODE"] = "true"
os.environ["STAGING_OUTPUT_DIR"] = "./outputs"
os.environ["STAGING_LINKS_FILE"] = "./links.txt"

from collector import run_collector
run_collector()