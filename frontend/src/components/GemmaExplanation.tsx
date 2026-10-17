import type { VerificationResponse } from "@/types/verification";
import CorrectedCode from "@/components/CorrectedCode";

export default function GemmaExplanation({ result, original }: { result: VerificationResponse; original: string }) {
  return (
    <section aria-labelledby="gemma-h" className="rounded-md border border-zinc-800 bg-zinc-900 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="gemma-h" className="text-base font-semibold text-white">🤖 Gemma 4 Explanation</h2>
        <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">Based on verified API evidence</span>
      </div>
      {result.aiAvailable && result.explanation ? (
        <>
          <p className="mt-3 whitespace-pre-line text-sm text-zinc-200">{result.explanation.text}</p>
          {result.explanation.correctedCode && <CorrectedCode original={original} corrected={result.explanation.correctedCode} />}
        </>
      ) : (
        <p role="alert" className="mt-3 text-sm text-amber-300">API verification completed, but the AI explanation is temporarily unavailable.</p>
      )}
    </section>
  );
}
