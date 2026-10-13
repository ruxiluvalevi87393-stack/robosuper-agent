import { http } from './http'

export interface MaintenanceLogOut {
  id: number
  work_order_no: string | null
  robot_instance_id: number | null
  alarm_code: string | null
  engineer_id: number | null
  fault_description: string | null
  root_cause: string | null
  sop_used: string | null
  parts_used: Record<string, unknown> | null
  downtime_minutes: number | null
  occurred_at: string
  created_at: string
}

export interface MaintenanceLogQuery {
  page?: number
  page_size?: number
  robot_instance_id?: number
  alarm_code?: string
  engineer_id?: number
  work_order_no?: string
}

export interface MaintenanceLogCreatePayload {
  work_order_no?: string
  robot_instance_id?: number
  alarm_code?: string
  engineer_id?: number
  fault_description?: string
  root_cause?: string
  sop_used?: string
  parts_used?: Record<string, number>
  downtime_minutes?: number
  occurred_at?: string
}

export async function listMaintenanceLogs(params: MaintenanceLogQuery) {
  const resp = await http.get<{ total: number; items: MaintenanceLogOut[] }>('/maintenance-logs', {
    params,
  })
  return resp.data
}

export async function createMaintenanceLog(payload: MaintenanceLogCreatePayload) {
  const resp = await http.post<MaintenanceLogOut>('/maintenance-logs', payload)
  return resp.data
}
