import type { VerificationResponse } from "@/types/verification";

const CFG = {
  all_valid: { icon: "✓", color: "border-emerald-500/50 text-emerald-300" },
  issues_found: { icon: "⚠", color: "border-amber-500/50 text-amber-300" },
  critical: { icon: "✕", color: "border-red-500/50 text-red-300" },
  inconclusive: { icon: "?", color: "border-zinc-500/50 text-zinc-300" },
  error: { icon: "✕", color: "border-red-500/50 text-red-300" },
} as const;

export default function VerificationSummary({ result }: { result: VerificationResponse }) {
  const n = result.issues.length;
  const title =
    result.overallStatus === "all_valid" ? "All API references verified"
    : result.overallStatus === "critical" ? "Invalid API references detected"
    : result.overallStatus === "error" ? "This code could not be verified"
    : result.overallStatus === "inconclusive" && n === 0 ? "Nothing could be verified for this library/version"
    : result.overallStatus === "inconclusive" ? `${n} reference${n === 1 ? "" : "s"} could not be verified`
    : `${n} potential API issue${n === 1 ? "" : "s"} found`;
  const c = CFG[result.overallStatus];
  return (
    <div role="status" className={`rounded-md border bg-zinc-900 p-4 ${c.color}`}>
      <p className="text-xs uppercase tracking-wider text-zinc-400">Verification Result</p>
      <p className="mt-1 text-lg font-semibold"><span aria-hidden>{c.icon} </span>{title}</p>
      <p className="text-sm text-zinc-400">{result.checkedCount} API reference{result.checkedCount === 1 ? "" : "s"} checked</p>
    </div>
  );
}
