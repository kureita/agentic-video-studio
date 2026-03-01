import re

def _repair_json(text: str) -> str:
    out = []
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '\\' and in_string:
            out.append(ch)
            if i + 1 < len(text):
                out.append(text[i + 1])
            i += 2
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
        elif in_string and ch == '\n':
            out.append('\\n')
        elif in_string and ch == '\r':
            out.append('\\r')
        elif in_string and ch == '\t':
            out.append('\\t')
        else:
            out.append(ch)
        i += 1
    text = ''.join(out)

    text = re.sub(r',\s*([\]}])', r'\1', text)
    
    in_str = False
    esc = False
    stack = []
    for char in text:
        if esc:
            esc = False
            continue
        if char == '\\':
            esc = True
            continue
        if char == '"':
            in_str = not in_str
        elif not in_str:
            if char == '{':
                stack.append('}')
            elif char == '[':
                stack.append(']')
            elif char == '}' and stack and stack[-1] == '}':
                stack.pop()
            elif char == ']' and stack and stack[-1] == ']':
                stack.pop()
                
    text = text.rstrip().rstrip(',')
    if in_str:
        text += '"'
    
    while stack:
        text += stack.pop()

    return text

import json

partial_json = """{
  "thinking": "testing",
  "tool_calls": [],
  "message": "msg",
  "nodes": [
    {
      "id": "vid_s3a",
      "type": "videoGen",
      "position": {"x": 1400, "y": 2400}"""

repaired = _repair_json(partial_json)
print(repaired)
try:
    json.loads(repaired)
    print("SUCCESS")
except Exception as e:
    print("FAILED", e)
