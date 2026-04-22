cd "D:\LLM code\insider-seller-channel-bot"
$output = & py -3 run_collector_wrapper.py 2>&1
$output | Out-File -FilePath preview_check.txt -Encoding utf8