import { Link } from "react-router-dom"
import { useTranslation } from "react-i18next"
import type { TFunction } from "i18next"

import { EmptyState } from "@/components/data-states/EmptyState"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { CaseWorkspaceSnapshot, WorkspacePerson } from "@/lib/types/api"

const ROLE_ORDER = ["Accused", "Victim", "Witness", "Complainant"]

// Maps the backend's fixed English role strings to translation keys — these
// come from PersonCaseRole data, not free text, so the mapping is exhaustive.
const ROLE_KEYS: Record<string, string> = {
  Accused: "suspectWitness.roles.accused",
  Victim: "suspectWitness.roles.victim",
  Witness: "suspectWitness.roles.witness",
  Complainant: "suspectWitness.roles.complainant",
}

function PersonRow({ person, t }: { person: WorkspacePerson; t: TFunction }) {
  return (
    <li className="flex items-center justify-between py-2">
      <Link
        to={`/persons/${person.person_id}`}
        className="text-sm text-zinc-800 hover:text-accent-700 dark:text-zinc-100 dark:hover:text-accent-300"
      >
        {person.name}
      </Link>
      <div className="flex items-center gap-1.5">
        {person.arrested ? <Badge variant="critical">{t("suspectWitness.arrested")}</Badge> : null}
        {person.bail_granted ? <Badge variant="affirm">{t("suspectWitness.bailGranted")}</Badge> : null}
        {!person.human_verified ? <Badge variant="neutral">{t("suspectWitness.unverifiedIdentity")}</Badge> : null}
      </div>
    </li>
  )
}

function SuspectWitnessPanel({ people }: { people: CaseWorkspaceSnapshot["people"] }) {
  const { t } = useTranslation()
  const rolesWithPeople = ROLE_ORDER.filter((role) => (people[role]?.length ?? 0) > 0)

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("suspectWitness.suspectsAndWitnesses")}</CardTitle>
      </CardHeader>
      <CardContent>
        {rolesWithPeople.length === 0 ? (
          <EmptyState title={t("suspectWitness.noPeopleYet")} />
        ) : (
          <div className="space-y-4">
            {rolesWithPeople.map((role) => (
              <div key={role}>
                <p className="section-label mb-1">{ROLE_KEYS[role] ? t(ROLE_KEYS[role]) : role}</p>
                <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
                  {people[role].map((person) => (
                    <PersonRow key={person.person_id} person={person} t={t} />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export { SuspectWitnessPanel }
