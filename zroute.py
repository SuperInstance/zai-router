#!/usr/bin/env python3
"""zroute: ZAI fallback router. Reads the key from OpenClaw config locally
(never prints it), calls api.z.ai directly, falls back across GLM models
on 429/concurrency errors. Usage: zroute.py "prompt" """
import json, sys, urllib.request, re

CFG = "/home/eileen/.openclaw/openclaw.json"
BASE = "https://api.z.ai/api/coding/paas/v4"
# Priority: best first. Per-model concurrency — flash:1, 5.2:5, 4.5:10
MODELS = ["glm-5.3", "glm-5.2", "glm-4.7", "glm-4.6", "glm-4.5", "glm-4.7-flash"]
FAIL = re.compile(r"429|too many|concurrency|rate.?limit|quota|overloaded", re.I)

def get_key():
    """Key sources, in order (read at use-time; never stored, never printed):
    1. env ZAI_KEY
    2. ~/.config/zai/token  (Z.ai coding-plan token store)
    3. /mnt/c/Users/casey/key.txt  ZAI_KEY line (Casey's key file)
    NOTE: openclaw.json's zai:default profile is mode-based (no key) —
    that path 401s, which is the bug this fixes."""
    import os
    k = os.environ.get("ZAI_KEY", "").strip()
    if k:
        return k
    tok = os.path.expanduser("~/.config/zai/token")
    try:
        k = open(tok).read().strip()
        if len(k) > 20:
            return k
    except OSError:
        pass
    try:
        for line in open("/mnt/c/Users/casey/key.txt", errors="replace"):
            if "ZAI_KEY" in line and "=" in line:
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None

def call(model, prompt, key, timeout=180):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 2000}).encode()
    req = urllib.request.Request(BASE + "/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode())
            return j["choices"][0]["message"]["content"], None
    except Exception as e:
        return None, str(e)[-300:]

def main():
    if len(sys.argv) < 2:
        print("usage: zroute.py \"prompt\"", file=sys.stderr); sys.exit(2)
    prompt = sys.argv[1]
    models = sys.argv[2].split(",") if len(sys.argv) > 2 else MODELS
    key = get_key()
    if not key:
        print("[zroute] no ZAI key found", file=sys.stderr); sys.exit(3)
    for m in models:
        print(f"[zroute] trying {m}...", file=sys.stderr)
        resp, err = call(m, prompt, key)
        if resp:
            print(f"[zroute] served by {m}", file=sys.stderr)
            print(resp)
            return
        print(f"[zroute] {m} failed: {err}", file=sys.stderr)
    print("[zroute] all models exhausted", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
