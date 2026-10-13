import { App, Button, Dropdown, Form, Input, Modal, Select, Table, Tag } from 'antd'
import type { TableColumnsType } from 'antd'
import { DownOutlined, PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import PageHeader from '../../../components/PageHeader'
import FilterBar from '../../../components/FilterBar'
import Pager from '../../../components/Pager'
import {
  createWorkOrder,
  deleteWorkOrder,
  listWorkOrders,
  updateWorkOrder,
  WORK_ORDER_NEXT_STATUS,
  WORK_ORDER_PRIORITY,
  WORK_ORDER_PRIORITY_COLOR,
  WORK_ORDER_STATUS,
  WORK_ORDER_STATUS_COLOR,
} from '../../../api/workOrder'
import type {
  WorkOrderCreatePayload,
  WorkOrderOut,
  WorkOrderPriority,
  WorkOrderQuery,
  WorkOrderStatus,
  WorkOrderUpdatePayload,
} from '../../../api/workOrder'
import { useCrud } from '../../../hooks/useCrud'
import { usePermission } from '../../../hooks/usePermission'
import { useRobotInstanceOptions, useUserOptions } from '../../../hooks/useOptions'
import { getApiErrorMessage } from '../../../utils/error'

const priorityOptions = Object.entries(WORK_ORDER_PRIORITY).map(([value, label]) => ({
  value: value as WorkOrderPriority,
  label,
}))

const statusOptions = Object.entries(WORK_ORDER_STATUS).map(([value, label]) => ({
  value: value as WorkOrderStatus,
  label,
}))

export default function WorkOrderList() {
  const { message, modal } = App.useApp()
  const { hasRole } = usePermission()
  const canWrite = hasRole('admin', 'engineer')
  const canSeeUsers = hasRole('admin')
  const [form] = Form.useForm()
  const [queryForm] = Form.useForm()
  const instanceOptions = useRobotInstanceOptions()
  const instanceMap = new Map(instanceOptions.map((o) => [o.value, o.label]))
  const userOptions = useUserOptions(canSeeUsers)
  const userMap = new Map(userOptions.map((o) => [o.value, o.label]))

  const crud = useCrud<WorkOrderOut, WorkOrderQuery, WorkOrderCreatePayload, WorkOrderUpdatePayload>(
    {
      list: listWorkOrders,
      create: createWorkOrder,
      update: updateWorkOrder,
      remove: deleteWorkOrder,
    },
    {
      keyword: undefined,
      status: undefined,
      priority: undefined,
      robot_instance_id: undefined,
      assignee_id: undefined,
      alarm_code: undefined,
    },
  )

  const onOpenCreate = () => {
    form.resetFields()
    form.setFieldsValue({ priority: 'normal' })
    crud.openCreate()
  }

  const onOpenEdit = (row: WorkOrderOut) => {
    form.resetFields()
    form.setFieldsValue({
      ...row,
      diagnosis_context: row.diagnosis_context
        ? JSON.stringify(row.diagnosis_context, null, 2)
        : undefined,
    })
    crud.openEdit(row)
  }

  const onSubmit = async () => {
    const values = form.getFieldsValue()
    const payload: WorkOrderUpdatePayload = { ...values }
    if (payload.diagnosis_context) {
      if (typeof payload.diagnosis_context === 'string') {
        try {
          payload.diagnosis_context = JSON.parse(payload.diagnosis_context)
        } catch {
          message.error('诊断结论 JSON 格式不正确')
          return
        }
      }
    } else {
      delete payload.diagnosis_context
    }
    await crud.save(payload)
  }

  const onTransition = async (row: WorkOrderOut, next: WorkOrderStatus) => {
    try {
      await updateWorkOrder(row.id, { status: next })
      message.success(`已流转为「${WORK_ORDER_STATUS[next]}」`)
      crud.fetchList()
    } catch (e) {
      message.error(getApiErrorMessage(e))
    }
  }

  const onDelete = (row: WorkOrderOut) => {
    modal.confirm({
      title: '删除工单',
      content: `确定删除工单「${row.work_order_no} ${row.title}」？`,
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => crud.remove(row.id),
    })
  }

  const columns: TableColumnsType<WorkOrderOut> = [
    { title: '工单号', dataIndex: 'work_order_no', width: 170 },
    { title: '标题', dataIndex: 'title', width: 220, ellipsis: true },
    {
      title: '优先级',
      dataIndex: 'priority',
      width: 90,
      render: (v: WorkOrderPriority) => (
        <Tag color={WORK_ORDER_PRIORITY_COLOR[v] || 'default'}>{WORK_ORDER_PRIORITY[v] || v}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v: WorkOrderStatus) => (
        <Tag color={WORK_ORDER_STATUS_COLOR[v] || 'default'}>{WORK_ORDER_STATUS[v] || v}</Tag>
      ),
    },
    {
      title: '机器人',
      dataIndex: 'robot_instance_id',
      width: 180,
      render: (v: number | null) => (v ? instanceMap.get(v) || v : '-'),
    },
    { title: '报警码', dataIndex: 'alarm_code', width: 110, render: (v: string) => v || '-' },
    {
      title: '处理人',
      dataIndex: 'assignee_id',
      width: 130,
      render: (v: number | null) => (v ? userMap.get(v) || v : '-'),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    ...(canWrite
      ? [
          {
            title: '操作',
            key: 'op',
            width: 180,
            fixed: 'right' as const,
            render: (_: unknown, r: WorkOrderOut) => {
              const nextList = WORK_ORDER_NEXT_STATUS[r.status as WorkOrderStatus] || []
              return (
                <div style={{ display: 'flex', gap: 8, whiteSpace: 'nowrap' }}>
                  <Button size="small" type="primary" onClick={() => onOpenEdit(r)}>
                    编辑
                  </Button>
                  {nextList.length > 0 && (
                    <Dropdown
                      menu={{
                        items: nextList.map((s) => ({
                          key: s,
                          label: `流转为 ${WORK_ORDER_STATUS[s]}`,
                        })),
                        onClick: ({ key }) => onTransition(r, key as WorkOrderStatus),
                      }}
                    >
                      <Button size="small">
                        流转 <DownOutlined />
                      </Button>
                    </Dropdown>
                  )}
                  <Button size="small" danger onClick={() => onDelete(r)}>
                    删除
                  </Button>
                </div>
              )
            },
          },
        ]
      : []),
  ]

  return (
    <div>
      <PageHeader
        title="工单管理"
        actions={
          canWrite && (
            <Button type="primary" icon={<PlusOutlined />} onClick={onOpenCreate}>
              新建工单
            </Button>
          )
        }
      />

      <FilterBar
        form={queryForm}
        onSearch={() => crud.onSearch(queryForm.getFieldsValue() as WorkOrderQuery)}
        onReset={() => {
          queryForm.resetFields()
          crud.onReset()
        }}
      >
        <Form.Item label="关键词" name="keyword">
          <Input placeholder="工单号/标题" allowClear style={{ width: 200 }} />
        </Form.Item>
        <Form.Item label="状态" name="status">
          <Select placeholder="全部" allowClear options={statusOptions} style={{ width: 120 }} />
        </Form.Item>
        <Form.Item label="优先级" name="priority">
          <Select placeholder="全部" allowClear options={priorityOptions} style={{ width: 110 }} />
        </Form.Item>
        <Form.Item label="机器人" name="robot_instance_id">
          <Select placeholder="全部" allowClear showSearch optionFilterProp="label" options={instanceOptions} style={{ width: 190 }} />
        </Form.Item>
        <Form.Item label="报警码" name="alarm_code">
          <Input placeholder="如 SRVO-050" allowClear style={{ width: 130 }} />
        </Form.Item>
        <Form.Item label="处理人" name="assignee_id">
          <Select placeholder="全部" allowClear options={userOptions} style={{ width: 150 }} disabled={!canSeeUsers} />
        </Form.Item>
      </FilterBar>

      <div className="table-card">
        <Table<WorkOrderOut>
          rowKey="id"
          loading={crud.loading}
          dataSource={crud.list}
          columns={columns}
          pagination={false}
          scroll={{ x: 1250 }}
        />
        <Pager
          current={crud.page}
          pageSize={crud.pageSize}
          total={crud.total}
          onChange={crud.onPageChange}
        />
      </div>

      <Modal
        title={crud.isEdit ? '编辑工单' : '新建工单'}
        width={600}
        open={crud.modalOpen}
        confirmLoading={crud.submitting}
        okText="确定"
        cancelText="取消"
        forceRender
        onOk={() => form.submit()}
        onCancel={() => crud.setModalOpen(false)}
      >
        <Form form={form} layout="vertical" onFinish={onSubmit} style={{ marginTop: 8 }}>
          <Form.Item name="title" label="工单标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="工单标题" maxLength={200} />
          </Form.Item>
          <Form.Item name="robot_instance_id" label="关联机器人">
            <Select placeholder="可选" allowClear showSearch optionFilterProp="label" options={instanceOptions} />
          </Form.Item>
          <Form.Item name="alarm_code" label="报警码">
            <Input placeholder="如 SRVO-050" maxLength={20} />
          </Form.Item>
          <Form.Item name="priority" label="优先级" rules={[{ required: true, message: '请选择优先级' }]}>
            <Select options={priorityOptions} />
          </Form.Item>
          <Form.Item
            name="assignee_id"
            label="指派工程师"
            extra={!canSeeUsers ? '仅管理员可指派' : undefined}
          >
            <Select placeholder="可选" allowClear options={userOptions} disabled={!canSeeUsers} />
          </Form.Item>
          {crud.isEdit && (
            <Form.Item
              name="status"
              label="状态"
              tooltip="仅允许按流程流转：created→assigned→in_progress→resolved→closed"
            >
              <Select options={statusOptions} />
            </Form.Item>
          )}
          {crud.isEdit && (
            <Form.Item name="diagnosis_context" label="诊断结论(JSON)">
              <Input.TextArea
                placeholder={'如 {"结论": "伺服过载", "建议": "更换电机"}，留空不修改'}
                rows={3}
              />
            </Form.Item>
          )}
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="工单描述" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
