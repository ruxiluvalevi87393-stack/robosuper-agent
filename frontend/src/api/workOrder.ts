import { http } from './http'

export type WorkOrderPriority = 'low' | 'normal' | 'high' | 'urgent'
export type WorkOrderStatus = 'created' | 'assigned' | 'in_progress' | 'resolved' | 'closed'

export const WORK_ORDER_PRIORITY: Record<WorkOrderPriority, string> = {
  low: '低',
  normal: '普通',
  high: '高',
  urgent: '紧急',
}

export const WORK_ORDER_PRIORITY_COLOR: Record<WorkOrderPriority, string> = {
  low: 'default',
  normal: 'blue',
  high: 'gold',
  urgent: 'red',
}

export const WORK_ORDER_STATUS: Record<WorkOrderStatus, string> = {
  created: '已创建',
  assigned: '已指派',
  in_progress: '处理中',
  resolved: '已解决',
  closed: '已关闭',
}

export const WORK_ORDER_STATUS_COLOR: Record<WorkOrderStatus, string> = {
  created: 'default',
  assigned: 'blue',
  in_progress: 'gold',
  resolved: 'green',
  closed: 'default',
}

/** 状态机允许的下一步（与后端保持一致，供流转按钮使用） */
export const WORK_ORDER_NEXT_STATUS: Partial<Record<WorkOrderStatus, WorkOrderStatus[]>> = {
  created: ['assigned', 'in_progress'],
  assigned: ['in_progress'],
  in_progress: ['resolved'],
  resolved: ['closed'],
  closed: [],
}

export interface WorkOrderOut {
  id: number
  work_order_no: string
  robot_instance_id: number | null
  alarm_code: string | null
  title: string
  description: string | null
  priority: string
  status: string
  assignee_id: number | null
  created_by: number | null
  diagnosis_context: Record<string, unknown> | null
  assigned_at: string | null
  resolved_at: string | null
  closed_at: string | null
  created_at: string
  updated_at: string
}

export interface WorkOrderQuery {
  page?: number
  page_size?: number
  status?: string
  priority?: string
  robot_instance_id?: number
  assignee_id?: number
  alarm_code?: string
  keyword?: string
}

export interface WorkOrderCreatePayload {
  work_order_no?: string
  robot_instance_id?: number
  alarm_code?: string
  title: string
  description?: string
  priority?: WorkOrderPriority
  assignee_id?: number
}

export interface WorkOrderUpdatePayload {
  robot_instance_id?: number
  alarm_code?: string
  title?: string
  description?: string
  priority?: WorkOrderPriority
  status?: WorkOrderStatus
  assignee_id?: number
  diagnosis_context?: Record<string, unknown>
}

export async function listWorkOrders(params: WorkOrderQuery) {
  const resp = await http.get<{ total: number; items: WorkOrderOut[] }>('/work-orders', { params })
  return resp.data
}

export async function createWorkOrder(payload: WorkOrderCreatePayload) {
  const resp = await http.post<WorkOrderOut>('/work-orders', payload)
  return resp.data
}

export async function updateWorkOrder(id: number, payload: WorkOrderUpdatePayload) {
  const resp = await http.put<WorkOrderOut>(`/work-orders/${id}`, payload)
  return resp.data
}

export async function deleteWorkOrder(id: number) {
  await http.delete(`/work-orders/${id}`)
}
