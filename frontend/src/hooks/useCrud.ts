import { useCallback, useEffect, useRef, useState } from 'react'
import { App } from 'antd'
import { getApiErrorMessage } from '../utils/error'

export interface CrudApi<T, Q, C, U> {
  list: (params: Q & { page?: number; page_size?: number }) => Promise<{ total: number; items: T[] }>
  create?: (payload: C) => Promise<T>
  update?: (id: number, payload: U) => Promise<T>
  remove?: (id: number) => Promise<void>
}

/** 通用列表/搜索/分页 + 弹窗新增/编辑/删除 的状态管理 */
export function useCrud<T, Q, C, U>(api: CrudApi<T, Q, C, U>, defaultFilters: Q) {
  const { message } = App.useApp()

  const [list, setList] = useState<T[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [filters, setFilters] = useState<Q>(defaultFilters)

  const [modalOpen, setModalOpen] = useState(false)
  const [isEdit, setIsEdit] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // api 由页面内联传入（每次渲染都是新对象），用 ref 持有最新值，
  // 避免其身份变化导致 fetchList 重建、触发 useEffect 无限重查
  const apiRef = useRef(api)
  apiRef.current = api

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiRef.current.list({ ...filters, page, page_size: pageSize })
      setList(data.items)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }, [filters, page, pageSize])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const onSearch = (f: Q) => {
    setFilters(f)
    setPage(1)
  }

  const onReset = () => {
    setFilters({ ...defaultFilters })
    setPage(1)
  }

  const onPageChange = (p: number, ps: number) => {
    setPage(p)
    setPageSize(ps)
  }

  const openCreate = () => {
    setIsEdit(false)
    setEditingId(null)
    setModalOpen(true)
  }

  const openEdit = (row: T & { id: number }) => {
    setIsEdit(true)
    setEditingId(row.id)
    setModalOpen(true)
  }

  /** 保存新增/编辑；payload 由页面在调用前组装好 */
  const save = async (payload: C | U) => {
    setSubmitting(true)
    try {
      if (isEdit) {
        if (!api.update) return false
        await api.update(editingId!, payload as U)
        message.success('更新成功')
      } else {
        if (!api.create) return false
        await api.create(payload as C)
        message.success('创建成功')
      }
      setModalOpen(false)
      await fetchList()
      return true
    } catch (e) {
      message.error(getApiErrorMessage(e))
      return false
    } finally {
      setSubmitting(false)
    }
  }

  /** 删除确认后调用（错误由页面或此处提示） */
  const remove = async (id: number) => {
    if (!api.remove) return
    try {
      await api.remove(id)
      message.success('删除成功')
      await fetchList()
    } catch (e) {
      message.error(getApiErrorMessage(e))
    }
  }

  return {
    list,
    setList,
    total,
    loading,
    page,
    pageSize,
    filters,
    modalOpen,
    isEdit,
    editingId,
    submitting,
    setModalOpen,
    fetchList,
    onSearch,
    onReset,
    onPageChange,
    openCreate,
    openEdit,
    save,
    remove,
  }
}
