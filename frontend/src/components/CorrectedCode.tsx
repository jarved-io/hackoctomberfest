"use client";
import { useState } from "react";

export default function CorrectedCode({ original, corrected }: { original: string; corrected: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(corrected);
    } catch {
      const t = document.createElement("textarea");
      t.value = corrected; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove();
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  const block = "overflow-x-auto rounded-md border bg-zinc-950 p-3 font-mono text-xs leading-5";
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm font-medium text-zinc-200">Compare</p>
        <button type="button" onClick={copy} aria-live="polite"
          className="rounded border border-zinc-700 px-3 py-1 text-xs text-zinc-200 hover:bg-zinc-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400">
          {copied ? "Copied ✓" : "Copy"}
        </button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <div><p className="mb-1 text-xs uppercase tracking-wider text-zinc-500">Original</p><pre className={`${block} border-red-500/30 text-zinc-300`}>{original}</pre></div>
        <div><p className="mb-1 text-xs uppercase tracking-wider text-zinc-500">Suggested correction</p><pre className={`${block} border-emerald-500/30 text-emerald-100`}>{corrected}</pre></div>
      </div>
    </div>
  );
}
