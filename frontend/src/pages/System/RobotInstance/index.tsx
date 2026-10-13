import { App, Button, DatePicker, Form, Input, Modal, Select, Table, Tag } from 'antd'
import type { TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import PageHeader from '../../../components/PageHeader'
import FilterBar from '../../../components/FilterBar'
import Pager from '../../../components/Pager'
import {
  createRobotInstance,
  deleteRobotInstance,
  listRobotInstances,
  updateRobotInstance,
  ROBOT_INSTANCE_STATUS,
  ROBOT_INSTANCE_STATUS_COLOR,
} from '../../../api/robotInstance'
import type {
  RobotInstanceCreatePayload,
  RobotInstanceOut,
  RobotInstanceQuery,
  RobotInstanceStatus,
  RobotInstanceUpdatePayload,
} from '../../../api/robotInstance'
import { useCrud } from '../../../hooks/useCrud'
import { usePermission } from '../../../hooks/usePermission'
import { useRobotModelOptions } from '../../../hooks/useOptions'

const statusOptions = Object.entries(ROBOT_INSTANCE_STATUS).map(([value, label]) => ({
  value: value as RobotInstanceStatus,
  label,
}))

export default function RobotInstanceList() {
  const { modal } = App.useApp()
  const { hasRole } = usePermission()
  const canWrite = hasRole('admin')
  const [form] = Form.useForm()
  const [queryForm] = Form.useForm()
  const modelOptions = useRobotModelOptions()
  const modelMap = new Map(modelOptions.map((o) => [o.value, o.label]))

  const crud = useCrud<
    RobotInstanceOut,
    RobotInstanceQuery,
    RobotInstanceCreatePayload,
    RobotInstanceUpdatePayload
  >(
    {
      list: listRobotInstances,
      create: createRobotInstance,
      update: updateRobotInstance,
      remove: deleteRobotInstance,
    },
    { keyword: undefined, robot_model_id: undefined, status: undefined, line_id: undefined },
  )

  const onOpenCreate = () => {
    form.resetFields()
    form.setFieldsValue({ status: 'running' })
    crud.openCreate()
  }

  const onOpenEdit = (row: RobotInstanceOut) => {
    form.resetFields()
    form.setFieldsValue({
      ...row,
      install_date: row.install_date ? dayjs(row.install_date) : undefined,
    })
    crud.openEdit(row)
  }

  const onSubmit = async () => {
    const values = form.getFieldsValue()
    await crud.save({
      ...values,
      install_date: values.install_date ? values.install_date.format('YYYY-MM-DD') : undefined,
    })
  }

  const onDelete = (row: RobotInstanceOut) => {
    modal.confirm({
      title: '删除实例',
      content: `确定删除实例「${row.asset_no}」？若有工单/日志关联将无法删除。`,
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => crud.remove(row.id),
    })
  }

  const columns: TableColumnsType<RobotInstanceOut> = [
    { title: '资产编号', dataIndex: 'asset_no', width: 150 },
    { title: '名称', dataIndex: 'name', width: 150, render: (v: string) => v || '-' },
    {
      title: '所属型号',
      dataIndex: 'robot_model_id',
      width: 190,
      render: (v: number) => modelMap.get(v) || v,
    },
    { title: '序列号', dataIndex: 'serial_no', width: 130, render: (v: string) => v || '-' },
    { title: '产线', dataIndex: 'line_id', width: 110, render: (v: string) => v || '-' },
    {
      title: '安装日期',
      dataIndex: 'install_date',
      width: 120,
      render: (v: string) => v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (v: RobotInstanceStatus) => (
        <Tag color={ROBOT_INSTANCE_STATUS_COLOR[v] || 'default'}>{ROBOT_INSTANCE_STATUS[v] || v}</Tag>
      ),
    },
    { title: '备注', dataIndex: 'note', ellipsis: true, render: (v: string) => v || '-' },
    ...(canWrite
      ? [
          {
            title: '操作',
            key: 'op',
            width: 140,
            fixed: 'right' as const,
            render: (_: unknown, r: RobotInstanceOut) => (
              <div style={{ display: 'flex', gap: 8, whiteSpace: 'nowrap' }}>
                <Button size="small" type="primary" onClick={() => onOpenEdit(r)}>
                  编辑
                </Button>
                <Button size="small" danger onClick={() => onDelete(r)}>
                  删除
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ]

  return (
    <div>
      <PageHeader
        title="机器人实例"
        actions={
          canWrite && (
            <Button type="primary" icon={<PlusOutlined />} onClick={onOpenCreate}>
              新增实例
            </Button>
          )
        }
      />

      <FilterBar
        form={queryForm}
        onSearch={() => crud.onSearch(queryForm.getFieldsValue() as RobotInstanceQuery)}
        onReset={() => {
          queryForm.resetFields()
          crud.onReset()
        }}
      >
        <Form.Item label="关键词" name="keyword">
          <Input placeholder="资产编号/名称" allowClear style={{ width: 200 }} />
        </Form.Item>
        <Form.Item label="型号" name="robot_model_id">
          <Select placeholder="全部" allowClear showSearch optionFilterProp="label" options={modelOptions} style={{ width: 200 }} />
        </Form.Item>
        <Form.Item label="状态" name="status">
          <Select placeholder="全部" allowClear options={statusOptions} style={{ width: 120 }} />
        </Form.Item>
        <Form.Item label="产线" name="line_id">
          <Input placeholder="如 LINE-001" allowClear style={{ width: 130 }} />
        </Form.Item>
      </FilterBar>

      <div className="table-card">
        <Table<RobotInstanceOut>
          rowKey="id"
          loading={crud.loading}
          dataSource={crud.list}
          columns={columns}
          pagination={false}
          scroll={{ x: 1150 }}
        />
        <Pager
          current={crud.page}
          pageSize={crud.pageSize}
          total={crud.total}
          onChange={crud.onPageChange}
        />
      </div>

      <Modal
        title={crud.isEdit ? '编辑实例' : '新增实例'}
        width={560}
        open={crud.modalOpen}
        confirmLoading={crud.submitting}
        okText="确定"
        cancelText="取消"
        forceRender
        onOk={() => form.submit()}
        onCancel={() => crud.setModalOpen(false)}
      >
        <Form form={form} layout="vertical" onFinish={onSubmit} style={{ marginTop: 8 }}>
          <Form.Item
            name="robot_model_id"
            label="所属型号"
            rules={[{ required: true, message: '请选择型号' }]}
          >
            <Select placeholder="选择型号" showSearch optionFilterProp="label" options={modelOptions} />
          </Form.Item>
          <Form.Item name="asset_no" label="资产编号" rules={[{ required: true, message: '请输入资产编号' }]}>
            <Input placeholder="客户资产编号，唯一" maxLength={50} />
          </Form.Item>
          <Form.Item name="name" label="实例名称/别名">
            <Input placeholder="如 1号焊接机器人" maxLength={100} />
          </Form.Item>
          <Form.Item name="serial_no" label="出厂序列号">
            <Input placeholder="出厂序列号" maxLength={50} />
          </Form.Item>
          <Form.Item name="line_id" label="所属产线">
            <Input placeholder="如 LINE-001" maxLength={50} />
          </Form.Item>
          <Form.Item name="install_date" label="安装日期">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select options={statusOptions} />
          </Form.Item>
          <Form.Item name="note" label="备注">
            <Input.TextArea placeholder="备注" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
