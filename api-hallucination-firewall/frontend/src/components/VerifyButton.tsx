interface Props { loading: boolean; onClick: () => void }
export default function VerifyButton({ loading, onClick }: Props) {
  return (
    <button type="button" onClick={onClick} disabled={loading} aria-busy={loading}
      className="inline-flex items-center justify-center gap-2 rounded-md bg-emerald-500 px-6 py-3 text-sm font-bold tracking-wide text-zinc-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-70 focus:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950">
      {loading ? (
        <>
          <span aria-hidden className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-950 border-t-transparent" />
          VERIFYING...
        </>
      ) : (
        <>🔍 VERIFY CODE</>
      )}
    </button>
  );
}
