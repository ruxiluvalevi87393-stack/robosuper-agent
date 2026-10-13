import { http } from './http'
import type { UserOut } from '../store/auth'

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserOut
}

/** 登录：后端使用 OAuth2PasswordRequestForm，须以表单格式提交 */
export async function login(payload: { username: string; password: string }): Promise<TokenResponse> {
  const body = new URLSearchParams()
  body.set('username', payload.username)
  body.set('password', payload.password)
  const resp = await http.post<TokenResponse>('/auth/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return resp.data
}

export async function fetchMe(): Promise<UserOut> {
  const resp = await http.get<UserOut>('/auth/me')
  return resp.data
}

export async function changePassword(payload: {
  old_password: string
  new_password: string
}): Promise<{ message: string }> {
  const resp = await http.put('/auth/password', payload)
  return resp.data
}
