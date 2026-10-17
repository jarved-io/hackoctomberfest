"""CLI so any teammate/service (incl. Node via child_process) can query the truth layer.
  python -m truth_db symbol requests 2.31.0 requests.fetch
  python -m truth_db kwargs requests 2.31.0 requests.get timeout_seconds --positional 1
  python -m truth_db versions requests
Prints JSON."""
import argparse, json, sys
import truth_db as t

p = argparse.ArgumentParser(prog="truth_db")
sub = p.add_subparsers(dest="cmd", required=True)
a = sub.add_parser("symbol"); a.add_argument("library"); a.add_argument("version"); a.add_argument("qname")
b = sub.add_parser("kwargs"); b.add_argument("library"); b.add_argument("version"); b.add_argument("qname")
b.add_argument("kw", nargs="*"); b.add_argument("--positional", type=int, default=0)
c = sub.add_parser("versions"); c.add_argument("library")
args = p.parse_args()
if args.cmd == "symbol":
    out = t.verify_symbol(args.library, args.version, args.qname)
elif args.cmd == "kwargs":
    out = t.verify_kwargs(args.library, args.version, args.qname, args.kw, args.positional)
else:
    out = t.available_versions(args.library)
json.dump(out, sys.stdout, indent=2); print()
