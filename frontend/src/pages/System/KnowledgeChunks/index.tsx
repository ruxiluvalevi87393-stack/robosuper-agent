import { useEffect, useState } from 'react'
import { App, Button, Form, Image, Input, InputNumber, Modal, Select, Space, Table, Tag } from 'antd'
import type { TableColumnsType } from 'antd'
import { ArrowLeftOutlined, DeleteOutlined, EditOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import dayjs from 'dayjs'
import PageHeader from '../../../components/PageHeader'
import Pager from '../../../components/Pager'
import FilterBar from '../../../components/FilterBar'
import MarkdownTable from '../../../components/MarkdownTable'
import { deleteChunk, embedChunk, listChunks, updateChunk } from '../../../api/knowledge'
import type { KbChunkOut, KbEmbedStatus } from '../../../api/knowledge'
import { usePermission } from '../../../hooks/usePermission'
import { getApiErrorMessage } from '../../../utils/error'

const CHUNK_CONTENT_STYLE: React.CSSProperties = {
  display: '-webkit-box',
  WebkitLineClamp: 3,
  WebkitBoxOrient: 'vertical',
  overflow: 'hidden',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-all',
  fontSize: 13,
}

const CHUNK_TYPE_META: Record<string, { color: string; text: string }> = {
  text: { color: 'default', text: '文本' },
  table: { color: 'blue', text: '表格' },
  image: { color: 'purple', text: '图片' },
}

const STATUS_META: Record<KbEmbedStatus, { color: string; text: string }> = {
  PENDING: { color: 'default', text: '待处理' },
  VECTORIZED: { color: 'success', text: '已向量化' },
  STORED: { color: 'blue', text: '已入库' },
  FAILED: { color: 'error', text: '失败' },
}

/** 分块内容渲染：text 截断预览；table 渲染 antd Table；image 渲染缩略图 */
function ChunkContent({ row }: { row: KbChunkOut }) {
  if (row.chunk_type === 'table') {
    return <MarkdownTable md={row.content} />
  }
  if (row.chunk_type === 'image') {
    return row.asset_url ? (
      <Image width={140} src={row.asset_url} style={{ borderRadius: 4 }} />
    ) : (
      <span style={{ color: 'rgba(0,0,0,.45)' }}>图片（未上传资产）</span>
    )
  }
  return (
    <div style={CHUNK_CONTENT_STYLE} title={row.content}>
      {row.content}
    </div>
  )
}

/** 分块管理独立页：进入来源为文档列表「分块」按钮，route: /knowledge/documents/:docId/chunks */
export default function KnowledgeChunks() {
  const { docId } = useParams<{ docId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { message, modal } = App.useApp()
  const { hasRole } = usePermission()
  const canWrite = hasRole('admin', 'engineer')

  const id = Number(docId)
  const docTitle = searchParams.get('title') || ''

  const [list, setList] = useState<KbChunkOut[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [filters, setFilters] = useState<{ chunk_type?: string; status?: string }>({})
  const [filterForm] = Form.useForm()

  const [editOpen, setEditOpen] = useState(false)
  const [editing, setEditing] = useState<KbChunkOut | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [retryingId, setRetryingId] = useState<number | null>(null)
  const [editForm] = Form.useForm()

  const fetchList = async (p = page, ps = pageSize, f = filters) => {
    if (!id) return
    setLoading(true)
    try {
      const data = await listChunks(id, {
        page: p,
        page_size: ps,
        chunk_type: f.chunk_type,
        status: f.status,
      })
      setList(data.items)
      setTotal(data.total)
    } catch (e) {
      message.error(getApiErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const openEdit = (row: KbChunkOut) => {
    setEditing(row)
    editForm.setFieldsValue({ content: row.content, section: row.section, page: row.page })
    setEditOpen(true)
  }

  const onEditSubmit = async () => {
    if (!editing) return
    const values = editForm.getFieldsValue()
    if (!values.content?.trim()) {
      message.warning('分块内容不能为空')
      return
    }
    setSubmitting(true)
    try {
      await updateChunk(editing.id, {
        content: values.content,
        section: values.section || null,
        page: values.page != null ? values.page : null,
      })
      message.success(editing.chunk_type === 'text' ? '已保存，正在重新向量化' : '已保存')
      setEditOpen(false)
      fetchList()
    } catch (e) {
      message.error(getApiErrorMessage(e))
    } finally {
      setSubmitting(false)
    }
  }

  const onRetryEmbed = async (row: KbChunkOut) => {
    setRetryingId(row.id)
    try {
      await embedChunk(row.id)
      message.success('已重新向量化')
      fetchList()
    } catch (e) {
      message.error(getApiErrorMessage(e))
    } finally {
      setRetryingId(null)
    }
  }

  const onDelete = (row: KbChunkOut) => {
    modal.confirm({
      title: '删除分块',
      content: `确定删除分块 #${row.chunk_index}？将同步从 Milvus 删除对应向量。`,
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await deleteChunk(row.id)
          message.success('删除成功')
          if (list.length === 1 && page > 1) {
            setPage(page - 1)
          }
          fetchList()
        } catch (e) {
          message.error(getApiErrorMessage(e))
        }
      },
    })
  }

  const columns: TableColumnsType<KbChunkOut> = [
    { title: '序号', dataIndex: 'chunk_index', width: 70 },
    {
      title: '类型',
      dataIndex: 'chunk_type',
      width: 80,
      render: (v: string) => {
        const meta = CHUNK_TYPE_META[v] || { color: 'default', text: v }
        return <Tag color={meta.color}>{meta.text}</Tag>
      },
    },
    {
      title: '状态',
      dataIndex: 'embed_status',
      width: 100,
      render: (v: KbEmbedStatus) => {
        const meta = STATUS_META[v] || { color: 'default', text: v }
        return <Tag color={meta.color}>{meta.text}</Tag>
      },
    },
    {
      title: '章节',
      dataIndex: 'section',
      width: 220,
      ellipsis: true,
      render: (v: string | null) => v || '-',
    },
    { title: '页', dataIndex: 'page', width: 70, render: (v: number | null) => v ?? '-' },
    {
      title: '内容',
      dataIndex: 'content',
      render: (v: string, r: KbChunkOut) => <ChunkContent row={r} />,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 160,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    ...(canWrite
      ? [
          {
            title: '操作',
            key: 'op',
            width: 180,
            fixed: 'right' as const,
            render: (_: unknown, r: KbChunkOut) => (
              <Space size={4}>
                {r.chunk_type === 'text' && r.embed_status === 'FAILED' && (
                  <Button
                    size="small"
                    icon={<ReloadOutlined />}
                    loading={retryingId === r.id}
                    onClick={() => onRetryEmbed(r)}
                  >
                    重试
                  </Button>
                )}
                <Button size="small" type="primary" icon={<EditOutlined />} onClick={() => openEdit(r)}>
                  编辑
                </Button>
                <Button size="small" danger icon={<DeleteOutlined />} onClick={() => onDelete(r)}>
                  删除
                </Button>
              </Space>
            ),
          },
        ]
      : []),
  ]

  return (
    <div>
      <PageHeader
        title={docTitle ? `分块管理 · ${docTitle}` : `分块管理 · #${id}`}
        actions={
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/knowledge/documents')}>
            返回
          </Button>
        }
      />

      <FilterBar
        form={filterForm}
        onSearch={() => {
          const f = filterForm.getFieldsValue()
          setFilters({ chunk_type: f.chunk_type, status: f.status })
          setPage(1)
          fetchList(1, pageSize, { chunk_type: f.chunk_type, status: f.status })
        }}
        onReset={() => {
          filterForm.resetFields()
          setFilters({})
          setPage(1)
          fetchList(1, pageSize, {})
        }}
      >
        <Form.Item label="类型" name="chunk_type">
          <Select
            allowClear
            placeholder="全部类型"
            style={{ width: 120 }}
            options={Object.entries(CHUNK_TYPE_META).map(([k, v]) => ({ value: k, label: v.text }))}
          />
        </Form.Item>
        <Form.Item label="状态" name="status">
          <Select
            allowClear
            placeholder="全部状态"
            style={{ width: 140 }}
            options={Object.entries(STATUS_META).map(([k, v]) => ({ value: k, label: v.text }))}
          />
        </Form.Item>
      </FilterBar>

      <div className="table-card">
        <Table<KbChunkOut>
          rowKey="id"
          size="small"
          loading={loading}
          dataSource={list}
          columns={columns}
          pagination={false}
          scroll={{ x: 1100 }}
        />
        <Pager
          current={page}
          pageSize={pageSize}
          total={total}
          onChange={(p, ps) => {
            setPage(p)
            setPageSize(ps)
            fetchList(p, ps)
          }}
        />
      </div>

      <Modal
        title="编辑分块"
        width={720}
        open={editOpen}
        confirmLoading={submitting}
        okText="保存"
        cancelText="取消"
        onOk={onEditSubmit}
        onCancel={() => setEditOpen(false)}
      >
        <Form form={editForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item label="章节路径" name="section">
            <Input placeholder="如 一、适用范围" maxLength={100} />
          </Form.Item>
          <Form.Item label="页码" name="page">
            <InputNumber min={0} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item label="分块内容" name="content" required>
            <Input.TextArea rows={10} placeholder="分块正文" />
          </Form.Item>
          <div style={{ fontSize: 12, color: 'rgba(0,0,0,.45)' }}>
            {editing?.chunk_type === 'text'
              ? '提交后将自动重新向量化（Milvus）'
              : '表格/图片分块不入向量库，保存后仅更新数据库记录'}
          </div>
        </Form>
      </Modal>
    </div>
  )
}
