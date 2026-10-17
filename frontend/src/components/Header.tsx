export default function Header() {
  return (
    <header className="border-b border-zinc-800 bg-zinc-950/80">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div>
          <p className="text-sm font-semibold tracking-wide text-zinc-100">🛡 API HALLUCINATION FIREWALL</p>
          <p className="text-xs text-zinc-400">Don&apos;t trust AI-generated code. Verify it.</p>
        </div>
        <nav aria-label="Primary" className="flex gap-4 text-sm">
          <a href="#verify" className="rounded text-zinc-300 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400">Verify</a>
          <a href="#how-it-works" className="rounded text-zinc-300 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400">How It Works</a>
        </nav>
      </div>
    </header>
  );
}
