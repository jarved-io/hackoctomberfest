"""CLI bridge so a non-Python backend (e.g. a Next.js route) can call the module.

    echo '{"code": "...", "library": "requests", "version": "2.31.0",
           "findings": [...], "apiEvidence": {...}}' | python -m ai_module

Reads one JSON object on stdin, writes the result JSON on stdout.
"""

import json
import sys

from .explain import generate_explanation


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = generate_explanation(
            payload["code"], payload["library"], payload["version"],
            payload["findings"], payload.get("apiEvidence") or {},
        )
    except (KeyError, ValueError, TypeError) as exc:
        print(json.dumps({"error": "bad_input", "detail": str(exc)[:300]}))
        return 2
    print(json.dumps(result.to_dict()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
