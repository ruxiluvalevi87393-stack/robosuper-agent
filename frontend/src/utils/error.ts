/** 从 axios 错误中提取可读错误消息（兼容 FastAPI 的 422 detail 数组 / 400 字符串） */
export function getApiErrorMessage(e: any, fallback = '操作失败'): string {
  const data = e?.response?.data
  if (!data) return e?.message || fallback
  const detail = data.detail ?? data.message
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0]
    if (first?.msg) return typeof first.msg === 'string' ? first.msg : JSON.stringify(first.msg)
  }
  return fallback
}
