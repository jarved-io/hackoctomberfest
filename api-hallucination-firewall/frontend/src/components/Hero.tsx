export default function Hero() {
  return (
    <section className="mx-auto max-w-6xl px-4 pb-6 pt-10">
      <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">AI writes code. We verify the APIs.</h1>
      <p className="mt-3 max-w-2xl text-zinc-300">
        Catch hallucinated functions, imports, and arguments before they break your project.
      </p>
      <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-sm text-zinc-400">
        {["API surface verified", "Version aware", "Gemma-powered explanations"].map((t) => (
          <li key={t} className="flex items-center gap-2">
            <span aria-hidden className="h-2 w-2 rounded-full bg-emerald-400" />
            {t}
          </li>
        ))}
      </ul>
    </section>
  );
}
