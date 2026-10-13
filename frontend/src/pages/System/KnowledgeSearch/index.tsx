import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { App, Button, Col, Empty, Form, Image, Input, InputNumber, List, Row, Select, Tag } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import PageHeader from '../../../components/PageHeader'
import MarkdownTable from '../../../components/MarkdownTable'
import { listDocuments, searchKnowledge } from '../../../api/knowledge'
import type { KbDocumentOut, KbSearchHit } from '../../../api/knowledge'
import { getApiErrorMessage } from '../../../utils/error'

const PH_RE = /\[(table|image)_(\d+)\]/g

/** 把命中 content 里的 [table_XX]/[image_XX] 占位符替换成实际渲染的表格/图片 */
function renderContentWithAttachments(content: string, hit: KbSearchHit): ReactNode[] {
  const tables = new Map(hit.tables.map((t) => [t.chunk_index, t.content]))
  const images = new Map(hit.images.map((im) => [im.chunk_index, im]))
  const parts: ReactNode[] = []
  let last = 0
  let k = 0
  let m: RegExpExecArray | null
  PH_RE.lastIndex = 0
  while ((m = PH_RE.exec(content)) !== null) {
    if (m.index > last) {
      parts.push(<span key={k++}>{content.slice(last, m.index)}</span>)
    }
    const type = m[1]
    const idx = Number(m[2])
    if (type === 'table') {
      const md = tables.get(idx)
      parts.push(<MarkdownTable key={k++} md={md ?? ''} />)
    } else {
      const assetUrl = images.get(idx)?.asset_url
      parts.push(
        assetUrl ? (
          <Image key={k++} src={assetUrl} width={320} style={{ borderRadius: 4 }} />
        ) : (
          <span key={k++}>[图片]</span>
        ),
      )
    }
    last = m.index + m[0].length
  }
  if (last < content.length) {
    parts.push(<span key={k++}>{content.slice(last)}</span>)
  }
  return parts
}

export default function KnowledgeSearch() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [hits, setHits] = useState<KbSearchHit[]>([])
  const [loading, setLoading] = useState(false)
  const [docOptions, setDocOptions] = useState<{ value: number; label: string }[]>([])

  useEffect(() => {
    listDocuments({ page: 1, page_size: 100 })
      .then((data) =>
        setDocOptions(
          data.items.map((d: KbDocumentOut) => ({ value: d.id, label: `${d.title}（#${d.id}）` })),
        ),
      )
      .catch(() => {})
  }, [])

  const onSearch = async () => {
    const values = form.getFieldsValue()
    const query = (values.query || '').trim()
    if (!query) {
      message.warning('请输入检索内容')
      return
    }
    setLoading(true)
    try {
      const data = await searchKnowledge({
        query,
        top_k: values.top_k || 5,
        document_id: values.document_id,
        brand: values.brand,
        category: values.category,
        robot_model: values.robot_model,
        vector_weight: values.vector_weight ?? 0.7,
        searcher_weight: values.searcher_weight ?? 0.3,
      })
      setHits(data)
    } catch (e) {
      message.error(getApiErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <PageHeader title="知识库检索测试" />

      <div className="filter-card">
        <Form form={form} layout="inline">
          <Row gutter={16} align="middle" style={{ width: '100%' }}>
            <Col flex="auto">
              <Form.Item name="query" noStyle>
                <Input.TextArea
                  placeholder="输入要检索的问题或关键词，如：FANUC 机器人 SRVO-050 报警如何复位？"
                  autoSize={{ minRows: 1, maxRows: 3 }}
                />
              </Form.Item>
            </Col>
            <Col flex="none">
              <Button
                type="primary"
                icon={<SearchOutlined />}
                loading={loading}
                onClick={onSearch}
                style={{ height: 40 }}
              >
                检索
              </Button>
            </Col>
          </Row>
          <Row gutter={16} style={{ marginTop: 12 }}>
            <Col>
              <Form.Item name="document_id" label="文档" style={{ marginBottom: 0 }}>
                <Select
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  placeholder="全部文档"
                  style={{ width: 200 }}
                  options={docOptions}
                />
              </Form.Item>
            </Col>
            <Col>
              <Form.Item name="brand" label="品牌" style={{ marginBottom: 0 }}>
                <Input allowClear placeholder="如 FANUC" style={{ width: 130 }} />
              </Form.Item>
            </Col>
            <Col>
              <Form.Item name="robot_model" label="型号" style={{ marginBottom: 0 }}>
                <Input allowClear placeholder="如 R-2000iC/210L" style={{ width: 150 }} />
              </Form.Item>
            </Col>
            <Col>
              <Form.Item name="category" label="分类" style={{ marginBottom: 0 }}>
                <Input allowClear placeholder="如 报警手册" style={{ width: 140 }} />
              </Form.Item>
            </Col>
            <Col>
              <Form.Item name="top_k" initialValue={5} label="条数" style={{ marginBottom: 0 }}>
                <InputNumber min={1} max={50} style={{ width: 80 }} />
              </Form.Item>
            </Col>
            <Col>
              <Form.Item name="vector_weight" initialValue={0.7} label="向量权重" style={{ marginBottom: 0 }}>
                <InputNumber min={0} max={1} step={0.1} style={{ width: 90 }} />
              </Form.Item>
            </Col>
            <Col>
              <Form.Item name="searcher_weight" initialValue={0.3} label="关键词权重" style={{ marginBottom: 0 }}>
                <InputNumber min={0} max={1} step={0.1} style={{ width: 90 }} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </div>

      <div className="table-card">
        {hits.length === 0 && !loading ? (
          <Empty description="暂无结果，输入内容后点击「检索」" style={{ padding: '48px 0' }} />
        ) : (
          <List
            dataSource={hits}
            loading={loading}
            renderItem={(item, idx) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <span>第 {idx + 1} 条</span>
                      <Tag color="gold">综合 {item.score}</Tag>
                      <Tag color="blue">向量 {item.vector_score}</Tag>
                      <Tag color="green">关键词 {item.bm25_score}</Tag>
                      <Tag>文档 #{item.document_id}</Tag>
                      {item.chunk_index != null && <Tag>chunk {item.chunk_index}</Tag>}
                      {item.page != null && <Tag>第 {item.page} 页</Tag>}
                      {item.brand && <Tag color="blue">{item.brand}</Tag>}
                      {item.robot_model && <Tag color="geekblue">{item.robot_model}</Tag>}
                      {item.category && <Tag color="cyan">{item.category}</Tag>}
                    </div>
                  }
                  description={
                    <div>
                      {item.section && (
                        <div style={{ color: '#8c8c8c', marginBottom: 4 }}>{item.section}</div>
                      )}
                      <div style={{ whiteSpace: 'pre-wrap' }}>
                        {renderContentWithAttachments(item.content, item)}
                      </div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </div>
    </div>
  )
}
