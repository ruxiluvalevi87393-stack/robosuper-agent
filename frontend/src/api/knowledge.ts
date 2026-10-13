import { http } from './http'

export type KbStatus = 'PENDING' | 'PROCESSING' | 'READY' | 'FAILED'

/** chunk 嵌入/入库状态：text=VECTORIZED（milvus_id 有值），table/image=STORED */
export type KbEmbedStatus = 'PENDING' | 'VECTORIZED' | 'STORED' | 'FAILED'

export interface KbDocumentOut {
  id: number
  title: string
  category: string | null
  brand: string | null
  robot_model: string | null
  file_path: string | null
  parse_result_path: string | null
  chunk_count: number
  processing_status: KbStatus
  file_url: string | null
  created_at: string
  updated_at: string
}

export interface KbChunkOut {
  id: number
  document_id: number
  chunk_index: number
  content: string
  chunk_type: string
  embed_status: KbEmbedStatus
  milvus_id: string | null
  asset_key: string | null
  asset_url: string | null
  section: string | null
  page: number | null
  created_at: string
}

export interface KbDocumentQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: string
}

/** 上传表单下拉选项：brand/robot_model 的 code 即为提交给 upload 的值 */
export interface KbBrandOption {
  code: string
  name: string
}

export interface KbRobotModelOption {
  brand: string
  code: string
  name: string
}

export interface KbUploadOptions {
  categories: string[]
  brands: KbBrandOption[]
  robot_models: KbRobotModelOption[]
}

export interface KbSearchReq {
  query: string
  top_k?: number
  document_id?: number
  brand?: string
  category?: string
  robot_model?: string
  vector_weight?: number
  searcher_weight?: number
}

export interface KbSearchAttachmentTable {
  chunk_index: number
  content: string
}

export interface KbSearchAttachmentImage {
  chunk_index: number
  content: string
  asset_url: string | null
}

export interface KbSearchHit {
  document_id: number | null
  chunk_index: number | null
  chunk_type: string
  section: string | null
  page: number | null
  brand: string | null
  category: string | null
  robot_model: string | null
  content: string
  score: number
  vector_score: number
  bm25_score: number
  tables: KbSearchAttachmentTable[]
  images: KbSearchAttachmentImage[]
}

export async function listDocuments(params: KbDocumentQuery) {
  const resp = await http.get<{ total: number; items: KbDocumentOut[] }>(
    '/knowledge/documents',
    { params },
  )
  return resp.data
}

export async function getDocument(id: number) {
  const resp = await http.get<KbDocumentOut>(`/knowledge/documents/${id}`)
  return resp.data
}

/** 上传原始文档（multipart）。上传成功仅入库元数据，需再调 import 触发解析 */
export async function uploadDocument(
  file: File,
  payload: { title?: string; category?: string; brand?: string; robot_model?: string },
) {
  const formData = new FormData()
  formData.append('file', file)
  if (payload.title) formData.append('title', payload.title)
  if (payload.category) formData.append('category', payload.category)
  if (payload.brand) formData.append('brand', payload.brand)
  if (payload.robot_model) formData.append('robot_model', payload.robot_model)
  const resp = await http.post<KbDocumentOut>('/knowledge/documents/upload', formData)
  return resp.data
}

/** 上传表单下拉数据源：分类枚举 + 真实品牌/型号（来自 PG 主数据） */
export async function getUploadOptions() {
  const resp = await http.get<KbUploadOptions>('/knowledge/upload-options')
  return resp.data
}

/** 触发 MinerU 解析 + 分块入库（后台任务，立即返回 202，前端轮询文档状态） */
export async function importDocument(id: number) {
  const resp = await http.post<{ submitted: boolean; doc_id: number }>(
    `/knowledge/documents/${id}/import`,
  )
  return resp.data
}

/** 重新导入：有已存档解析产物则复用重分块，否则全量重解析（后台任务，立即返回） */
export async function reimportDocument(id: number) {
  const resp = await http.post<{ submitted: boolean; doc_id: number }>(
    `/knowledge/documents/${id}/reimport`,
  )
  return resp.data
}

export async function listChunks(
  docId: number,
  params: { page?: number; page_size?: number; chunk_type?: string; status?: string },
) {
  const resp = await http.get<{ total: number; items: KbChunkOut[] }>(
    `/knowledge/documents/${docId}/chunks`,
    { params },
  )
  return resp.data
}

/** 编辑分块（content/section/page），保存后后端自动重新向量化 */
export async function updateChunk(
  id: number,
  payload: { content: string; section?: string | null; page?: number | null },
) {
  const resp = await http.patch<KbChunkOut>(`/knowledge/chunks/${id}`, payload)
  return resp.data
}

export async function deleteChunk(id: number) {
  await http.delete(`/knowledge/chunks/${id}`)
}

/** 单个文本分块重新向量化（FAILED/PENDING 修复入口） */
export async function embedChunk(id: number) {
  const resp = await http.post<KbChunkOut>(`/knowledge/chunks/${id}/embed`)
  return resp.data
}

/** 下载原文件：JWT 鉴权下不能走普通 <a href>，改为 blob 下载并解析文件名 */
export async function downloadDocument(id: number) {
  const resp = await http.get<Blob>(`/knowledge/documents/${id}/download`, {
    responseType: 'blob',
  })
  const disposition: string = (resp.headers['content-disposition'] as string) || ''
  let filename = `document_${id}`
  const star = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  const plain = disposition.match(/filename="?([^";]+)"?/i)
  if (star?.[1]) filename = decodeURIComponent(star[1])
  else if (plain?.[1]) filename = plain[1]
  const url = URL.createObjectURL(resp.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export async function deleteDocument(id: number) {
  await http.delete(`/knowledge/documents/${id}`)
}

export async function searchKnowledge(payload: KbSearchReq) {
  const resp = await http.post<KbSearchHit[]>('/knowledge/search', payload)
  return resp.data
}
