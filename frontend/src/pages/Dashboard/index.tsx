import { useEffect, useState } from 'react'
import { Empty, Table, Tag } from 'antd'
import type { TableColumnsType } from 'antd'
import {
  AlertOutlined,
  ApartmentOutlined,
  ControlOutlined,
  InboxOutlined,
  RobotOutlined,
  TagsOutlined,
  ToolOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import StatCard from '../../components/StatCard'
import { listBrands } from '../../api/brand'
import { listControllers } from '../../api/controller'
import { listRobotModels } from '../../api/robotModel'
import { listRobotInstances } from '../../api/robotInstance'
import { listPartInventory } from '../../api/partInventory'
import { listWorkOrders, WORK_ORDER_PRIORITY, WORK_ORDER_PRIORITY_COLOR, WORK_ORDER_STATUS, WORK_ORDER_STATUS_COLOR } from '../../api/workOrder'
import type { WorkOrderOut } from '../../api/workOrder'

const count = (p: Promise<{ total: number; items: unknown[] }>) => p.then((d) => d.total)

export default function Dashboard() {
  const [stats, setStats] = useState({
    instances: 0,
    running: 0,
    alarmMaintenance: 0,
    offline: 0,
    workOrders: 0,
    inProgress: 0,
    parts: 0,
    lowStock: 0,
    brands: 0,
    controllers: 0,
    models: 0,
  })
  const [recentOrders, setRecentOrders] = useState<WorkOrderOut[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    Promise.all([
      count(listRobotInstances({ page: 1, page_size: 1 })),
      count(listRobotInstances({ page: 1, page_size: 1, status: 'running' })),
      Promise.all([
        count(listRobotInstances({ page: 1, page_size: 1, status: 'alarm' })),
        count(listRobotInstances({ page: 1, page_size: 1, status: 'maintenance' })),
      ]).then(([a, m]) => a + m),
      count(listRobotInstances({ page: 1, page_size: 1, status: 'offline' })),
      count(listWorkOrders({ page: 1, page_size: 1 })),
      count(listWorkOrders({ page: 1, page_size: 1, status: 'in_progress' })),
      count(listPartInventory({ page: 1, page_size: 1 })),
      count(listPartInventory({ page: 1, page_size: 1, low_stock: true })),
      count(listBrands({ page: 1, page_size: 1 })),
      count(listControllers({ page: 1, page_size: 1 })),
      count(listRobotModels({ page: 1, page_size: 1 })),
    ])
      .then(
        ([
          instances, running, alarmMaintenance, offline, workOrders,
          inProgress, parts, lowStock, brands, controllers, models,
        ]) => {
          if (!alive) return
          setStats({
            instances, running, alarmMaintenance, offline, workOrders,
            inProgress, parts, lowStock, brands, controllers, models,
          })
        },
      )
      .catch(() => {})
      .finally(() => alive && setLoading(false))

    listWorkOrders({ page: 1, page_size: 8 })
      .then((d) => alive && setRecentOrders(d.items))
      .catch(() => {})

    return () => {
      alive = false
    }
  }, [])

  const orderColumns: TableColumnsType<WorkOrderOut> = [
    { title: '工单号', dataIndex: 'work_order_no', width: 180 },
    { title: '标题', dataIndex: 'title', ellipsis: true },
    {
      title: '优先级',
      dataIndex: 'priority',
      width: 80,
      render: (v: string) => (
        <Tag color={WORK_ORDER_PRIORITY_COLOR[v as keyof typeof WORK_ORDER_PRIORITY_COLOR] || 'default'}>
          {WORK_ORDER_PRIORITY[v as keyof typeof WORK_ORDER_PRIORITY] || v}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 80,
      render: (v: string) => (
        <Tag color={WORK_ORDER_STATUS_COLOR[v as keyof typeof WORK_ORDER_STATUS_COLOR] || 'default'}>
          {WORK_ORDER_STATUS[v as keyof typeof WORK_ORDER_STATUS] || v}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
  ]

  return (
    <div>
      <div className="stat-grid" style={{ marginBottom: 12 }}>
        <StatCard title="机器人实例（总）" value={stats.instances} icon={<RobotOutlined />} />
        <StatCard title="运行中" value={stats.running} icon={<ControlOutlined />} />
        <StatCard title="报警/维护中" value={stats.alarmMaintenance} icon={<AlertOutlined />} />
        <StatCard title="离线" value={stats.offline} icon={<ToolOutlined />} />
      </div>
      <div className="stat-grid" style={{ marginBottom: 12 }}>
        <StatCard title="工单总数" value={stats.workOrders} icon={<ToolOutlined />} />
        <StatCard title="处理中工单" value={stats.inProgress} icon={<AlertOutlined />} />
        <StatCard title="备件种类" value={stats.parts} icon={<InboxOutlined />} />
        <StatCard title="缺货备件" value={stats.lowStock} icon={<AlertOutlined />} />
      </div>
      <div className="stat-grid" style={{ marginBottom: 16 }}>
        <StatCard title="品牌数" value={stats.brands} icon={<TagsOutlined />} />
        <StatCard title="控制器型号" value={stats.controllers} icon={<ControlOutlined />} />
        <StatCard title="机器人型号" value={stats.models} icon={<ApartmentOutlined />} />
        <StatCard title="设备数据接入" value="REST" icon={<InboxOutlined />} />
      </div>

      <div className="table-card">
        <h2
          style={{
            color: '#fafafa',
            fontSize: 16,
            fontWeight: 600,
            borderLeft: '4px solid #fadb14',
            paddingLeft: 12,
            margin: '0 0 16px',
          }}
        >
          最近工单
        </h2>
        <Table<WorkOrderOut>
          rowKey="id"
          size="small"
          loading={loading}
          dataSource={recentOrders}
          columns={orderColumns}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无工单" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
        />
      </div>
    </div>
  )
}
