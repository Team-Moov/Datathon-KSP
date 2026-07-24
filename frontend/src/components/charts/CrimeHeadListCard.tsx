export interface CrimeHeadOption {
  id: number
  name: string
  code: string | null
}

/** Crime-category reference list — mirrors DistrictListCard for the same
 * "resolve a name before calling a tool that needs an id" pattern. */
function CrimeHeadListCard({ crimeHeads }: { crimeHeads: CrimeHeadOption[] }) {
  if (crimeHeads.length === 0) {
    return <p className="px-1 text-xs text-zinc-400">No crime categories found.</p>
  }
  return (
    <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
      {crimeHeads.map((c) => (
        <li key={c.id} className="flex items-center justify-between px-3 py-2 text-xs">
          <span className="font-medium text-zinc-800 dark:text-zinc-100">{c.name}</span>
          {c.code ? <span className="text-[10px] text-zinc-400">{c.code}</span> : null}
        </li>
      ))}
    </ul>
  )
}

export { CrimeHeadListCard }
