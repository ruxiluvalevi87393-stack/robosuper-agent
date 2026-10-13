import { http } from './http'

export interface PartInventoryOut {
  id: number
  part_no: string
  name: string
  brand_id: number | null
  category: string | null
  price: number | string | null
  lead_time_days: number | null
  compatible_brands: string[] | null
  quantity: number
  warehouse: string
  location: string | null
  safety_stock: number
  updated_at: string
}

export interface PartInventoryQuery {
  page?: number
  page_size?: number
  keyword?: string
  brand_id?: number
  category?: string
  warehouse?: string
  low_stock?: boolean
}

export interface PartInventoryCreatePayload {
  part_no: string
  name: string
  brand_id?: number
  category?: string
  price?: number | string
  lead_time_days?: number
  compatible_brands?: string[]
  quantity?: number
  warehouse: string
  location?: string
  safety_stock?: number
}

export type PartInventoryUpdatePayload = Partial<PartInventoryCreatePayload>

export async function listPartInventory(params: PartInventoryQuery) {
  const resp = await http.get<{ total: number; items: PartInventoryOut[] }>('/part-inventory', {
    params,
  })
  return resp.data
}

export async function createPartInventory(payload: PartInventoryCreatePayload) {
  const resp = await http.post<PartInventoryOut>('/part-inventory', payload)
  return resp.data
}

export async function updatePartInventory(id: number, payload: PartInventoryUpdatePayload) {
  const resp = await http.put<PartInventoryOut>(`/part-inventory/${id}`, payload)
  return resp.data
}

export async function deletePartInventory(id: number) {
  await http.delete(`/part-inventory/${id}`)
}
