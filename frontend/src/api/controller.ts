import { http } from './http'

export interface ControllerOut {
  id: number
  brand_id: number
  code: string
  name: string
  series: string | null
  description: string | null
  created_at: string
}

export interface ControllerQuery {
  page?: number
  page_size?: number
  brand_id?: number
  keyword?: string
}

export interface ControllerCreatePayload {
  brand_id: number
  code: string
  name: string
  series?: string
  description?: string
}

export type ControllerUpdatePayload = Partial<ControllerCreatePayload>

export async function listControllers(params: ControllerQuery) {
  const resp = await http.get<{ total: number; items: ControllerOut[] }>('/controllers', { params })
  return resp.data
}

export async function createController(payload: ControllerCreatePayload) {
  const resp = await http.post<ControllerOut>('/controllers', payload)
  return resp.data
}

export async function updateController(id: number, payload: ControllerUpdatePayload) {
  const resp = await http.put<ControllerOut>(`/controllers/${id}`, payload)
  return resp.data
}

export async function deleteController(id: number) {
  await http.delete(`/controllers/${id}`)
}
