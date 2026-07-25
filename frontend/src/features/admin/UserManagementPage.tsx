import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { zodResolver } from "@hookform/resolvers/zod"
import { UserPlus, Users } from "lucide-react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { useTranslation } from "react-i18next"
import { z } from "zod"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { RANK_LABELS, type PoliceRank } from "@/lib/types/permissions"
import {
  type AdminUserRecord,
  fetchAdminUserList,
  submitNewUser,
  submitUserDeactivation,
  submitUserRoleChange,
} from "./adminApi"

const RANKS = Object.keys(RANK_LABELS) as PoliceRank[]

function CreateUserDialog() {
  const { t } = useTranslation()
  const createUserFormSchema = z.object({
    email: z.string().email(),
    password: z.string().min(8, t("userManagement.atLeast8Chars")),
    full_name: z.string().min(1, t("userManagement.required")),
    role: z.enum(RANKS as [PoliceRank, ...PoliceRank[]]),
    badge_number: z.string().optional(),
  })
  type CreateUserFormValues = z.infer<typeof createUserFormSchema>

  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = React.useState(false)
  const { register, handleSubmit, reset, formState: { errors } } = useForm<CreateUserFormValues>({
    resolver: zodResolver(createUserFormSchema),
    defaultValues: { role: "CONSTABLE" },
  })

  const createMutation = useMutation({
    mutationFn: submitNewUser,
    onSuccess: () => {
      toast.success(t("userManagement.userCreated"))
      void queryClient.invalidateQueries({ queryKey: ["admin-users"] })
      reset()
      setIsOpen(false)
    },
    onError: (error) => toast.error(extractApiErrorMessage(error)),
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button size="sm" className="gap-1.5">
          <UserPlus className="size-3.5" />
          {t("userManagement.newUser")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("userManagement.createUser")}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit((values) => createMutation.mutate(values))} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="new-user-name">{t("userManagement.fullName")}</Label>
            <Input id="new-user-name" {...register("full_name")} />
            {errors.full_name ? <p className="text-xs text-critical-500">{errors.full_name.message}</p> : null}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-user-email">{t("auth.email")}</Label>
            <Input id="new-user-email" type="email" {...register("email")} />
            {errors.email ? <p className="text-xs text-critical-500">{errors.email.message}</p> : null}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-user-password">{t("userManagement.temporaryPassword")}</Label>
            <Input id="new-user-password" type="password" {...register("password")} />
            {errors.password ? <p className="text-xs text-critical-500">{errors.password.message}</p> : null}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-user-badge">{t("userManagement.badgeNumber")}</Label>
            <Input id="new-user-badge" {...register("badge_number")} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? t("userManagement.creating") : t("userManagement.createUser")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function UserRow({ user }: { user: AdminUserRecord }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const roleChangeMutation = useMutation({
    mutationFn: (role: PoliceRank) => submitUserRoleChange(user.id, role),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
    onError: (error) => toast.error(extractApiErrorMessage(error)),
  })

  const deactivateMutation = useMutation({
    mutationFn: () => submitUserDeactivation(user.id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
    onError: (error) => toast.error(extractApiErrorMessage(error)),
  })

  return (
    <TableRow>
      <TableCell>
        <p className="text-zinc-800 dark:text-zinc-100">{user.full_name}</p>
        <p className="text-xs text-zinc-400">{user.email}</p>
      </TableCell>
      <TableCell>
        <Select value={user.role} onValueChange={(value) => roleChangeMutation.mutate(value as PoliceRank)}>
          <SelectTrigger className="h-7 w-40 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {RANKS.map((rank) => (
              <SelectItem key={rank} value={rank}>
                {RANK_LABELS[rank]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TableCell>
      <TableCell>{user.is_active ? <Badge variant="affirm">{t("userManagement.active")}</Badge> : <Badge variant="critical">{t("userManagement.deactivated")}</Badge>}</TableCell>
      <TableCell className="text-right">
        {user.is_active ? (
          <Button
            size="sm"
            variant="outline"
            className="text-critical-600"
            onClick={() => deactivateMutation.mutate()}
            disabled={deactivateMutation.isPending}
          >
            {t("userManagement.deactivate")}
          </Button>
        ) : null}
      </TableCell>
    </TableRow>
  )
}

function UserManagementPage() {
  const { t } = useTranslation()
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["admin-users"],
    queryFn: fetchAdminUserList,
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t("nav.userManagement")}</h1>
        <CreateUserDialog />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("userManagement.platformUsers")}</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <LoadingSkeleton variant="table" rows={6} />
          ) : isError ? (
            <ErrorState message={extractApiErrorMessage(error)} onRetry={() => void refetch()} />
          ) : !data || data.length === 0 ? (
            <EmptyState icon={Users} title={t("userManagement.noUsersFound")} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("userManagement.user")}</TableHead>
                  <TableHead>{t("userManagement.rank")}</TableHead>
                  <TableHead>{t("userManagement.status")}</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((user) => (
                  <UserRow key={user.id} user={user} />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export { UserManagementPage }
