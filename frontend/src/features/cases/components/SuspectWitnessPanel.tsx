import { Link } from "react-router-dom"

import { EmptyState } from "@/components/data-states/EmptyState"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { CaseWorkspaceSnapshot, WorkspacePerson } from "@/lib/types/api"

const ROLE_ORDER = ["Accused", "Victim", "Witness", "Complainant"]

function PersonRow({ person }: { person: WorkspacePerson }) {
  return (
    <li className="flex items-center justify-between py-2">
      <Link
        to={`/persons/${person.person_id}`}
        className="text-sm text-zinc-800 hover:text-accent-700 dark:text-zinc-100 dark:hover:text-accent-300"
      >
        {person.name}
      </Link>
      <div className="flex items-center gap-1.5">
        {person.arrested ? <Badge variant="critical">arrested</Badge> : null}
        {person.bail_granted ? <Badge variant="affirm">bail granted</Badge> : null}
        {!person.human_verified ? <Badge variant="neutral">unverified identity</Badge> : null}
      </div>
    </li>
  )
}

function SuspectWitnessPanel({ people }: { people: CaseWorkspaceSnapshot["people"] }) {
  const rolesWithPeople = ROLE_ORDER.filter((role) => (people[role]?.length ?? 0) > 0)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Suspects &amp; Witnesses</CardTitle>
      </CardHeader>
      <CardContent>
        {rolesWithPeople.length === 0 ? (
          <EmptyState title="No people linked to this case yet" />
        ) : (
          <div className="space-y-4">
            {rolesWithPeople.map((role) => (
              <div key={role}>
                <p className="section-label mb-1">{role}</p>
                <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
                  {people[role].map((person) => (
                    <PersonRow key={person.person_id} person={person} />
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
