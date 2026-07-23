import { ShieldCheck } from "lucide-react"

interface PersonSearchResult {
  person_id: string
  name: string
  aliases: string[] | null
  human_verified: boolean
}

/** Name-search results the assistant resolved before calling a person-scoped
 * tool — shown so the investigator can see (and correct) exactly who was
 * matched, especially when more than one person shares a name. */
function PersonSearchResultsList({ results }: { results: PersonSearchResult[] }) {
  if (results.length === 0) {
    return <p className="px-1 text-xs text-zinc-400">No matching persons found.</p>
  }
  return (
    <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
      {results.map((person) => (
        <li key={person.person_id} className="flex items-start justify-between px-3 py-2 text-xs">
          <div>
            <p className="flex items-center gap-1.5 font-medium text-zinc-800 dark:text-zinc-100">
              {person.name}
              {person.human_verified ? <ShieldCheck className="size-3 text-affirm-500" /> : null}
            </p>
            {person.aliases && person.aliases.length > 0 ? (
              <p className="text-[10px] text-zinc-400">aka {person.aliases.join(", ")}</p>
            ) : null}
          </div>
          <span className="shrink-0 font-mono text-[10px] text-zinc-400">{person.person_id.slice(0, 8)}…</span>
        </li>
      ))}
    </ul>
  )
}

export { PersonSearchResultsList }
export type { PersonSearchResult }
