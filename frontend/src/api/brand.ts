import { http } from './http'

export interface BrandOut {
  id: number
  code: string
  name: string
  country: string | null
  description: string | null
  created_at: string
}

export interface BrandQuery {
  page?: number
  page_size?: number
  keyword?: string
}

export interface BrandCreatePayload {
  code: string
  name: string
  country?: string
  description?: string
}

export type BrandUpdatePayload = Partial<BrandCreatePayload>

export async function listBrands(params: BrandQuery) {
  const resp = await http.get<{ total: number; items: BrandOut[] }>('/brands', { params })
  return resp.data
}

export async function createBrand(payload: BrandCreatePayload) {
  const resp = await http.post<BrandOut>('/brands', payload)
  return resp.data
}

export async function updateBrand(id: number, payload: BrandUpdatePayload) {
  const resp = await http.put<BrandOut>(`/brands/${id}`, payload)
  return resp.data
}

export async function deleteBrand(id: number) {
  await http.delete(`/brands/${id}`)
}
