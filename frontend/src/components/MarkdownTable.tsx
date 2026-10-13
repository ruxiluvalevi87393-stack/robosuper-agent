import { Table } from 'antd'

/** 把 Markdown 表格（| a | b |\n|---|---|\n| 1 | 2 |）解析成列/行，供 antd Table 渲染 */
export function parseMarkdownTable(md: string): { columns: string[]; rows: string[][] } | null {
  const lines = md
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l.startsWith('|'))
  if (lines.length < 2) return null
  const parseRow = (line: string) =>
    line.replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim())
  return { columns: parseRow(lines[0]), rows: lines.slice(2).map(parseRow) }
}

/** 渲染一个 Markdown 表格；解析失败回退为纯文本 <pre> */
export default function MarkdownTable({ md }: { md: string }) {
  const parsed = parseMarkdownTable(md)
  if (!parsed) {
    return <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: 0 }}>{md}</pre>
  }
  const { columns, rows } = parsed
  return (
    <Table
      size="small"
      pagination={false}
      rowKey={(_, i) => String(i ?? 0)}
      columns={columns.map((c) => ({ title: c, dataIndex: c, key: c, ellipsis: true }))}
      dataSource={rows.map((r) => Object.fromEntries(columns.map((c, i) => [c, r[i] ?? ''])))}
      scroll={{ x: 'max-content' }}
    />
  )
}
