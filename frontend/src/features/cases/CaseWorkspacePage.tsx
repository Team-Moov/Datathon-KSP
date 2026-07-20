import { useParams } from "react-router-dom"

import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { useAuth } from "@/features/auth/AuthProvider"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { AiBriefPanel } from "./components/AiBriefPanel"
import { CaseHeaderCard } from "./components/CaseHeaderCard"
import { CaseNotesPanel } from "./components/CaseNotesPanel"
import { CaseTimeline } from "./components/CaseTimeline"
import { EvidenceList } from "./components/EvidenceList"
import { ReportExportDialog } from "./components/ReportExportDialog"
import { SuspectWitnessPanel } from "./components/SuspectWitnessPanel"
import { useCaseWorkspace } from "./useCaseWorkspace"

function CaseWorkspacePage() {
  const { caseId } = useParams<{ caseId: string }>()
  const { currentUser } = useAuth()
  const { workspaceSnapshot, isLoading, isError, error, refetch } = useCaseWorkspace(caseId ?? "")

  if (!caseId) return <ErrorState message="No case selected." />

  if (isLoading) {
    return (
      <div className="space-y-4">
        <LoadingSkeleton variant="card" rows={1} />
        <LoadingSkeleton variant="card" rows={3} />
      </div>
    )
  }

  if (isError || !workspaceSnapshot) {
    return <ErrorState message={extractApiErrorMessage(error, "Couldn't load this case.")} onRetry={() => void refetch()} />
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <CaseHeaderCard caseId={caseId} caseData={workspaceSnapshot.case} />
        </div>
        <ReportExportDialog caseId={caseId} crimeNo={workspaceSnapshot.case.crime_no} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <CaseTimeline timeline={workspaceSnapshot.timeline} />
          <EvidenceList documents={workspaceSnapshot.documents} />
          <SuspectWitnessPanel people={workspaceSnapshot.people} />
        </div>
        <div className="space-y-4">
          <AiBriefPanel caseId={caseId} />
          <CaseNotesPanel caseId={caseId} notes={workspaceSnapshot.notes} currentUserId={currentUser?.id} />
        </div>
      </div>
    </div>
  )
}

export { CaseWorkspacePage }
