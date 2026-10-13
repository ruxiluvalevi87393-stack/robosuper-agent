import { App, Button, Form, Input, InputNumber, Modal, Select, Table } from 'antd'
import type { TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import PageHeader from '../../../components/PageHeader'
import FilterBar from '../../../components/FilterBar'
import Pager from '../../../components/Pager'
import { createServoParam, deleteServoParam, listServoParams, updateServoParam } from '../../../api/servoParam'
import type { ServoParamCreatePayload, ServoParamOut, ServoParamQuery, ServoParamUpdatePayload } from '../../../api/servoParam'
import { useCrud } from '../../../hooks/useCrud'
import { usePermission } from '../../../hooks/usePermission'
import { useRobotModelOptions } from '../../../hooks/useOptions'

export default function ServoParamList() {
  const { modal } = App.useApp()
  const { hasRole } = usePermission()
  const canWrite = hasRole('admin')
  const [form] = Form.useForm()
  const [queryForm] = Form.useForm()
  const modelOptions = useRobotModelOptions()
  const modelMap = new Map(modelOptions.map((o) => [o.value, o.label]))

  const crud = useCrud<ServoParamOut, ServoParamQuery, ServoParamCreatePayload, ServoParamUpdatePayload>(
    {
      list: listServoParams,
      create: createServoParam,
      update: updateServoParam,
      remove: deleteServoParam,
    },
    { keyword: undefined, robot_model_id: undefined },
  )

  const onOpenCreate = () => {
    form.resetFields()
    crud.openCreate()
  }

  const onOpenEdit = (row: ServoParamOut) => {
    form.resetFields()
    form.setFieldsValue(row)
    crud.openEdit(row)
  }

  const onSubmit = async () => {
    const values = form.getFieldsValue()
    await crud.save(values)
  }

  const onDelete = (row: ServoParamOut) => {
    modal.confirm({
      title: '删除参数',
      content: `确定删除参数「${row.param_code} ${row.param_name}」？`,
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => crud.remove(row.id),
    })
  }

  const columns: TableColumnsType<ServoParamOut> = [
    {
      title: '所属型号',
      dataIndex: 'robot_model_id',
      width: 190,
      render: (v: number) => modelMap.get(v) || v,
    },
    { title: '参数代码', dataIndex: 'param_code', width: 150 },
    { title: '参数名称', dataIndex: 'param_name', width: 180 },
    {
      title: '默认值',
      dataIndex: 'default_value',
      width: 90,
      render: (v: number | string | null) => v ?? '-',
    },
    {
      title: '允许范围',
      key: 'range',
      width: 140,
      render: (_, r) => {
        const lo = r.min_value ?? '-∞'
        const hi = r.max_value ?? '+∞'
        return `${lo} ~ ${hi}${r.unit ? ' ' + r.unit : ''}`
      },
    },
    { title: '单位', dataIndex: 'unit', width: 80, render: (v: string) => v || '-' },
    { title: '描述', dataIndex: 'description', ellipsis: true, render: (v: string) => v || '-' },
    ...(canWrite
      ? [
          {
            title: '操作',
            key: 'op',
            width: 140,
            fixed: 'right' as const,
            render: (_: unknown, r: ServoParamOut) => (
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
        title="伺服参数"
        actions={
          canWrite && (
            <Button type="primary" icon={<PlusOutlined />} onClick={onOpenCreate}>
              新增参数
            </Button>
          )
        }
      />

      <FilterBar
        form={queryForm}
        onSearch={() => crud.onSearch(queryForm.getFieldsValue() as ServoParamQuery)}
        onReset={() => {
          queryForm.resetFields()
          crud.onReset()
        }}
      >
        <Form.Item label="关键词" name="keyword">
          <Input placeholder="参数代码/名称" allowClear style={{ width: 220 }} />
        </Form.Item>
        <Form.Item label="型号" name="robot_model_id">
          <Select placeholder="全部" allowClear showSearch optionFilterProp="label" options={modelOptions} style={{ width: 200 }} />
        </Form.Item>
      </FilterBar>

      <div className="table-card">
        <Table<ServoParamOut>
          rowKey="id"
          loading={crud.loading}
          dataSource={crud.list}
          columns={columns}
          pagination={false}
          scroll={{ x: 1000 }}
        />
        <Pager
          current={crud.page}
          pageSize={crud.pageSize}
          total={crud.total}
          onChange={crud.onPageChange}
        />
      </div>

      <Modal
        title={crud.isEdit ? '编辑参数' : '新增参数'}
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
          <Form.Item name="param_code" label="参数代码" rules={[{ required: true, message: '请输入参数代码' }]}>
            <Input placeholder="型号内唯一" maxLength={50} />
          </Form.Item>
          <Form.Item name="param_name" label="参数名称" rules={[{ required: true, message: '请输入参数名称' }]}>
            <Input placeholder="参数名称" maxLength={100} />
          </Form.Item>
          <Form.Item name="default_value" label="出厂默认值">
            <InputNumber stringMode placeholder="如 100" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="min_value" label="允许下限">
            <InputNumber stringMode placeholder="如 0" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="max_value" label="允许上限">
            <InputNumber stringMode placeholder="如 500" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="unit" label="单位">
            <Input placeholder="如 r/min" maxLength={20} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="参数说明" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
