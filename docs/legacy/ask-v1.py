#!/usr/bin/env python3
# Original ~/bin/ask script — v1 (single-file, no streaming)
# API key removed — set ASK_ZAI_API_KEY env var or pass directly
import os
import sys

from anthropic import Anthropic

client = Anthropic(
    api_key=os.environ.get("ASK_ZAI_API_KEY", ""),
    base_url="https://api.z.ai/api/anthropic",
)

# Check if input is piped
if not sys.stdin.isatty():
    piped_input = sys.stdin.read().strip()
    query = " ".join(sys.argv[1:]) + "\n\n" + piped_input
else:
    query = " ".join(sys.argv[1:])

if not query.strip():
    print("Usage: ask <your question>")
    print("   or: command | ask <context>")
    sys.exit(1)

message = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=1024,
    messages=[{"role": "user", "content": query}],
)

print(message.content[0].text)
