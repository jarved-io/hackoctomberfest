export default function EmptyState() {
  return (
    <div className="rounded-md border border-dashed border-zinc-700 px-6 py-12 text-center">
      <p className="text-lg font-semibold text-zinc-100">🛡 Ready to verify</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-zinc-400">
        Paste AI-generated code above and click Verify Code. We&apos;ll check imports, functions, classes and arguments against the selected API version.
      </p>
    </div>
  );
}
