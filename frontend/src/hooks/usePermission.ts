import { useAuthStore } from '../store/auth'

/** 基于当前用户角色的权限判断 */
export function usePermission() {
  const role = useAuthStore((s) => s.user?.role)
  return {
    role,
    hasRole: (...roles: string[]) => !!role && roles.includes(role),
  }
}
