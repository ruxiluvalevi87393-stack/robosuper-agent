import { App, Button, DatePicker, Form, Input, InputNumber, Modal, Select, Table } from 'antd'
import type { TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import PageHeader from '../../../components/PageHeader'
import FilterBar from '../../../components/FilterBar'
import Pager from '../../../components/Pager'
import { createMaintenanceLog, listMaintenanceLogs } from '../../../api/maintenanceLog'
import type {
  MaintenanceLogCreatePayload,
  MaintenanceLogOut,
  MaintenanceLogQuery,
} from '../../../api/maintenanceLog'
import { useCrud } from '../../../hooks/useCrud'
import { usePermission } from '../../../hooks/usePermission'
import { useRobotInstanceOptions, useUserOptions } from '../../../hooks/useOptions'

export default function MaintenanceLogList() {
  const { message } = App.useApp()
  const { hasRole } = usePermission()
  const canWrite = hasRole('admin', 'engineer')
  const canSeeUsers = hasRole('admin')
  const [form] = Form.useForm()
  const [queryForm] = Form.useForm()
  const instanceOptions = useRobotInstanceOptions()
  const instanceMap = new Map(instanceOptions.map((o) => [o.value, o.label]))
  const userOptions = useUserOptions(canSeeUsers)
  const userMap = new Map(userOptions.map((o) => [o.value, o.label]))

  // 维修历史只增只查，无 update/remove
  const crud = useCrud<MaintenanceLogOut, MaintenanceLogQuery, MaintenanceLogCreatePayload, never>(
    { list: listMaintenanceLogs, create: createMaintenanceLog },
    { robot_instance_id: undefined, alarm_code: undefined, engineer_id: undefined, work_order_no: undefined },
  )

  const onOpenCreate = () => {
    form.resetFields()
    crud.openCreate()
  }

  const onSubmit = async () => {
    const values = form.getFieldsValue()
    const payload: MaintenanceLogCreatePayload = { ...values }
    if (payload.parts_used) {
      if (typeof payload.parts_used === 'string') {
        try {
          payload.parts_used = JSON.parse(payload.parts_used)
        } catch {
          message.error('备件清单 JSON 格式不正确')
          return
        }
      }
    } else {
      delete payload.parts_used
    }
    if (values.occurred_at) {
      payload.occurred_at = values.occurred_at.toISOString()
    } else {
      delete payload.occurred_at
    }
    await crud.save(payload)
  }

  const columns: TableColumnsType<MaintenanceLogOut> = [
    { title: '工单号', dataIndex: 'work_order_no', width: 160, render: (v: string) => v || '-' },
    {
      title: '机器人',
      dataIndex: 'robot_instance_id',
      width: 180,
      render: (v: number | null) => (v ? instanceMap.get(v) || v : '-'),
    },
    { title: '报警码', dataIndex: 'alarm_code', width: 110, render: (v: string) => v || '-' },
    {
      title: '工程师',
      dataIndex: 'engineer_id',
      width: 130,
      render: (v: number | null) => (v ? userMap.get(v) || v : '-'),
    },
    { title: '故障描述', dataIndex: 'fault_description', ellipsis: true, render: (v: string) => v || '-' },
    { title: '根因', dataIndex: 'root_cause', width: 180, ellipsis: true, render: (v: string) => v || '-' },
    {
      title: '停机时长',
      dataIndex: 'downtime_minutes',
      width: 110,
      render: (v: number | null) => (v == null ? '-' : `${v} 分钟`),
    },
    {
      title: '发生时间',
      dataIndex: 'occurred_at',
      width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
  ]

  return (
    <div>
      <PageHeader
        title="维护日志"
        actions={
          canWrite && (
            <Button type="primary" icon={<PlusOutlined />} onClick={onOpenCreate}>
              新增维修记录
            </Button>
          )
        }
      />

      <FilterBar
        form={queryForm}
        onSearch={() => crud.onSearch(queryForm.getFieldsValue() as MaintenanceLogQuery)}
        onReset={() => {
          queryForm.resetFields()
          crud.onReset()
        }}
      >
        <Form.Item label="工单号" name="work_order_no">
          <Input placeholder="工单号" allowClear style={{ width: 170 }} />
        </Form.Item>
        <Form.Item label="机器人" name="robot_instance_id">
          <Select placeholder="全部" allowClear showSearch optionFilterProp="label" options={instanceOptions} style={{ width: 190 }} />
        </Form.Item>
        <Form.Item label="报警码" name="alarm_code">
          <Input placeholder="如 SRVO-050" allowClear style={{ width: 130 }} />
        </Form.Item>
        <Form.Item label="工程师" name="engineer_id">
          <Select placeholder="全部" allowClear options={userOptions} style={{ width: 150 }} disabled={!canSeeUsers} />
        </Form.Item>
      </FilterBar>

      <div className="table-card">
        <Table<MaintenanceLogOut>
          rowKey="id"
          loading={crud.loading}
          dataSource={crud.list}
          columns={columns}
          pagination={false}
          scroll={{ x: 1100 }}
        />
        <Pager
          current={crud.page}
          pageSize={crud.pageSize}
          total={crud.total}
          onChange={crud.onPageChange}
        />
      </div>

      <Modal
        title="新增维修记录"
        width={640}
        open={crud.modalOpen}
        confirmLoading={crud.submitting}
        okText="确定"
        cancelText="取消"
        forceRender
        onOk={() => form.submit()}
        onCancel={() => crud.setModalOpen(false)}
      >
        <Form form={form} layout="vertical" onFinish={onSubmit} style={{ marginTop: 8 }}>
          <Form.Item name="work_order_no" label="关联工单号">
            <Input placeholder="可选" maxLength={30} />
          </Form.Item>
          <Form.Item name="robot_instance_id" label="维修对象">
            <Select placeholder="可选" allowClear showSearch optionFilterProp="label" options={instanceOptions} />
          </Form.Item>
          <Form.Item name="alarm_code" label="报警码">
            <Input placeholder="如 SRVO-050" maxLength={20} />
          </Form.Item>
          <Form.Item
            name="engineer_id"
            label="处理工程师"
            extra={!canSeeUsers ? '默认当前用户，仅管理员可指定' : undefined}
          >
            <Select placeholder="留空默认当前用户" allowClear options={userOptions} disabled={!canSeeUsers} />
          </Form.Item>
          <Form.Item name="fault_description" label="故障描述">
            <Input.TextArea placeholder="故障现象描述" rows={2} />
          </Form.Item>
          <Form.Item name="root_cause" label="根本原因">
            <Input.TextArea placeholder="根因分析" rows={2} />
          </Form.Item>
          <Form.Item name="sop_used" label="使用 SOP">
            <Input placeholder="如 SOP-003 伺服过载排查" maxLength={200} />
          </Form.Item>
          <Form.Item name="parts_used" label="使用备件(JSON)">
            <Input.TextArea
              placeholder={'如 {"电机": 1, "编码器": 1}'}
              rows={2}
            />
          </Form.Item>
          <Form.Item name="downtime_minutes" label="停机时长(分钟)">
            <InputNumber min={0} placeholder="如 120" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="occurred_at" label="故障发生时间">
            <DatePicker showTime style={{ width: '100%' }} placeholder="留空默认当前时间" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
