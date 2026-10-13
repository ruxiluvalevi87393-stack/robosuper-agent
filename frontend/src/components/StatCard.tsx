import type { ReactNode } from 'react'

/** 黑金风格统计卡片：面板底 + 金色上边框 + 金色图标/数值 */
export default function StatCard({
  title,
  value,
  icon,
}: {
  title: string
  value: number | string
  icon: ReactNode
}) {
  return (
    <div className="stat-card">
      <div className="stat-card-icon">{icon}</div>
      <div className="stat-card-body">
        <div className="stat-card-value">{value}</div>
        <div className="stat-card-title">{title}</div>
      </div>
    </div>
  )
}
