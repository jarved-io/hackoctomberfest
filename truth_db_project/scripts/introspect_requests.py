"""Runs INSIDE a process whose PYTHONPATH points at one pinned `requests` version.
Prints that version's public API surface as JSON. Called by generate_snapshots.py.
The truth comes from the real installed library, never from an LLM."""
import importlib
import inspect
import json
import warnings

warnings.filterwarnings("ignore")
import requests  # noqa: E402

MODULES = ["requests", "requests.api", "requests.sessions", "requests.models",
           "requests.adapters", "requests.auth", "requests.cookies",
           "requests.exceptions", "requests.structures", "requests.status_codes",
           "requests.utils", "requests.hooks"]

# **kwargs of these callables are forwarded to a concrete signature; we resolve them
# so "unknown keyword" checks are exact instead of "anything goes".
_HTTP = ["get", "options", "head", "post", "put", "patch", "delete"]
FORWARDS = {f"requests.api.{m}": "requests.sessions.Session.request" for m in _HTTP + ["request"]}
FORWARDS.update({f"requests.sessions.Session.{m}": "requests.sessions.Session.request" for m in _HTTP})


def sig_info(fn, drop_self=False):
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None
    args, required, var_kw, var_pos = [], [], False, False
    for i, (n, p) in enumerate(sig.parameters.items()):
        if drop_self and i == 0 and n in ("self", "cls"):
            continue
        if p.kind is p.VAR_KEYWORD:
            var_kw = True
        elif p.kind is p.VAR_POSITIONAL:
            var_pos = True
        else:
            args.append(n)
            if p.default is p.empty:
                required.append(n)
    return {"arguments": args, "required": required,
            "accepts_var_kwargs": var_kw, "accepts_var_args": var_pos}


def own(obj, module_names):
    return getattr(obj, "__module__", "") in module_names


apis = {}


def add(qname, module, symbol, kind, extra=None, canonical=None):
    e = {"module": module, "symbol": symbol, "kind": kind, "deprecated": False}
    if extra:
        e.update(extra)
    if canonical and canonical != qname:
        e["alias_of"] = canonical
    apis[qname] = e


def add_class(qname, module, symbol, cls, canonical):
    if "__init__" in cls.__dict__:
        init = sig_info(cls.__init__, drop_self=True) or {}
    else:
        init = {"arguments": [], "required": [], "accepts_var_kwargs": False, "accepts_var_args": False}
    kind = "exception" if issubclass(cls, BaseException) else "class"
    add(qname, module, symbol, kind, init, canonical)
    attrs = list(getattr(cls, "__attrs__", []))
    for a in attrs:
        add(f"{qname}.{a}", module, f"{symbol}.{a}", "attribute", None,
            f"{canonical}.{a}" if canonical != qname else None)
    for name, _member in inspect.getmembers(cls):
        if name.startswith("_") or name in attrs:
            continue
        owner = next((c for c in cls.__mro__ if name in c.__dict__), None)
        if owner is None or not owner.__module__.startswith("requests"):
            continue
        raw = owner.__dict__[name]
        if isinstance(raw, property):
            add(f"{qname}.{name}", module, f"{symbol}.{name}", "property")
        elif inspect.isfunction(raw) or isinstance(raw, (staticmethod, classmethod)):
            fn = raw.__func__ if isinstance(raw, (staticmethod, classmethod)) else raw
            info = sig_info(fn, drop_self=not isinstance(raw, staticmethod)) or {}
            fq = f"{owner.__module__}.{owner.__name__}.{name}"
            if fq in FORWARDS:
                info["forwards_kwargs_to"] = FORWARDS[fq]
            add(f"{qname}.{name}", module, f"{symbol}.{name}", "method", info)


for modname in MODULES:
    mod = importlib.import_module(modname)
    public = getattr(mod, "__all__", None) or [n for n in dir(mod) if not n.startswith("_")]
    for name in public:
        obj = getattr(mod, name, None)
        qname = f"{modname}.{name}"
        if inspect.ismodule(obj):
            if obj.__name__.startswith("requests"):
                add(qname, modname, name, "module")
            continue
        if inspect.isclass(obj) and own(obj, set(MODULES)):
            add_class(qname, modname, name, obj, f"{obj.__module__}.{obj.__name__}")
        elif inspect.isfunction(obj) and own(obj, set(MODULES)):
            canon = f"{obj.__module__}.{obj.__name__}"
            info = sig_info(obj) or {}
            if canon in FORWARDS:
                info["forwards_kwargs_to"] = FORWARDS[canon]
            add(qname, modname, name, "function", info, canon)
        elif modname in ("requests", "requests.status_codes") and not callable(obj) \
                and isinstance(obj, (int, str, float, dict)) or name == "codes":
            add(qname, modname, name, "constant")

# resolve forwarded kwargs -> concrete accepted list
for q, e in apis.items():
    tgt = e.get("forwards_kwargs_to")
    if tgt and tgt in apis:
        e["forwarded_arguments"] = [a for a in apis[tgt]["arguments"] if a not in ("method", "url")]
        e["accepts_var_kwargs"] = False  # fully resolved; unknown kwargs raise TypeError
        e["accepted_arguments"] = sorted(set(e["arguments"]) | set(e["forwarded_arguments"]))

print(json.dumps({"version": requests.__version__, "apis": apis}, sort_keys=True))
