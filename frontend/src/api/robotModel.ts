import { http } from './http'

export interface RobotModelOut {
  id: number
  brand_id: number
  controller_id: number | null
  code: string
  name: string
  payload_kg: number | string | null
  reach_mm: number | string | null
  axes: number | null
  description: string | null
  created_at: string
}

export interface RobotModelQuery {
  page?: number
  page_size?: number
  brand_id?: number
  controller_id?: number
  keyword?: string
}

export interface RobotModelCreatePayload {
  brand_id: number
  controller_id?: number
  code: string
  name: string
  payload_kg?: number | string
  reach_mm?: number | string
  axes?: number
  description?: string
}

export type RobotModelUpdatePayload = Partial<RobotModelCreatePayload>

export async function listRobotModels(params: RobotModelQuery) {
  const resp = await http.get<{ total: number; items: RobotModelOut[] }>('/robot-models', { params })
  return resp.data
}

export async function createRobotModel(payload: RobotModelCreatePayload) {
  const resp = await http.post<RobotModelOut>('/robot-models', payload)
  return resp.data
}

export async function updateRobotModel(id: number, payload: RobotModelUpdatePayload) {
  const resp = await http.put<RobotModelOut>(`/robot-models/${id}`, payload)
  return resp.data
}

export async function deleteRobotModel(id: number) {
  await http.delete(`/robot-models/${id}`)
}
