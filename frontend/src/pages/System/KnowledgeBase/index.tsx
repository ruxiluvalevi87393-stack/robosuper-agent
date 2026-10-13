import { useEffect, useMemo, useRef, useState } from 'react'
import {
  App,
  Button,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Upload,
} from 'antd'
import type { TableColumnsType, UploadFile } from 'antd'
import {
  DeleteOutlined,
  DownloadOutlined,
  InboxOutlined,
  ReloadOutlined,
  SearchOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import PageHeader from '../../../components/PageHeader'
import FilterBar from '../../../components/FilterBar'
import Pager from '../../../components/Pager'
import {
  deleteDocument,
  downloadDocument,
  getUploadOptions,
  importDocument,
  listDocuments,
  reimportDocument,
  uploadDocument,
} from '../../../api/knowledge'
import type { KbDocumentOut, KbDocumentQuery, KbUploadOptions } from '../../../api/knowledge'
import { useCrud } from '../../../hooks/useCrud'
import { usePermission } from '../../../hooks/usePermission'
import { getApiErrorMessage } from '../../../utils/error'

const STATUS_META: Record<string, { color: string; text: string }> = {
  PENDING: { color: 'default', text: '待导入' },
  PROCESSING: { color: 'processing', text: '解析中' },
  READY: { color: 'success', text: '已就绪' },
  FAILED: { color: 'error', text: '导入失败' },
}

export default function KnowledgeBase() {
  const { message, modal } = App.useApp()
  const { hasRole } = usePermission()
  const canWrite = hasRole('admin', 'engineer')
  const navigate = useNavigate()

  const crud = useCrud<KbDocumentOut, KbDocumentQuery, never, never>(
    { list: listDocuments },
    { keyword: undefined, status: undefined },
  )

  // 上传弹窗
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [upForm] = Form.useForm()
  const [filterForm] = Form.useForm()

  // 上传表单下拉数据源：分类枚举 + 真实品牌/型号（code 即提交值），避免自由文本入库
  const [uploadOpts, setUploadOpts] = useState<KbUploadOptions | null>(null)
  const selectedBrand = Form.useWatch('brand', upForm)
  useEffect(() => {
    getUploadOptions()
      .then(setUploadOpts)
      .catch(() => message.warning('加载上传选项失败，请刷新后重试'))
  }, [])

  const modelOptions = useMemo(() => {
    const list = selectedBrand
      ? (uploadOpts?.robot_models ?? []).filter((m) => m.brand === selectedBrand)
      : (uploadOpts?.robot_models ?? [])
    return list.map((m) => ({ value: m.code, label: `${m.code} · ${m.name}` }))
  }, [uploadOpts, selectedBrand])

  /** 品牌变更时，若已选型号不属于该品牌则清空，保证提交组合通过后端校验 */
  const onBrandChange = (code: string) => {
    const model = upForm.getFieldValue('robot_model')
    if (model && code) {
      const ok = (uploadOpts?.robot_models ?? []).some((m) => m.brand === code && m.code === model)
      if (!ok) upForm.setFieldValue('robot_model', undefined)
    }
  }

  // 后台导入轮询：有 PROCESSING 行时每 5s 刷新列表，全部结束自动停止
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null)
  const fetchListRef = useRef(crud.fetchList)
  fetchListRef.current = crud.fetchList

  useEffect(() => {
    return () => {
      if (pollTimer.current) clearInterval(pollTimer.current)
      pollTimer.current = null
    }
  }, [])

  useEffect(() => {
    const hasProcessing = crud.list.some((d) => d.processing_status === 'PROCESSING')
    if (hasProcessing && !pollTimer.current) {
      pollTimer.current = setInterval(() => fetchListRef.current(), 5000)
    } else if (!hasProcessing && pollTimer.current) {
      clearInterval(pollTimer.current)
      pollTimer.current = null
    }
  }, [crud.list])

  /** 乐观置为 PROCESSING 并启动轮询 */
  const markProcessing = (rowId: number) => {
    crud.setList((prev) =>
      prev.map((d) => (d.id === rowId ? { ...d, processing_status: 'PROCESSING' } : d)),
    )
  }

  const onUploadSubmit = async () => {
    const values = upForm.getFieldsValue()
    const file = fileList[0]?.originFileObj as File | undefined
    if (!file) {
      message.warning('请先选择要上传的文件')
      return
    }
    setUploading(true)
    try {
      await uploadDocument(file, {
        title: values.title,
        category: values.category,
        brand: values.brand,
        robot_model: values.robot_model,
      })
      message.success('上传成功，请点击「导入」触发解析入库')
      setUploadOpen(false)
      upForm.resetFields()
      setFileList([])
      crud.fetchList()
    } catch (e) {
      message.error(getApiErrorMessage(e))
    } finally {
      setUploading(false)
    }
  }

  /** 首次导入：确认后提交后台任务，立即返回，不再阻塞弹窗等待解析完成 */
  const onImport = (row: KbDocumentOut) => {
    modal.confirm({
      title: '导入文档',
      content: `对「${row.title}」执行 MinerU 解析 + 分块入库？将消耗 MinerU 配额。提交后可在后台运行，页面每 5s 自动刷新状态。`,
      okText: '开始导入',
      cancelText: '取消',
      onOk: async () => {
        try {
          await importDocument(row.id)
          message.success('已提交后台导入，处理完成后自动更新')
          markProcessing(row.id)
        } catch (e) {
          message.error(getApiErrorMessage(e))
        }
      },
    })
  }

  /** 重新导入：复用已存档解析产物（省 MinerU 配额），无存档则全量重解析 */
  const onReimport = (row: KbDocumentOut) => {
    modal.confirm({
      title: '重新导入',
      content: `重新导入「${row.title}」？有已存档解析产物则复用重切分，否则全量重新解析。`,
      okText: '开始重新导入',
      cancelText: '取消',
      onOk: async () => {
        try {
          await reimportDocument(row.id)
          message.success('已提交重新导入，处理完成后自动更新')
          markProcessing(row.id)
        } catch (e) {
          message.error(getApiErrorMessage(e))
        }
      },
    })
  }

  const onDownload = async (row: KbDocumentOut) => {
    try {
      await downloadDocument(row.id)
    } catch (e) {
      message.error(getApiErrorMessage(e))
    }
  }

  const onViewChunks = (row: KbDocumentOut) => {
    navigate(`/knowledge/documents/${row.id}/chunks?title=${encodeURIComponent(row.title)}`)
  }

  const onDelete = (row: KbDocumentOut) => {
    modal.confirm({
      title: '删除文档',
      content: `删除「${row.title}」将同时移除其分块、Milvus 向量与 OSS 原文件，确定？`,
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await deleteDocument(row.id)
          message.success('删除成功')
          crud.fetchList()
        } catch (e) {
          message.error(getApiErrorMessage(e))
        }
      },
    })
  }

  const columns: TableColumnsType<KbDocumentOut> = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '标题', dataIndex: 'title', width: 240, ellipsis: true },
    {
      title: '分类',
      dataIndex: 'category',
      width: 120,
      render: (v: string | null) => v || '-',
    },
    { title: '品牌', dataIndex: 'brand', width: 100, render: (v: string | null) => v || '-' },
    {
      title: '型号',
      dataIndex: 'robot_model',
      width: 130,
      render: (v: string | null) => v || '-',
    },
    {
      title: '分块数',
      dataIndex: 'chunk_count',
      width: 90,
      render: (v: number) => v || 0,
    },
    {
      title: '状态',
      dataIndex: 'processing_status',
      width: 110,
      render: (v: string) => {
        const meta = STATUS_META[v] || { color: 'default', text: v }
        return <Tag color={meta.color}>{meta.text}</Tag>
      },
    },
    {
      title: '原文件',
      dataIndex: 'file_path',
      width: 90,
      render: (v: string | null, r: KbDocumentOut) =>
        v ? (
          <Button type="link" size="small" icon={<DownloadOutlined />} onClick={() => onDownload(r)}>
            下载
          </Button>
        ) : (
          '-'
        ),
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
            width: 240,
            fixed: 'right' as const,
            render: (_: unknown, r: KbDocumentOut) => {
              const isProcessing = r.processing_status === 'PROCESSING'
              return (
                <Space size={4} style={{ whiteSpace: 'nowrap' }}>
                  {isProcessing ? (
                    <Button size="small" disabled>
                      处理中
                    </Button>
                  ) : (
                    <>
                      {(r.processing_status === 'PENDING' || r.processing_status === 'FAILED') && (
                        <Button
                          size="small"
                          type="primary"
                          icon={<UploadOutlined />}
                          onClick={() => onImport(r)}
                        >
                          导入
                        </Button>
                      )}
                      {r.processing_status === 'READY' && (
                        <Button
                          size="small"
                          icon={<ReloadOutlined />}
                          onClick={() => onReimport(r)}
                        >
                          重新导入
                        </Button>
                      )}
                    </>
                  )}
                  {r.processing_status === 'READY' && (
                    <Button size="small" icon={<SearchOutlined />} onClick={() => onViewChunks(r)}>
                      分块
                    </Button>
                  )}
                  <Button size="small" danger icon={<DeleteOutlined />} onClick={() => onDelete(r)}>
                    删除
                  </Button>
                </Space>
              )
            },
          },
        ]
      : []),
  ]

  return (
    <div>
      <PageHeader
        title="知识库文档管理"
        actions={
          canWrite && (
            <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadOpen(true)}>
              上传文档
            </Button>
          )
        }
      />

      <FilterBar
        form={filterForm}
        onSearch={() => crud.onSearch(filterForm.getFieldsValue() as KbDocumentQuery)}
        onReset={() => {
          filterForm.resetFields()
          crud.onReset()
        }}
      >
        <Form.Item label="关键词" name="keyword">
          <Input placeholder="标题/分类/品牌" allowClear style={{ width: 220 }} />
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
        <Table<KbDocumentOut>
          rowKey="id"
          loading={crud.loading}
          dataSource={crud.list}
          columns={columns}
          pagination={false}
          scroll={{ x: 1200 }}
        />
        <Pager
          current={crud.page}
          pageSize={crud.pageSize}
          total={crud.total}
          onChange={crud.onPageChange}
        />
      </div>

      {/* 上传弹窗 */}
      <Modal
        title="上传知识库文档"
        width={520}
        open={uploadOpen}
        confirmLoading={uploading}
        okText="上传"
        cancelText="取消"
        forceRender
        onOk={onUploadSubmit}
        onCancel={() => setUploadOpen(false)}
      >
        <Form form={upForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item label="文件" required>
            <Upload.Dragger
              accept=".pdf,.doc,.docx"
              maxCount={1}
              fileList={fileList}
              beforeUpload={() => false}
              onChange={({ fileList: fl }) => setFileList(fl.slice(-1))}
              onRemove={() => setFileList([])}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
              <p className="ant-upload-hint">支持 pdf / doc / docx，单文件不超过 200MB</p>
            </Upload.Dragger>
          </Form.Item>
          <Form.Item name="title" label="标题">
            <Input placeholder="留空则使用文件名" maxLength={200} />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Select
              allowClear
              placeholder="请选择分类"
              options={(uploadOpts?.categories ?? []).map((c) => ({ value: c, label: c }))}
            />
          </Form.Item>
          <Form.Item name="brand" label="品牌">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder="请选择品牌"
              onChange={onBrandChange}
              options={(uploadOpts?.brands ?? []).map((b) => ({
                value: b.code,
                label: `${b.code} · ${b.name}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="robot_model" label="机器人型号">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder={selectedBrand ? '请选择该品牌下的型号' : '请选择型号'}
              options={modelOptions}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
