import type { ReactNode } from 'react'
import { Button, Form } from 'antd'
import type { FormInstance } from 'antd'

/** 筛选卡片：内联表单 + 查询/重置按钮 */
export default function FilterBar({
  form,
  onSearch,
  onReset,
  children,
}: {
  form: FormInstance
  onSearch: () => void
  onReset: () => void
  children: ReactNode
}) {
  return (
    <div className="filter-card">
      <Form form={form} layout="inline">
        {children}
        <Form.Item style={{ marginBottom: 16 }}>
          <Button type="primary" onClick={onSearch}>
            查询
          </Button>
          <Button style={{ marginLeft: 8 }} onClick={onReset}>
            重置
          </Button>
        </Form.Item>
      </Form>
    </div>
  )
}
