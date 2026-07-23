import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Check, Search, X } from "lucide-react"

import { Input } from "@/components/ui/input"
import { searchPersonsByName } from "@/features/persons/personsApi"
import { useDebouncedValue } from "@/lib/hooks/useDebounce"
import type { PersonSummary } from "@/lib/types/api"

export interface PickedPerson {
  id: string
  name: string
}

/**
 * Reusable name→UUID typeahead. The single connective tissue that lets every
 * analysis surface (risk, network, financial) take a *person the user recognizes*
 * instead of a raw UUID they'd have to copy-paste. Resolves the id under the hood
 * via /persons/search; the caller only ever gets {id, name}.
 */
function PersonPicker({
  selected,
  onSelect,
  onClear,
  placeholder = "Search a person by name…",
  autoFocus,
}: {
  selected: PickedPerson | null
  onSelect: (person: PickedPerson) => void
  onClear?: () => void
  placeholder?: string
  autoFocus?: boolean
}) {
  const [query, setQuery] = React.useState("")
  const [isOpen, setIsOpen] = React.useState(false)
  const debounced = useDebouncedValue(query, 250)
  const containerRef = React.useRef<HTMLDivElement>(null)

  const { data: matches, isFetching } = useQuery({
    queryKey: ["person-picker", debounced],
    queryFn: () => searchPersonsByName(debounced),
    enabled: debounced.trim().length >= 2,
  })

  React.useEffect(() => {
    function onDocClick(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setIsOpen(false)
    }
    document.addEventListener("mousedown", onDocClick)
    return () => document.removeEventListener("mousedown", onDocClick)
  }, [])

  function choose(person: PersonSummary) {
    onSelect({ id: person.id, name: person.full_name })
    setQuery("")
    setIsOpen(false)
  }

  // When a person is already selected, show a compact "chip" with a clear button
  // rather than a text field, so the selection reads as a resolved entity.
  if (selected) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-md border border-accent-300/60 bg-accent-500/5 px-3 py-2 dark:border-accent-400/30">
        <span className="flex items-center gap-1.5 truncate text-sm text-zinc-800 dark:text-zinc-100">
          <Check className="size-3.5 shrink-0 text-accent-600 dark:text-accent-400" />
          {selected.name}
        </span>
        {onClear ? (
          <button
            type="button"
            onClick={onClear}
            className="shrink-0 rounded p-0.5 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
            title="Choose a different person"
          >
            <X className="size-3.5" />
          </button>
        ) : null}
      </div>
    )
  }

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-zinc-400" />
        <Input
          value={query}
          autoFocus={autoFocus}
          onChange={(event) => {
            setQuery(event.target.value)
            setIsOpen(true)
          }}
          onFocus={() => setIsOpen(true)}
          placeholder={placeholder}
          className="pl-8"
        />
      </div>
      {isOpen && debounced.trim().length >= 2 ? (
        <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-md border border-zinc-200 bg-white shadow-lg dark:border-zinc-800 dark:bg-zinc-900">
          {isFetching && !matches ? (
            <li className="px-3 py-2 text-xs text-zinc-400">Searching…</li>
          ) : matches && matches.length > 0 ? (
            matches.map((person) => (
              <li key={person.id}>
                <button
                  type="button"
                  onClick={() => choose(person)}
                  className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm hover:bg-accent-50 dark:hover:bg-accent-900/40"
                >
                  <span className="truncate text-zinc-800 dark:text-zinc-100">{person.full_name}</span>
                  {person.human_verified ? (
                    <span className="shrink-0 text-[10px] text-affirm-600 dark:text-affirm-500">verified</span>
                  ) : null}
                </button>
              </li>
            ))
          ) : (
            <li className="px-3 py-2 text-xs text-zinc-400">No matches.</li>
          )}
        </ul>
      ) : null}
    </div>
  )
}

export { PersonPicker }
