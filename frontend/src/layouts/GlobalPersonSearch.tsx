import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Search, UserRound } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { searchPersonsByName } from "@/features/persons/personsApi"
import { useDebouncedValue } from "@/lib/hooks/useDebounce"

function GlobalPersonSearch() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [rawQuery, setRawQuery] = React.useState("")
  const [isOpen, setIsOpen] = React.useState(false)
  const debouncedQuery = useDebouncedValue(rawQuery, 300)

  const { data: matches, isFetching } = useQuery({
    queryKey: ["global-person-search", debouncedQuery],
    queryFn: () => searchPersonsByName(debouncedQuery),
    enabled: debouncedQuery.trim().length >= 2,
  })

  function navigateToPerson(personId: string) {
    setIsOpen(false)
    setRawQuery("")
    navigate(`/persons/${personId}`)
  }

  return (
    <Popover open={isOpen && debouncedQuery.trim().length >= 2} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <div className="relative w-72">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-zinc-400" />
          <Input
            value={rawQuery}
            onChange={(event) => {
              setRawQuery(event.target.value)
              setIsOpen(true)
            }}
            placeholder={t("common.searchPersonsPlaceholder")}
            className="h-8 pl-8 text-xs"
          />
        </div>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-1.5" onOpenAutoFocus={(event) => event.preventDefault()}>
        {isFetching ? (
          <p className="px-2 py-2 text-xs text-zinc-400">{t("common.searching")}</p>
        ) : matches && matches.length > 0 ? (
          <ul className="max-h-64 overflow-y-auto">
            {matches.map((person) => (
              <li key={person.id}>
                <button
                  type="button"
                  onClick={() => navigateToPerson(person.id)}
                  className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm text-zinc-700 hover:bg-accent-50 dark:text-zinc-200 dark:hover:bg-accent-900/40"
                >
                  <UserRound className="size-3.5 shrink-0 text-zinc-400" />
                  <span className="truncate">{person.full_name}</span>
                  {!person.human_verified ? (
                    <span className="ml-auto shrink-0 text-[10px] text-caution-600 dark:text-caution-500">{t("common.unverified")}</span>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-2 py-2 text-xs text-zinc-400">{t("common.noMatchesFor", { query: debouncedQuery })}</p>
        )}
      </PopoverContent>
    </Popover>
  )
}

export { GlobalPersonSearch }
