import type { VerifiedItem as Item } from "@/types/verification";
export default function VerifiedItem({ item }: { item: Item }) {
  return (
    <li className="rounded-md border border-emerald-500/30 bg-zinc-900 p-3">
      <p className="text-xs font-bold tracking-wider text-emerald-300">✓ VERIFIED{item.line !== undefined && <span className="ml-2 font-normal text-zinc-500">Line {item.line}</span>}</p>
      <p className="mt-1 break-all font-mono text-sm text-white">{item.symbol}</p>
      <p className="text-xs text-zinc-400">{item.message ?? `${item.kind} exists`}</p>
    </li>
  );
}
