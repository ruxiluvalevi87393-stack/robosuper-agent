import type { ReactNode } from 'react'

/** 页面页头：金色左竖条标题 + 右侧操作区 */
export default function PageHeader({
  title,
  actions,
}: {
  title: string
  actions?: ReactNode
}) {
  return (
    <div className="page-header">
      <h2>{title}</h2>
      {actions && <div className="page-header-actions">{actions}</div>}
    </div>
  )
}
