# API Truth Database (Person 4 layer)

The deterministic source of truth for **API Hallucination Firewall**. Gemma never decides
whether an API exists - this layer does, and Gemma only explains its evidence.

Target (per the team PRD): **Python + `requests`**, versions 2.25.1, 2.28.2, 2.31.0, 2.32.3.

## How the data is made
`scripts/generate_snapshots.py` pip-installs each pinned `requests` version and runs
`inspect.signature` over its public modules, so snapshots mirror the real library
(~500 symbols each: functions, classes, methods, properties, exceptions, attributes).
`**kwargs` of `requests.get/post/...` and `Session.get/...` are resolved to the real
`Session.request` parameters, so `timeout_seconds` is provably invalid.

    python scripts/generate_snapshots.py 2.25.1 2.28.2 2.31.0 2.32.3

Snapshot entry (`data/python/requests/<version>.json` -> `apis["requests.get"]`):
`module, symbol, kind, arguments, required, accepts_var_kwargs, accepted_arguments, alias_of, deprecated`.
`deprecated` is currently always `false` (no reliable machine source yet).

## Using it (Person 2 / Person 1)
    from truth_db import verify_symbol, verify_kwargs, suggest
    verify_symbol("requests", "2.31.0", "requests.fetch")
    # {status: "missing", suggestions: [{symbol: "requests.get", source: "curated", ...}]}
    verify_kwargs("requests", "2.31.0", "requests.get", ["timeout_seconds"], n_positional=1)
    # {status: "invalid_arguments", invalid: [{argument: "timeout_seconds", suggestions: [{argument: "timeout"}]}]}

Statuses: `exists | missing | wrong_version | unknown_library | unsupported_version`
(symbols) and `ok | invalid_arguments | unverifiable_var_kwargs | cannot_verify` (arguments).
Feed these dicts to Gemma as the *evidence* block. CLI for non-Python callers:
`python -m truth_db kwargs requests 2.31.0 requests.get timeout_seconds --positional 1`.

Contract for the validator (Person 2): pass **fully-qualified** names after resolving import
aliases (`import requests as r; r.get` -> `requests.get`; `from requests import get` -> `requests.get`).
If a name can't be resolved to the library with certainty, do not flag it (see `ambiguous_symbol` fixture).

## Curated hints
`data/curated/requests.json` holds common AI mistakes (httpx-isms like `follow_redirects`) mapped
to the right API. They only power suggestions; `test_curated_hints_are_honest` in
`test_truth_db.py` prove each wrong name is truly absent and each target truly present.

## QA
`tests/fixtures.py` has 12 snippets covering the PRD checklist (valid, fake function/argument/method/class,
wrong import, wrong version, malformed, empty, ambiguous). `python -m pytest` runs the truth-layer checks.
Still to cover once the API exists: oversized input, Gemma down, truth DB missing (the lookup raises
`UnsupportedVersion`, which should become a graceful "cannot verify").

## Limitations
Only module-level/class public surface; no call-chain type inference (`requests.get(u).json_data`
needs the validator to know the return type is `Response`). One library, 4 versions.
