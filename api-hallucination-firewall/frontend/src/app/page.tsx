"use client";
import { useEffect, useMemo, useState } from "react";
import Header from "@/components/Header";
import Hero from "@/components/Hero";
import CodeEditor from "@/components/CodeEditor";
import LibrarySelector from "@/components/LibrarySelector";
import VersionSelector from "@/components/VersionSelector";
import VerifyButton from "@/components/VerifyButton";
import EmptyState from "@/components/EmptyState";
import VerificationSummary from "@/components/VerificationSummary";
import IssueCard from "@/components/IssueCard";
import VerifiedItem from "@/components/VerifiedItem";
import GemmaExplanation from "@/components/GemmaExplanation";
import { ApiError, ERROR_MESSAGES, getLibraries, verifyCode } from "@/lib/api";
import { DEMO_EXAMPLES, FALLBACK_LIBRARIES } from "@/lib/demo";
import type { LibraryOption, VerificationResponse } from "@/types/verification";

export default function Page() {
  const [libs, setLibs] = useState<LibraryOption[]>(FALLBACK_LIBRARIES);
  const [library, setLibrary] = useState(FALLBACK_LIBRARIES[0].name);
  const [version, setVersion] = useState(FALLBACK_LIBRARIES[0].versions[0]);
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerificationResponse | null>(null);
  const [checkedCode, setCheckedCode] = useState("");

  useEffect(() => {
    getLibraries().then((l) => { setLibs(l); setLibrary(l[0].name); setVersion(l[0].versions[0]); });
  }, []);
  const versions = useMemo(() => libs.find((l) => l.name === library)?.versions ?? [], [libs, library]);

  const verify = async () => {
    if (loading) return;
    setError(null);
    if (!code.trim()) { setError(ERROR_MESSAGES.empty); return; }
    setLoading(true);
    try {
      setResult(await verifyCode({ code, library, version }));
      setCheckedCode(code);
    } catch (e) {
      setResult(null);
      setError(e instanceof ApiError ? e.message : ERROR_MESSAGES.unavailable);
    } finally {
      setLoading(false);
    }
  };

  const srcLines = checkedCode.split("\n");
  const issueLines = result?.issues.flatMap((i) => (i.line !== undefined ? [i.line] : [])) ?? [];

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <Header />
      <main>
        <Hero />
        <section id="verify" className="mx-auto grid max-w-6xl gap-6 px-4 pb-16 lg:grid-cols-2">
          <div className="min-w-0 space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <LibrarySelector value={library} options={libs.map((l) => l.name)} disabled={loading}
                onChange={(v) => { setLibrary(v); setVersion(libs.find((l) => l.name === v)?.versions[0] ?? ""); }} />
              <VersionSelector value={version} options={versions} onChange={setVersion} disabled={loading} />
            </div>
            <CodeEditor value={code} onChange={setCode} highlightLines={issueLines} disabled={loading}
              onClear={() => { setCode(""); setResult(null); setError(null); }} />
            <div className="flex flex-wrap items-center gap-3">
              <VerifyButton loading={loading} onClick={verify} />
              <span className="text-xs text-zinc-500">Try example:</span>
              {DEMO_EXAMPLES.map((ex) => (
                <button key={ex.id} type="button" disabled={loading}
                  onClick={() => { setCode(ex.code); setResult(null); setError(null); }}
                  className="rounded border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400">
                  {ex.label}
                </button>
              ))}
            </div>
            {error && <p role="alert" className="rounded-md border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
          </div>

          <div className="min-w-0 space-y-4" aria-live="polite">
            {loading ? (
              <p className="rounded-md border border-zinc-800 p-6 text-sm text-zinc-300">Checking API references against {library} {version}…</p>
            ) : result ? (
              <>
                <VerificationSummary result={result} />
                {result.issues.length > 0 && (
                  <section aria-labelledby="issues-h" className="space-y-3">
                    <h2 id="issues-h" className="text-sm font-semibold text-zinc-200">Issues</h2>
                    {result.issues.map((i) => (
                      <IssueCard key={i.id} issue={i} sourceLine={i.line !== undefined ? srcLines[i.line - 1] : undefined} />
                    ))}
                  </section>
                )}
                {result.verifiedItems.length > 0 && (
                  <section aria-labelledby="ok-h">
                    <h2 id="ok-h" className="mb-2 text-sm font-semibold text-zinc-200">Verified</h2>
                    <ul className="grid gap-2 sm:grid-cols-2">
                      {result.verifiedItems.map((v, i) => <VerifiedItem key={`${v.symbol}-${i}`} item={v} />)}
                    </ul>
                  </section>
                )}
                {result.issues.some((i) => i.severity !== "info") && <GemmaExplanation result={result} original={checkedCode} />}
              </>
            ) : <EmptyState />}
          </div>
        </section>

        <section id="how-it-works" className="mx-auto max-w-6xl border-t border-zinc-800 px-4 py-10">
          <h2 className="text-lg font-semibold">How It Works</h2>
          <ol className="mt-3 grid gap-4 text-sm text-zinc-400 sm:grid-cols-3">
            <li><b className="text-zinc-200">1. Extract.</b> API references are pulled from your code.</li>
            <li><b className="text-zinc-200">2. Verify.</b> Each is checked against the real API surface of the chosen version. This is the source of truth.</li>
            <li><b className="text-zinc-200">3. Explain.</b> Gemma explains verified findings and suggests a fix. It never decides what is valid.</li>
          </ol>
        </section>
      </main>
    </div>
  );
}
