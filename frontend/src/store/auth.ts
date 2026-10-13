import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface UserOut {
  id: number
  username: string
  role: string
  name: string | null
  email: string | null
  phone: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

interface AuthState {
  token: string | null
  user: UserOut | null
  setAuth: (token: string, user: UserOut) => void
  setUser: (user: UserOut) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setAuth: (token, user) => set({ token, user }),
      setUser: (user) => set({ user }),
      logout: () => set({ token: null, user: null }),
    }),
    { name: 'robosuper-auth' },
  ),
)
