interface MultiJurisdictionOffender {
  person_id: string
  name: string
  jurisdiction_count: number
  units: number[]
}

/** A person's cases spanning multiple police units is itself a signal of organized/mobile activity. */
function MultiJurisdictionOffendersList({ offenders }: { offenders: MultiJurisdictionOffender[] }) {
  if (offenders.length === 0) {
    return <p className="px-1 text-xs text-zinc-400">No multi-jurisdiction offenders found.</p>
  }
  return (
    <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
      {offenders.map((offender) => (
        <li key={offender.person_id} className="flex items-center justify-between px-3 py-2 text-xs">
          <div>
            <p className="font-medium text-zinc-800 dark:text-zinc-100">{offender.name || offender.person_id}</p>
            <p className="text-[10px] text-zinc-400">Units: {offender.units.join(", ")}</p>
          </div>
          <span className="shrink-0 rounded-full bg-critical-500/10 px-2 py-0.5 text-[10px] font-medium text-critical-600 dark:text-critical-400">
            {offender.jurisdiction_count} jurisdictions
          </span>
        </li>
      ))}
    </ul>
  )
}

export { MultiJurisdictionOffendersList }
export type { MultiJurisdictionOffender }
