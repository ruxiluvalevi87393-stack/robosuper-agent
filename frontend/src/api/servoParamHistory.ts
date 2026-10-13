import { http } from './http'

export interface ServoParamHistoryOut {
  id: number
  robot_instance_id: number | null
  robot_model_id: number | null
  param_code: string
  old_value: number | string | null
  new_value: number | string | null
  changed_by: number | null
  reason: string | null
  changed_at: string
}

export interface ServoParamHistoryQuery {
  page?: number
  page_size?: number
  robot_instance_id?: number
  robot_model_id?: number
  param_code?: string
  changed_by?: number
}

export interface ServoParamHistoryCreatePayload {
  robot_instance_id?: number
  robot_model_id?: number
  param_code: string
  old_value?: number | string
  new_value?: number | string
  changed_by?: number
  reason?: string
}

export async function listServoParamHistories(params: ServoParamHistoryQuery) {
  const resp = await http.get<{ total: number; items: ServoParamHistoryOut[] }>(
    '/servo-param-histories',
    { params },
  )
  return resp.data
}

export async function createServoParamHistory(payload: ServoParamHistoryCreatePayload) {
  const resp = await http.post<ServoParamHistoryOut>('/servo-param-histories', payload)
  return resp.data
}
