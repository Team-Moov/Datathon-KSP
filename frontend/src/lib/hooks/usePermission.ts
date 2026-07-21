import { useAuth } from "@/features/auth/AuthProvider"
import { type Permission, roleHasAnyPermission, roleHasPermission } from "@/lib/types/permissions"

/**
 * Mirrors the backend's require_permission dependency for UI gating (nav items,
 * route guards, conditionally rendered actions). The API is the actual
 * enforcement boundary — this only prevents showing controls a request would
 * get a 403 from anyway.
 */
export function usePermission() {
  const { currentUser } = useAuth()

  return {
    has: (permission: Permission) => roleHasPermission(currentUser?.role, permission),
    hasAny: (permissions: Permission[]) => roleHasAnyPermission(currentUser?.role, permissions),
  }
}
