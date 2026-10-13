import { Pagination } from 'antd'

/** 右对齐分页条 */
export default function Pager({
  current,
  pageSize,
  total,
  onChange,
}: {
  current: number
  pageSize: number
  total: number
  onChange: (page: number, pageSize: number) => void
}) {
  return (
    <div className="pager">
      <Pagination
        current={current}
        pageSize={pageSize}
        total={total}
        showSizeChanger
        showQuickJumper
        showTotal={(t) => `共 ${t} 条`}
        pageSizeOptions={[10, 20, 50]}
        onChange={onChange}
      />
    </div>
  )
}
