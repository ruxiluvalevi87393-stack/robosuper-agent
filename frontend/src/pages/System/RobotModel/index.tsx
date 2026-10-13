import { App, Button, Form, Input, InputNumber, Modal, Select, Table } from 'antd'
import type { TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import PageHeader from '../../../components/PageHeader'
import FilterBar from '../../../components/FilterBar'
import Pager from '../../../components/Pager'
import { createRobotModel, deleteRobotModel, listRobotModels, updateRobotModel } from '../../../api/robotModel'
import type { RobotModelCreatePayload, RobotModelOut, RobotModelQuery, RobotModelUpdatePayload } from '../../../api/robotModel'
import { useCrud } from '../../../hooks/useCrud'
import { usePermission } from '../../../hooks/usePermission'
import { useBrandOptions, useControllerOptions } from '../../../hooks/useOptions'

export default function RobotModelList() {
  const { modal } = App.useApp()
  const { hasRole } = usePermission()
  const canWrite = hasRole('admin')
  const [form] = Form.useForm()
  const [queryForm] = Form.useForm()
  const brandOptions = useBrandOptions()
  const controllerOptions = useControllerOptions()
  const brandMap = new Map(brandOptions.map((o) => [o.value, o.label]))
  const controllerMap = new Map(controllerOptions.map((o) => [o.value, o.label]))

  const crud = useCrud<RobotModelOut, RobotModelQuery, RobotModelCreatePayload, RobotModelUpdatePayload>(
    {
      list: listRobotModels,
      create: createRobotModel,
      update: updateRobotModel,
      remove: deleteRobotModel,
    },
    { keyword: undefined, brand_id: undefined, controller_id: undefined },
  )

  const onOpenCreate = () => {
    form.resetFields()
    crud.openCreate()
  }

  const onOpenEdit = (row: RobotModelOut) => {
    form.resetFields()
    form.setFieldsValue(row)
    crud.openEdit(row)
  }

  const onSubmit = async () => {
    const values = form.getFieldsValue()
    await crud.save(values)
  }

  const onDelete = (row: RobotModelOut) => {
    modal.confirm({
      title: '删除型号',
      content: `确定删除型号「${row.name}」？若有实例/参数关联将无法删除。`,
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => crud.remove(row.id),
    })
  }

  const columns: TableColumnsType<RobotModelOut> = [
    {
      title: '品牌',
      dataIndex: 'brand_id',
      width: 140,
      render: (v: number) => brandMap.get(v) || v,
    },
    {
      title: '控制器',
      dataIndex: 'controller_id',
      width: 150,
      render: (v: number | null) => (v ? controllerMap.get(v) || v : '-'),
    },
    { title: '型号代码', dataIndex: 'code', width: 160 },
    { title: '名称', dataIndex: 'name', width: 200 },
    {
      title: '负载(kg)',
      dataIndex: 'payload_kg',
      width: 100,
      render: (v: number | string | null) => v ?? '-',
    },
    {
      title: '臂展(mm)',
      dataIndex: 'reach_mm',
      width: 100,
      render: (v: number | string | null) => v ?? '-',
    },
    { title: '轴数', dataIndex: 'axes', width: 80, render: (v: number | null) => v ?? '-' },
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
            width: 140,
            fixed: 'right' as const,
            render: (_: unknown, r: RobotModelOut) => (
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
        title="机器人型号"
        actions={
          canWrite && (
            <Button type="primary" icon={<PlusOutlined />} onClick={onOpenCreate}>
              新增型号
            </Button>
          )
        }
      />

      <FilterBar
        form={queryForm}
        onSearch={() => crud.onSearch(queryForm.getFieldsValue() as RobotModelQuery)}
        onReset={() => {
          queryForm.resetFields()
          crud.onReset()
        }}
      >
        <Form.Item label="关键词" name="keyword">
          <Input placeholder="型号代码/名称" allowClear style={{ width: 220 }} />
        </Form.Item>
        <Form.Item label="品牌" name="brand_id">
          <Select placeholder="全部" allowClear options={brandOptions} style={{ width: 180 }} />
        </Form.Item>
        <Form.Item label="控制器" name="controller_id">
          <Select placeholder="全部" allowClear options={controllerOptions} style={{ width: 180 }} />
        </Form.Item>
      </FilterBar>

      <div className="table-card">
        <Table<RobotModelOut>
          rowKey="id"
          loading={crud.loading}
          dataSource={crud.list}
          columns={columns}
          pagination={false}
          scroll={{ x: 1050 }}
        />
        <Pager
          current={crud.page}
          pageSize={crud.pageSize}
          total={crud.total}
          onChange={crud.onPageChange}
        />
      </div>

      <Modal
        title={crud.isEdit ? '编辑型号' : '新增型号'}
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
          <Form.Item name="brand_id" label="品牌" rules={[{ required: true, message: '请选择品牌' }]}>
            <Select placeholder="选择品牌" showSearch optionFilterProp="label" options={brandOptions} />
          </Form.Item>
          <Form.Item name="controller_id" label="控制器">
            <Select placeholder="可选" allowClear showSearch optionFilterProp="label" options={controllerOptions} />
          </Form.Item>
          <Form.Item name="code" label="型号代码" rules={[{ required: true, message: '请输入型号代码' }]}>
            <Input placeholder="如 R-2000iC/210L" maxLength={50} />
          </Form.Item>
          <Form.Item name="name" label="型号名称" rules={[{ required: true, message: '请输入型号名称' }]}>
            <Input placeholder="型号名称" maxLength={100} />
          </Form.Item>
          <Form.Item name="payload_kg" label="额定负载(kg)">
            <InputNumber stringMode min={0} placeholder="如 210" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="reach_mm" label="臂展/工作半径(mm)">
            <InputNumber stringMode min={0} placeholder="如 3103" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="axes" label="轴数">
            <InputNumber min={1} max={10} placeholder="1-10" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="型号描述" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
