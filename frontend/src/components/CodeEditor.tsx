"use client";
import { useRef } from "react";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onClear: () => void;
  highlightLines?: number[];
  disabled?: boolean;
}

export default function CodeEditor({ value, onChange, onClear, highlightLines = [], disabled }: Props) {
  const gutter = useRef<HTMLDivElement>(null);
  const lines = Math.max(value.split("\n").length, 12);
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <label htmlFor="code-input" className="text-sm font-medium text-zinc-200">AI-generated code (Python)</label>
        <button type="button" onClick={onClear} disabled={disabled || !value}
          className="rounded px-2 py-1 text-xs text-zinc-400 hover:text-white disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400">
          Clear
        </button>
      </div>
      <div className="flex h-72 overflow-hidden rounded-md border border-zinc-700 bg-zinc-950 focus-within:ring-2 focus-within:ring-emerald-400">
        <div ref={gutter} aria-hidden className="select-none overflow-hidden bg-zinc-900 py-3 text-right font-mono text-sm leading-6 text-zinc-500">
          {Array.from({ length: lines }, (_, i) => (
            <div key={i} className={`px-3 ${highlightLines.includes(i + 1) ? "bg-red-500/20 text-red-300" : ""}`}>{i + 1}</div>
          ))}
        </div>
        <textarea
          id="code-input"
          value={value}
          disabled={disabled}
          spellCheck={false}
          wrap="off"
          onChange={(e) => onChange(e.target.value)}
          onScroll={(e) => { if (gutter.current) gutter.current.scrollTop = e.currentTarget.scrollTop; }}
          placeholder={'import requests\n\nresponse = requests.get(\n    "https://example.com",\n    timeout_seconds=10\n)'}
          className="min-w-0 flex-1 resize-none bg-transparent p-3 font-mono text-sm leading-6 text-zinc-100 placeholder:text-zinc-600 focus:outline-none"
        />
      </div>
    </div>
  );
}
