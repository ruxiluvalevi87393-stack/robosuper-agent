import { http } from './http'

export type RobotInstanceStatus = 'running' | 'idle' | 'alarm' | 'maintenance' | 'offline'

export const ROBOT_INSTANCE_STATUS: Record<RobotInstanceStatus, string> = {
  running: '运行中',
  idle: '待机',
  alarm: '报警',
  maintenance: '维护中',
  offline: '离线',
}

export const ROBOT_INSTANCE_STATUS_COLOR: Record<RobotInstanceStatus, string> = {
  running: 'green',
  idle: 'default',
  alarm: 'red',
  maintenance: 'gold',
  offline: 'default',
}

export interface RobotInstanceOut {
  id: number
  robot_model_id: number
  asset_no: string
  name: string | null
  serial_no: string | null
  line_id: string | null
  install_date: string | null
  status: RobotInstanceStatus
  note: string | null
  created_at: string
}

export interface RobotInstanceQuery {
  page?: number
  page_size?: number
  robot_model_id?: number
  status?: string
  line_id?: string
  keyword?: string
}

export interface RobotInstanceCreatePayload {
  robot_model_id: number
  asset_no: string
  name?: string
  serial_no?: string
  line_id?: string
  install_date?: string
  status?: RobotInstanceStatus
  note?: string
}

export type RobotInstanceUpdatePayload = Partial<RobotInstanceCreatePayload>

export async function listRobotInstances(params: RobotInstanceQuery) {
  const resp = await http.get<{ total: number; items: RobotInstanceOut[] }>('/robot-instances', {
    params,
  })
  return resp.data
}

export async function createRobotInstance(payload: RobotInstanceCreatePayload) {
  const resp = await http.post<RobotInstanceOut>('/robot-instances', payload)
  return resp.data
}

export async function updateRobotInstance(id: number, payload: RobotInstanceUpdatePayload) {
  const resp = await http.put<RobotInstanceOut>(`/robot-instances/${id}`, payload)
  return resp.data
}

export async function deleteRobotInstance(id: number) {
  await http.delete(`/robot-instances/${id}`)
}
