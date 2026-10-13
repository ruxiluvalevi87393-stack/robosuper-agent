import { http } from './http'
import type { UserOut } from '../store/auth'

export interface UserQuery {
  page?: number
  page_size?: number
  keyword?: string
  role?: string
  is_active?: boolean
}

export interface UserListResp {
  total: number
  items: UserOut[]
}

export interface UserCreatePayload {
  username: string
  password: string
  role: string
  name?: string
  email?: string
  phone?: string
  is_active?: boolean
}

export interface UserUpdatePayload {
  role?: string
  name?: string
  email?: string
  phone?: string
  is_active?: boolean
  password?: string
}

export async function listUsers(params: UserQuery): Promise<UserListResp> {
  const resp = await http.get<UserListResp>('/users', { params })
  return resp.data
}

export async function createUser(payload: UserCreatePayload): Promise<UserOut> {
  const resp = await http.post<UserOut>('/users', payload)
  return resp.data
}

export async function updateUser(id: number, payload: UserUpdatePayload): Promise<UserOut> {
  const resp = await http.put<UserOut>(`/users/${id}`, payload)
  return resp.data
}

export async function deleteUser(id: number): Promise<void> {
  await http.delete(`/users/${id}`)
}
