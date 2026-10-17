"""truth_db - deterministic, LLM-free API lookups against versioned snapshots.

Person 2 (validator) calls these functions; Person 1 (Gemma) receives their
return values as *evidence*. Nothing here ever calls a model.

    from truth_db import verify_symbol, verify_kwargs
    verify_symbol("requests", "2.31.0", "requests.fetch")
    verify_kwargs("requests", "2.31.0", "requests.get", ["timeout_seconds"], n_positional=1)

All results are plain JSON-serialisable dicts with a stable shape.
"""
from __future__ import annotations

import difflib
import functools
import json
import pathlib
import re
from typing import Iterable, Optional

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
LANGUAGE = "python"


class TruthDBError(Exception):
    """Base error; the API layer should map these to a graceful 'cannot verify' response."""


class UnknownLibrary(TruthDBError):
    pass


class UnsupportedVersion(TruthDBError):
    def __init__(self, library, version, known):
        super().__init__(f"{library} {version!r} not in snapshots (known: {', '.join(known)})")
        self.library, self.version, self.known = library, version, known


def _vkey(v: str):
    return tuple(int(x) if x.isdigit() else x for x in re.split(r"[.\-]", v))


def available_versions(library: str) -> list[str]:
    d = DATA_DIR / LANGUAGE / library
    if not d.is_dir():
        return []
    return sorted((p.stem for p in d.glob("*.json")), key=_vkey)


def supported_libraries() -> list[str]:
    d = DATA_DIR / LANGUAGE
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []


@functools.lru_cache(maxsize=32)
def _load(library: str, version: str) -> dict:
    path = DATA_DIR / LANGUAGE / library / f"{version}.json"
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as e:  # truth database missing -> caller degrades gracefully
        raise UnsupportedVersion(library, version, available_versions(library)) from e


@functools.lru_cache(maxsize=8)
def _curated(library: str) -> dict:
    path = DATA_DIR / "curated" / f"{library}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def load(library: str, version: str) -> dict:
    if library not in supported_libraries():
        raise UnknownLibrary(f"{library!r} not supported (supported: {', '.join(supported_libraries())})")
    return _load(library, version)


def lookup(library: str, version: str, qname: str) -> Optional[dict]:
    return load(library, version)["apis"].get(qname)


def versions_containing(library: str, qname: str) -> list[str]:
    return [v for v in available_versions(library) if qname in _load(library, v)["apis"]]


def suggest(library: str, version: str, qname: str, n: int = 3, cutoff: float = 0.6) -> list[dict]:
    """Closest valid symbols. Curated mappings first (known hallucinations), then string similarity."""
    apis = load(library, version)["apis"]
    out, seen = [], set()
    cur = _curated(library).get("symbol_corrections", {}).get(qname)
    if cur:
        target = cur["use"]
        if target.split("(")[0] in apis:
            out.append({"symbol": target, "source": "curated", "note": cur.get("note", "")})
            seen.add(target)
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    pool = [k for k, v in apis.items() if "alias_of" not in v or k.count(".") <= 2]
    by_norm = {}
    for k in pool:
        by_norm.setdefault(norm(k), k)
    for m in difflib.get_close_matches(norm(qname), list(by_norm), n=n * 2, cutoff=cutoff):
        k = by_norm[m]
        if k not in seen:
            seen.add(k)
            out.append({"symbol": k, "source": "similarity",
                        "score": round(difflib.SequenceMatcher(None, norm(qname), m).ratio(), 2)})
    return out[:n]


def verify_symbol(library: str, version: str, qname: str) -> dict:
    """Checks A/B/D/E: does `qname` exist in library@version? Includes version evidence."""
    base = {"check": "symbol", "library": library, "version": version, "symbol": qname}
    try:
        entry = lookup(library, version, qname)
    except UnknownLibrary as e:
        return {**base, "status": "unknown_library", "detail": str(e), "suggestions": []}
    except UnsupportedVersion as e:
        return {**base, "status": "unsupported_version", "detail": str(e),
                "known_versions": e.known, "suggestions": []}
    if entry:
        return {**base, "status": "exists", "kind": entry["kind"], "evidence": entry,
                "deprecated": entry.get("deprecated", False)}
    seen_in = versions_containing(library, qname)
    res = {**base, "status": "missing", "suggestions": suggest(library, version, qname)}
    if seen_in:  # exists elsewhere -> a *version* problem, not a hallucination
        res["status"] = "wrong_version"
        res["exists_in_versions"] = seen_in
        res["detail"] = f"{qname} exists in {seen_in[0]}..{seen_in[-1]} but not in {version}"
    return res


def verify_kwargs(library: str, version: str, qname: str, kwargs: Iterable[str],
                  n_positional: int = 0) -> dict:
    """Check C: are the keyword arguments accepted by qname's real signature?
    `n_positional` = number of positional args at the call site (only used for the
    'too many positional' check)."""
    kwargs = list(kwargs)
    base = {"check": "arguments", "library": library, "version": version, "symbol": qname,
            "supplied": kwargs}
    sym = verify_symbol(library, version, qname)
    if sym["status"] != "exists":
        return {**base, "status": "cannot_verify", "reason": sym["status"]}
    e = sym["evidence"]
    if e["kind"] not in ("function", "method", "class", "exception"):
        return {**base, "status": "cannot_verify", "reason": f"{e['kind']} is not callable"}
    accepted = e.get("accepted_arguments", e.get("arguments", []))
    if e.get("accepts_var_kwargs"):
        return {**base, "status": "unverifiable_var_kwargs", "accepted": accepted,
                "detail": "signature takes **kwargs; unknown names cannot be proven invalid"}
    invalid = [k for k in kwargs if k not in accepted]
    corr = _curated(library).get("argument_corrections", {})
    findings = []
    for k in invalid:
        alts = []
        c = corr.get(k)
        if c and c["use"] in accepted:
            alts.append({"argument": c["use"], "source": "curated", "note": c.get("note", "")})
        for m in difflib.get_close_matches(k, accepted, n=2, cutoff=0.5):
            if all(a["argument"] != m for a in alts):
                alts.append({"argument": m, "source": "similarity"})
        findings.append({"argument": k, "suggestions": alts[:3]})
    max_pos = len(e.get("arguments", []))
    too_many = (n_positional > max_pos) and not e.get("accepts_var_args")
    status = "invalid_arguments" if (invalid or too_many) else "ok"
    res = {**base, "status": status, "accepted": accepted, "invalid": findings}
    if too_many:
        res["detail"] = f"{qname} takes at most {max_pos} positional arguments, got {n_positional}"
    missing_required = [r for r in e.get("required", []) if r not in kwargs]
    res["required"] = e.get("required", [])
    res["required_not_passed_by_keyword"] = missing_required  # informational; may be positional
    return res
