interface Props { value: string; options: string[]; onChange: (v: string) => void; disabled?: boolean }
export default function LibrarySelector({ value, options, onChange, disabled }: Props) {
  return (
    <div>
      <label htmlFor="library" className="mb-1 block text-sm font-medium text-zinc-200">Library</label>
      <select id="library" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400">
        {options.map((o) => <option key={o}>{o}</option>)}
      </select>
    </div>
  );
}
