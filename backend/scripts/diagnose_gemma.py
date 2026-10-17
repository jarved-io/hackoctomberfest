"""Standalone diagnostic: which Gemma models can this API key use, and which one answers?

Run from the project folder (it reads GEMINI_API_KEY from .env or the environment):
    python diagnose_gemma.py

Uses only the standard library. Prints Google's short error message (never your key).
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://generativelanguage.googleapis.com/v1beta"


def load_key():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key and os.path.exists(".env"):
        for line in open(".env", encoding="utf-8"):
            line = line.strip()
            if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return key


KEY = load_key()


def scrub(text):
    return str(text).replace(KEY, "***") if KEY else str(text)


def call(method, path, body=None):
    """Returns (status, parsed_json_or_None, short_message)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method,
        headers={"Content-Type": "application/json", "x-goog-api-key": KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw), ""
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        msg = raw[:200]
        try:
            err = json.loads(raw).get("error", {})
            msg = f"{err.get('status', '')}: {err.get('message', '')}"[:300]
        except ValueError:
            pass
        return exc.code, None, scrub(msg)
    except Exception as exc:  # network problems, timeouts
        return 0, None, scrub(f"{type(exc).__name__}: {exc}")[:200]


def reply_text(data):
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()[:80]
    except (KeyError, IndexError, TypeError):
        return f"(no text; finishReason={data.get('candidates', [{}])[0].get('finishReason') if data else '?'})"


def replay_module_request(model):
    """Send the module's real prompts, changing one setting at a time."""
    try:
        from ai_module.prompt import SYSTEM_PROMPT, build_user_prompt
    except Exception as exc:  # noqa: BLE001
        print(f"\n(Skipping replay: could not import ai_module: {type(exc).__name__}: {exc})")
        return
    findings = [
        {"line": 1, "api": "requests.get", "kind": "function", "status": "valid", "reason": "Found."},
        {"line": 1, "api": "requests.get", "kind": "argument", "argument": "timeout_seconds",
         "status": "invalid", "reason": "Not in trusted signature.", "closestValid": "timeout"},
    ]
    registry = {"requests.get": {"kind": "function", "arguments": ["url", "params", "headers", "timeout"]}}
    user = build_user_prompt('requests.get("https://example.com", timeout_seconds=10)', "requests", "2.31.0",
                             findings, registry, 20000)

    def body(system, text, config=None):
        b = {"system_instruction": {"parts": [{"text": system}]},
             "contents": [{"role": "user", "parts": [{"text": text}]}]}
        if config:
            b["generationConfig"] = config
        return b

    variants = [
        ("real prompts, no settings", body(SYSTEM_PROMPT, user)),
        ("real prompts + temperature 0", body(SYSTEM_PROMPT, user, {"temperature": 0.0})),
        ("real prompts + maxOutputTokens 1500", body(SYSTEM_PROMPT, user, {"maxOutputTokens": 1500})),
        ("real prompts + both (module's exact request)", body(SYSTEM_PROMPT, user, {"temperature": 0.0, "maxOutputTokens": 1500})),
        ("short prompt + both", body("You answer with one word.", "Reply with the single word: pong",
                                     {"temperature": 0.0, "maxOutputTokens": 1500})),
    ]
    print(f"\nReplaying the module's real request on {model} (prompt size: {len(SYSTEM_PROMPT) + len(user)} characters):")
    for label, b in variants:
        for attempt in (1, 2):
            status, data, msg = call("POST", f"/models/{model}:generateContent", b)
            result = reply_text(data) if status == 200 else msg
            print(f"  {label:<46} try {attempt}: HTTP {status}  {result}")


def main():
    if not KEY:
        print("No key found. Put GEMINI_API_KEY=... in .env or set it in the terminal.")
        return 1
    print(f"Key found (length {len(KEY)}). Asking Google which Gemma models are available...\n")

    names, token = [], ""
    for _ in range(5):
        status, data, msg = call("GET", f"/models?pageSize=200{'&pageToken=' + token if token else ''}")
        if status != 200:
            print(f"LIST MODELS FAILED: HTTP {status} {msg}")
            print("-> 400/403 usually means the key is wrong or not allowed; 0 means no internet/proxy.")
            return 1
        for m in data.get("models", []):
            if "gemma" in m.get("name", "").lower():
                names.append((m["name"].split("/", 1)[1], m.get("supportedGenerationMethods", [])))
        token = data.get("nextPageToken", "")
        if not token:
            break
    print("Key is accepted. Gemma models this key can see:")
    for name, methods in names:
        print(f"  {name}   methods={methods}")
    if not names:
        print("  (none listed)")

    candidates = [os.environ.get("GEMMA_MODEL") or "gemma-4-26b-a4b-it", "gemma-4-31b-it", "gemma-4-26b-a4b-it"]
    candidates += [n for n, m in names if "generateContent" in m and "gemma-4" in n]
    tested = []
    for model in candidates:
        if model in tested:
            continue
        tested.append(model)
        print(f"\nModel: {model}")
        plain = {"contents": [{"role": "user", "parts": [{"text": "Reply with the single word: pong"}]}]}
        withsys = dict(plain, system_instruction={"parts": [{"text": "You answer with one word."}]})
        for label, body in (("plain prompt", plain), ("with system instruction", withsys)):
            status, data, msg = call("POST", f"/models/{model}:generateContent", body)
            result = reply_text(data) if status == 200 else msg
            print(f"  {label:<25} HTTP {status}  {result}")
        if len(tested) >= 4:
            break
    replay_module_request(os.environ.get("GEMMA_MODEL") or "gemma-4-26b-a4b-it")
    print("\nSend me this whole output (it contains no key).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
