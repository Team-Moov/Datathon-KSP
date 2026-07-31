interface ExtractedEntity {
  text: string
  type: string
}

const TYPE_COLORS: Record<string, string> = {
  PERSON: "bg-accent-500/10 text-accent-600 dark:text-accent-400",
  PER: "bg-accent-500/10 text-accent-600 dark:text-accent-400",
  LOCATION: "bg-affirm-500/10 text-affirm-600 dark:text-affirm-400",
  LOC: "bg-affirm-500/10 text-affirm-600 dark:text-affirm-400",
  ORGANIZATION: "bg-caution-500/10 text-caution-600 dark:text-caution-400",
  ORG: "bg-caution-500/10 text-caution-600 dark:text-caution-400",
}
const DEFAULT_COLOR = "bg-zinc-500/10 text-zinc-600 dark:text-zinc-400"

/** Entities grouped by type as tag chips — NER output (§2.4 step 3), local
 * spaCy or Zia depending on NLP_PROVIDER, normalized to the same {text, type} shape either way. */
function EntitiesList({ entities }: { entities: ExtractedEntity[] }) {
  if (entities.length === 0) {
    return <p className="px-1 text-xs text-zinc-400">No entities extracted.</p>
  }

  const groups = entities.reduce<Record<string, string[]>>((acc, entity) => {
    acc[entity.type] ??= []
    acc[entity.type].push(entity.text)
    return acc
  }, {})

  return (
    <div className="space-y-2">
      {Object.entries(groups).map(([type, values]) => (
        <div key={type}>
          <p className="mb-1 text-[10px] uppercase tracking-wide text-zinc-400">{type}</p>
          <div className="flex flex-wrap gap-1.5">
            {values.map((value, index) => (
              <span
                key={`${value}-${index}`}
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${TYPE_COLORS[type.toUpperCase()] ?? DEFAULT_COLOR}`}
              >
                {value}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export { EntitiesList }
export type { ExtractedEntity }
