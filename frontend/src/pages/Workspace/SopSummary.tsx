import type { AnswerSop } from './types'

/** SOP 摘要卡：排障步骤 / 备件建议 / 安全提示（消息流与人工确认卡共用）。 */
export default function SopSummary({ sop }: { sop: AnswerSop }) {
  const steps = sop.steps ?? []
  const parts = sop.parts ?? []
  const safety = sop.safety ?? []
  return (
    <div
      style={{
        border: '1px solid #303030',
        borderRadius: 8,
        padding: '12px 14px',
        fontSize: 12,
        margin: '0 0 8px',
        background: '#0a0a0a',
      }}
    >
      {steps.length > 0 && (
        <>
          <div style={{ color: '#fadb14', fontWeight: 600, marginBottom: 6 }}>排障步骤</div>
          <ol style={{ margin: 0, paddingLeft: 18 }}>
            {steps.map((s, i) => (
              <li key={i} style={{ marginBottom: 4, color: '#d9d9d9' }}>
                <b style={{ color: '#fafafa' }}>{s.title ?? ''}</b>
                {s.detail ? `：${s.detail}` : ''}
              </li>
            ))}
          </ol>
        </>
      )}
      {parts.length > 0 && (
        <>
          <div style={{ color: '#fadb14', fontWeight: 600, margin: '10px 0 6px' }}>备件建议</div>
          <ul style={{ margin: 0, paddingLeft: 18, color: '#d9d9d9' }}>
            {parts.map((p, i) => (
              <li key={i}>
                {p.part_no} {p.name} ×{p.qty ?? 1}
              </li>
            ))}
          </ul>
        </>
      )}
      {safety.length > 0 && (
        <>
          <div style={{ color: '#ff4d4f', fontWeight: 600, margin: '10px 0 6px' }}>安全提示</div>
          <ul style={{ margin: 0, paddingLeft: 18, color: '#d9d9d9' }}>
            {safety.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
