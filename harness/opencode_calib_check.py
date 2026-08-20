#!/usr/bin/env python3
"""
Helper for opencode_probe.sh. Parses an `opencode export <sessionID>` JSON dump and reports,
for the messages added since a given prior message count:
  - the concatenated assistant text (all "text" parts, in order)
  - how many tool-call parts appeared (type == "tool")
Usage: opencode_calib_check.py <export.json> <prev_message_count>
Prints two lines to stdout: TOOLCOUNT=<n> then the assistant text (may be empty/multi-line).

NOTE: schema verified empirically against the *error* path of `opencode export` (opencode
1.14.29) -- a real assistant turn's message/part shape (info.role, parts[].type) is expected to
follow the same "info"/"parts" structure but has not been observed against a live model response.
Spot-check this once the pod servers are up; adjust TEXT_TYPES/TOOL_TYPES below if the real shape
differs.
"""
import json
import sys

TEXT_TYPES = {"text"}
TOOL_TYPES = {"tool", "tool-call", "tool_use"}

path, prev_count = sys.argv[1], int(sys.argv[2])
with open(path, encoding="utf-8") as f:
    data = json.load(f)

messages = data.get("messages", [])
new = messages[prev_count:]

text_chunks = []
tool_count = 0
for m in new:
    info = m.get("info", {})
    if info.get("role") != "assistant":
        continue
    for part in m.get("parts", []):
        ptype = part.get("type")
        if ptype in TEXT_TYPES and part.get("text"):
            text_chunks.append(part["text"])
        elif ptype in TOOL_TYPES:
            tool_count += 1

print(f"TOOLCOUNT={tool_count}")
print(f"TOTALMESSAGES={len(messages)}")
print("\n".join(text_chunks))
