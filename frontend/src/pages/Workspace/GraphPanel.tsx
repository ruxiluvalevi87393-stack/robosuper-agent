import { useEffect, useMemo, useRef, useState } from 'react'
import { Button, Drawer, Empty, Segmented, Tag } from 'antd'
import { ApartmentOutlined, ZoomInOutlined } from '@ant-design/icons'
import { drag } from 'd3-drag'
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } from 'd3-force'
import type { SimulationNodeDatum } from 'd3-force'
import { select } from 'd3-selection'
import { zoom, zoomIdentity } from 'd3-zoom'
import type { ZoomBehavior } from 'd3-zoom'
import type { GraphAlarm, GraphResult } from './types'

type NodeType = 'query' | 'alarm' | 'cause' | 'sop' | 'similar'

interface GNode extends SimulationNodeDatum {
  id: string
  label: string
  type: NodeType
  detail: unknown
  dragged?: boolean
}

interface GLink {
  source: string | GNode
  target: string | GNode
}

const TYPE_COLORS: Record<NodeType, string> = {
  query: '#fadb14',
  alarm: '#ff4d4f',
  cause: '#fa8c16',
  sop: '#52c41a',
  similar: '#8c8c8c',
}
const TYPE_LABELS: Record<NodeType, string> = {
  query: '查询意图',
  alarm: '报警码',
  cause: '可能原因',
  sop: '处置步骤',
  similar: '相似报警',
}

const truncate = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

/** GraphResult[] → 力导向/分层布局用的节点边数据（query→alarm→cause/sop/similar）。 */
function buildGraph(graphs: GraphResult[]): { nodes: GNode[]; links: GLink[] } {
  const nodes: GNode[] = []
  const links: GLink[] = []
  const ids = new Set<string>()
  const addNode = (n: GNode) => {
    if (ids.has(n.id)) return
    ids.add(n.id)
    nodes.push(n)
  }
  const addLink = (a: string, b: string) => links.push({ source: a, target: b })

  for (const g of graphs) {
    const qid = `q-${g.intent ?? '?'}-${g.brand ?? '?'}-${g.alarm_code ?? '?'}`
    addNode({ id: qid, label: `${g.intent ?? '图谱查询'}${g.brand ? ' · ' + g.brand : ''}`, type: 'query', detail: g })
    for (const r of g.results ?? []) {
      const brand = r.brand ?? g.brand
      const aid = `a-${brand}-${r.code}`
      addNode({ id: aid, label: `${r.code ?? ''} ${r.title ?? ''}`.trim() || '报警', type: 'alarm', detail: r })
      addLink(qid, aid)

      ;(r.causes ?? []).forEach((c, i) => {
        const cid = `c-${aid}-${i}`
        addNode({ id: cid, label: c, type: 'cause', detail: r })
        addLink(aid, cid)
      })

      ;(r.cause_chain ?? []).forEach((cc, i) => {
        const cid = `cc-${aid}-${i}`
        addNode({ id: cid, label: cc.text ?? '原因链', type: 'cause', detail: { ...cc, alarm: r } })
        addLink(aid, cid)
        ;(cc.sops ?? []).forEach((s, j) => {
          const sid = `s-cc-${aid}-${i}-${j}`
          addNode({ id: sid, label: s, type: 'sop', detail: { sop: s, alarm: r } })
          addLink(cid, sid)
        })
      })

      ;(r.direct_sops ?? []).forEach((s, j) => {
        const sid = `s-d-${aid}-${j}`
        addNode({ id: sid, label: s, type: 'sop', detail: { sop: s, alarm: r } })
        addLink(aid, sid)
      })
      ;(r.sops ?? []).forEach((s, j) => {
        const sid = `s-${aid}-${j}`
        addNode({ id: sid, label: s, type: 'sop', detail: { sop: s, alarm: r } })
        addLink(aid, sid)
      })

      ;(r.similar?.items ?? []).forEach((si, j) => {
        const sid = `sim-${aid}-${j}`
        addNode({ id: sid, label: `${si.code ?? ''} ${si.title ?? ''}`.trim() || '相似报警', type: 'similar', detail: si })
        addLink(aid, sid)
      })
    }
  }
  return { nodes, links }
}

/** 图谱诊断面板（F3）：d3-force SVG 力导向 + 分层径向两种布局，点击节点看详情。 */
export default function GraphPanel({ graphs }: { graphs: GraphResult[] }) {
  const svgRef = useRef<SVGSVGElement>(null)
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const [layout, setLayout] = useState<'force' | 'radial'>('force')
  const [selected, setSelected] = useState<unknown | null>(null)
  const data = useMemo(() => buildGraph(graphs), [graphs])

  useEffect(() => {
    const svgEl = svgRef.current
    if (!svgEl || data.nodes.length === 0) return
    const svg = select(svgEl)
    svg.selectAll('*').remove()
    const width = svgEl.clientWidth || 640
    const height = svgEl.clientHeight || 460
    const root = svg.append('g').attr('class', 'graph-root')

    const zoomBehavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 4])
      .on('zoom', (event) => root.attr('transform', event.transform))
    zoomRef.current = zoomBehavior
    svg.call(zoomBehavior as never).call(zoomBehavior.transform as never, zoomIdentity)

    const defs = svg.append('defs')
    defs
      .append('marker')
      .attr('id', 'graph-arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#595959')

    const linkSel = root
      .append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(data.links)
      .join('line')
      .attr('stroke', '#434343')
      .attr('stroke-width', 1.2)
      .attr('marker-end', 'url(#graph-arrow)')
      .attr('opacity', 0.85)

    const nodeSel = root
      .append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(data.nodes)
      .join('g')
      .attr('cursor', 'pointer')
      .on('click', (event, d) => {
        event.stopPropagation()
        if (d.dragged) return
        setSelected(d.detail)
      })
    nodeSel
      .append('circle')
      .attr('r', (d) => (d.type === 'query' ? 15 : d.type === 'alarm' ? 11 : 8))
      .attr('fill', (d) => TYPE_COLORS[d.type])
      .attr('fill-opacity', 0.88)
      .attr('stroke', '#0a0a0a')
      .attr('stroke-width', 1.5)
    nodeSel
      .append('text')
      .attr('dy', (d) => (d.type === 'query' ? -24 : d.type === 'alarm' ? -18 : -15))
      .attr('text-anchor', 'middle')
      .attr('fill', '#fafafa')
      .attr('font-size', (d) => (d.type === 'query' ? 12 : d.type === 'alarm' ? 11 : 10))
      .style('paint-order', 'stroke')
      .style('stroke', '#0a0a0a')
      .style('stroke-width', 2.5)
      .text((d) => truncate(d.label, d.type === 'query' ? 18 : 22))

    if (layout === 'force') {
      const sim = forceSimulation<GNode>(data.nodes)
        .force('link', forceLink<GNode, GLink>(data.links).id((d) => d.id).distance(95).strength(0.4))
        .force('charge', forceManyBody<GNode>().strength(-340))
        .force('center', forceCenter<GNode>(width / 2, height / 2))
        .force('collide', forceCollide<GNode>().radius((d) => (d.type === 'query' ? 30 : 26)).iterations(2))
        .on('tick', () => {
          const posOf = (v: string | GNode) => (typeof v === 'string' ? undefined : (v as GNode))
          linkSel
            .attr('x1', (d) => posOf(d.source)?.x ?? 0)
            .attr('y1', (d) => posOf(d.source)?.y ?? 0)
            .attr('x2', (d) => posOf(d.target)?.x ?? 0)
            .attr('y2', (d) => posOf(d.target)?.y ?? 0)
          nodeSel.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`)
        })
      // 节点拖拽：阻止事件冒泡避免触发整体平移；拖拽期间固定节点位置，结束后释放
      const dragBehavior = drag<SVGGElement, GNode>()
        .on('start', (event, d) => {
          event.sourceEvent.stopPropagation()
          if (!event.active) sim.alphaTarget(0.3).restart()
          d.dragged = false
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.dragged = true
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) sim.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
      nodeSel.call(dragBehavior as never)
      return () => {
        sim.stop()
        svg.selectAll('*').remove()
      }
    }

    // 分层（径向）布局：BFS 从 query 根算深度，同层按角度散布
    const idOf = (v: string | GNode) => (typeof v === 'string' ? v : v.id)
    const adj = new Map<string, string[]>()
    for (const l of data.links) {
      const a = idOf(l.source)
      const b = idOf(l.target)
      if (!adj.has(a)) adj.set(a, [])
      adj.get(a)!.push(b)
    }
    const depth = new Map<string, number>()
    const queue: string[] = []
    for (const n of data.nodes)
      if (n.type === 'query') {
        depth.set(n.id, 0)
        queue.push(n.id)
      }
    for (let qi = 0; qi < queue.length; qi++) {
      const cur = queue[qi]
      const d = depth.get(cur)!
      for (const nb of adj.get(cur) ?? [])
        if (!depth.has(nb)) {
          depth.set(nb, d + 1)
          queue.push(nb)
        }
    }
    let maxDepth = 0
    const byDepth = new Map<number, GNode[]>()
    for (const n of data.nodes) {
      const d = depth.get(n.id) ?? 0
      maxDepth = Math.max(maxDepth, d)
      if (!byDepth.has(d)) byDepth.set(d, [])
      byDepth.get(d)!.push(n)
    }
    const pos = new Map<string, { x: number; y: number }>()
    const step = Math.min(width, height) / (maxDepth + 2.2)
    for (const [d, list] of byDepth) {
      const r = (d + 1) * step
      list.forEach((n, i) => {
        const angle = (i / list.length) * 2 * Math.PI - Math.PI / 2
        pos.set(n.id, { x: width / 2 + r * Math.cos(angle), y: height / 2 + r * Math.sin(angle) })
      })
    }
    linkSel
      .attr('x1', (d) => pos.get(idOf(d.source))?.x ?? 0)
      .attr('y1', (d) => pos.get(idOf(d.source))?.y ?? 0)
      .attr('x2', (d) => pos.get(idOf(d.target))?.x ?? 0)
      .attr('y2', (d) => pos.get(idOf(d.target))?.y ?? 0)
    nodeSel.attr('transform', (d) => {
      const p = pos.get(d.id)
      return p ? `translate(${p.x},${p.y})` : ''
    })

    return () => {
      svg.selectAll('*').remove()
    }
  }, [data, layout])

  const resetView = () => {
    const svgEl = svgRef.current
    const z = zoomRef.current
    if (!svgEl || !z) return
    select(svgEl).call(z.transform, zoomIdentity)
  }

  const empty = graphs.length === 0

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#1f1f1f',
        border: '1px solid #303030',
        borderRadius: 4,
        minHeight: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', borderBottom: '1px solid #303030' }}>
        <ApartmentOutlined style={{ color: '#fadb14' }} />
        <span style={{ color: '#fafafa', fontSize: 13, fontWeight: 600 }}>图谱诊断</span>
        <Segmented
          size="small"
          value={layout}
          onChange={(v) => setLayout(v as 'force' | 'radial')}
          options={[
            { label: '力导向', value: 'force' },
            { label: '分层', value: 'radial' },
          ]}
          style={{ marginLeft: 'auto' }}
        />
        <Button size="small" icon={<ZoomInOutlined />} disabled={empty} onClick={resetView}>
          重置视图
        </Button>
      </div>

      {empty ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Empty description={<span style={{ color: '#8c8c8c' }}>完成一次排查后，这里展示报警码 → 原因 → 处置的图谱</span>} />
        </div>
      ) : (
        <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
          <svg ref={svgRef} width="100%" height="100%" style={{ display: 'block' }} />
        </div>
      )}

      {!empty && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, padding: '8px 12px', borderTop: '1px solid #303030' }}>
          {(Object.keys(TYPE_COLORS) as NodeType[]).map((t) => (
            <Tag key={t} color={TYPE_COLORS[t]} style={{ marginInlineEnd: 0 }}>
              {TYPE_LABELS[t]}
            </Tag>
          ))}
        </div>
      )}

      <Drawer
        open={!!selected}
        onClose={() => setSelected(null)}
        width={500}
        title="节点详情"
        styles={{ body: { background: '#0a0a0a', padding: 12 } }}
      >
        <pre
          style={{
            margin: 0,
            color: '#b7eb8f',
            fontSize: 11,
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            maxHeight: '70vh',
            overflow: 'auto',
          }}
        >
          {JSON.stringify(selected, null, 2)}
        </pre>
      </Drawer>
    </div>
  )
}
