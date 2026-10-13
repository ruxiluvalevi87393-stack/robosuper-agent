import { App, Button, Form, Input, InputNumber, Modal, Select, Switch, Table, Tag } from 'antd'
import type { TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import PageHeader from '../../../components/PageHeader'
import FilterBar from '../../../components/FilterBar'
import Pager from '../../../components/Pager'
import {
  createPartInventory,
  deletePartInventory,
  listPartInventory,
  updatePartInventory,
} from '../../../api/partInventory'
import type {
  PartInventoryCreatePayload,
  PartInventoryOut,
  PartInventoryQuery,
  PartInventoryUpdatePayload,
} from '../../../api/partInventory'
import { useCrud } from '../../../hooks/useCrud'
import { usePermission } from '../../../hooks/usePermission'
import { useBrandOptions } from '../../../hooks/useOptions'

export default function PartInventoryList() {
  const { modal } = App.useApp()
  const { hasRole } = usePermission()
  const canWrite = hasRole('admin')
  const [form] = Form.useForm()
  const [queryForm] = Form.useForm()
  const brandOptions = useBrandOptions()
  const brandMap = new Map(brandOptions.map((o) => [o.value, o.label]))

  const crud = useCrud<
    PartInventoryOut,
    PartInventoryQuery,
    PartInventoryCreatePayload,
    PartInventoryUpdatePayload
  >(
    {
      list: listPartInventory,
      create: createPartInventory,
      update: updatePartInventory,
      remove: deletePartInventory,
    },
    { keyword: undefined, brand_id: undefined, category: undefined, warehouse: undefined, low_stock: undefined },
  )

  const onOpenCreate = () => {
    form.resetFields()
    form.setFieldsValue({ quantity: 0, safety_stock: 0 })
    crud.openCreate()
  }

  const onOpenEdit = (row: PartInventoryOut) => {
    form.resetFields()
    form.setFieldsValue({ ...row, compatible_brands: row.compatible_brands || [] })
    crud.openEdit(row)
  }

  const onSubmit = async () => {
    const values = form.getFieldsValue()
    await crud.save(values)
  }

  const onDelete = (row: PartInventoryOut) => {
    modal.confirm({
      title: '删除备件',
      content: `确定删除备件「${row.part_no} ${row.name}」？`,
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => crud.remove(row.id),
    })
  }

  const columns: TableColumnsType<PartInventoryOut> = [
    { title: '图号/编号', dataIndex: 'part_no', width: 150 },
    { title: '名称', dataIndex: 'name', width: 200 },
    {
      title: '主品牌',
      dataIndex: 'brand_id',
      width: 120,
      render: (v: number | null) => (v ? brandMap.get(v) || v : '-'),
    },
    { title: '分类', dataIndex: 'category', width: 100, render: (v: string) => v || '-' },
    {
      title: '单价',
      dataIndex: 'price',
      width: 110,
      render: (v: number | string | null) => (v == null ? '-' : `¥${v}`),
    },
    {
      title: '库存',
      dataIndex: 'quantity',
      width: 90,
      render: (v: number, r: PartInventoryOut) =>
        v <= r.safety_stock ? <Tag color="red">{v}</Tag> : v,
    },
    { title: '安全库存', dataIndex: 'safety_stock', width: 90 },
    { title: '仓库', dataIndex: 'warehouse', width: 110 },
    { title: '货位', dataIndex: 'location', width: 100, render: (v: string) => v || '-' },
    {
      title: '采购周期',
      dataIndex: 'lead_time_days',
      width: 100,
      render: (v: number | null) => (v == null ? '-' : `${v} 天`),
    },
    ...(canWrite
      ? [
          {
            title: '操作',
            key: 'op',
            width: 140,
            fixed: 'right' as const,
            render: (_: unknown, r: PartInventoryOut) => (
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
        title="备件库存"
        actions={
          canWrite && (
            <Button type="primary" icon={<PlusOutlined />} onClick={onOpenCreate}>
              新增备件
            </Button>
          )
        }
      />

      <FilterBar
        form={queryForm}
        onSearch={() => crud.onSearch(queryForm.getFieldsValue() as PartInventoryQuery)}
        onReset={() => {
          queryForm.resetFields()
          crud.onReset()
        }}
      >
        <Form.Item label="关键词" name="keyword">
          <Input placeholder="图号/名称" allowClear style={{ width: 220 }} />
        </Form.Item>
        <Form.Item label="品牌" name="brand_id">
          <Select placeholder="全部" allowClear showSearch optionFilterProp="label" options={brandOptions} style={{ width: 170 }} />
        </Form.Item>
        <Form.Item label="分类" name="category">
          <Input placeholder="如 电机" allowClear style={{ width: 120 }} />
        </Form.Item>
        <Form.Item label="仓库" name="warehouse">
          <Input placeholder="如 W1" allowClear style={{ width: 110 }} />
        </Form.Item>
        <Form.Item label="仅看缺货" name="low_stock" valuePropName="checked">
          <Switch />
        </Form.Item>
      </FilterBar>

      <div className="table-card">
        <Table<PartInventoryOut>
          rowKey="id"
          loading={crud.loading}
          dataSource={crud.list}
          columns={columns}
          pagination={false}
          scroll={{ x: 1200 }}
        />
        <Pager
          current={crud.page}
          pageSize={crud.pageSize}
          total={crud.total}
          onChange={crud.onPageChange}
        />
      </div>

      <Modal
        title={crud.isEdit ? '编辑备件' : '新增备件'}
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
          <Form.Item name="part_no" label="图号/备件编号" rules={[{ required: true, message: '请输入图号' }]}>
            <Input placeholder="EPC 图号" maxLength={50} />
          </Form.Item>
          <Form.Item name="name" label="备件名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="备件名称" maxLength={200} />
          </Form.Item>
          <Form.Item name="brand_id" label="主品牌">
            <Select placeholder="可选" allowClear showSearch optionFilterProp="label" options={brandOptions} />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Input placeholder="如 电机/编码器" maxLength={50} />
          </Form.Item>
          <Form.Item name="price" label="单价">
            <InputNumber stringMode min={0} placeholder="如 3200.5" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="lead_time_days" label="采购周期(天)">
            <InputNumber min={0} placeholder="如 30" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="compatible_brands" label="兼容品牌">
            <Select mode="tags" placeholder="回车添加，如 FANUC" open={false} suffixIcon={null} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="quantity" label="库存数量" rules={[{ required: true, message: '请输入库存数量' }]}>
            <InputNumber min={0} placeholder="0" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="warehouse" label="所属仓库" rules={[{ required: true, message: '请输入仓库' }]}>
            <Input placeholder="如 W1" maxLength={50} />
          </Form.Item>
          <Form.Item name="location" label="货位">
            <Input placeholder="如 A-01-03" maxLength={50} />
          </Form.Item>
          <Form.Item name="safety_stock" label="安全库存阈值" rules={[{ required: true, message: '请输入安全库存' }]}>
            <InputNumber min={0} placeholder="0" style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
