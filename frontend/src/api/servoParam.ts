import { http } from './http'

export interface ServoParamOut {
  id: number
  robot_model_id: number
  param_code: string
  param_name: string
  default_value: number | string | null
  min_value: number | string | null
  max_value: number | string | null
  unit: string | null
  description: string | null
  created_at: string
}

export interface ServoParamQuery {
  page?: number
  page_size?: number
  robot_model_id?: number
  keyword?: string
}

export interface ServoParamCreatePayload {
  robot_model_id: number
  param_code: string
  param_name: string
  default_value?: number | string
  min_value?: number | string
  max_value?: number | string
  unit?: string
  description?: string
}

export type ServoParamUpdatePayload = Partial<ServoParamCreatePayload>

export async function listServoParams(params: ServoParamQuery) {
  const resp = await http.get<{ total: number; items: ServoParamOut[] }>('/servo-params', { params })
  return resp.data
}

export async function createServoParam(payload: ServoParamCreatePayload) {
  const resp = await http.post<ServoParamOut>('/servo-params', payload)
  return resp.data
}

export async function updateServoParam(id: number, payload: ServoParamUpdatePayload) {
  const resp = await http.put<ServoParamOut>(`/servo-params/${id}`, payload)
  return resp.data
}

export async function deleteServoParam(id: number) {
  await http.delete(`/servo-params/${id}`)
}
