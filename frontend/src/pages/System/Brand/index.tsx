import { App, Button, Form, Input, Modal, Table } from 'antd'
import type { TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import PageHeader from '../../../components/PageHeader'
import FilterBar from '../../../components/FilterBar'
import Pager from '../../../components/Pager'
import { createBrand, deleteBrand, listBrands, updateBrand } from '../../../api/brand'
import type { BrandCreatePayload, BrandOut, BrandQuery, BrandUpdatePayload } from '../../../api/brand'
import { useCrud } from '../../../hooks/useCrud'
import { usePermission } from '../../../hooks/usePermission'

export default function BrandList() {
  const { modal } = App.useApp()
  const { hasRole } = usePermission()
  const canWrite = hasRole('admin')
  const [form] = Form.useForm()
  const [queryForm] = Form.useForm()

  const crud = useCrud<BrandOut, BrandQuery, BrandCreatePayload, BrandUpdatePayload>(
    { list: listBrands, create: createBrand, update: updateBrand, remove: deleteBrand },
    { keyword: undefined },
  )

  const onOpenCreate = () => {
    form.resetFields()
    crud.openCreate()
  }

  const onOpenEdit = (row: BrandOut) => {
    form.resetFields()
    form.setFieldsValue(row)
    crud.openEdit(row)
  }

  const onSubmit = async () => {
    const values = form.getFieldsValue()
    await crud.save(values)
  }

  const onDelete = (row: BrandOut) => {
    modal.confirm({
      title: '删除品牌',
      content: `确定删除品牌「${row.name}」？若有控制器/型号关联将无法删除。`,
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => crud.remove(row.id),
    })
  }

  const columns: TableColumnsType<BrandOut> = [
    { title: '品牌代码', dataIndex: 'code', width: 140 },
    { title: '品牌名称', dataIndex: 'name', width: 160 },
    { title: '所属国家', dataIndex: 'country', width: 120, render: (v: string) => v || '-' },
    { title: '描述', dataIndex: 'description', ellipsis: true, render: (v: string) => v || '-' },
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
            render: (_: unknown, r: BrandOut) => (
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
        title="品牌管理"
        actions={
          canWrite && (
            <Button type="primary" icon={<PlusOutlined />} onClick={onOpenCreate}>
              新增品牌
            </Button>
          )
        }
      />

      <FilterBar
        form={queryForm}
        onSearch={() => crud.onSearch(queryForm.getFieldsValue() as BrandQuery)}
        onReset={() => {
          queryForm.resetFields()
          crud.onReset()
        }}
      >
        <Form.Item label="关键词" name="keyword">
          <Input placeholder="代码/名称/国家" allowClear style={{ width: 240 }} />
        </Form.Item>
      </FilterBar>

      <div className="table-card">
        <Table<BrandOut>
          rowKey="id"
          loading={crud.loading}
          dataSource={crud.list}
          columns={columns}
          pagination={false}
          scroll={{ x: 800 }}
        />
        <Pager
          current={crud.page}
          pageSize={crud.pageSize}
          total={crud.total}
          onChange={crud.onPageChange}
        />
      </div>

      <Modal
        title={crud.isEdit ? '编辑品牌' : '新增品牌'}
        width={480}
        open={crud.modalOpen}
        confirmLoading={crud.submitting}
        okText="确定"
        cancelText="取消"
        forceRender
        onOk={() => form.submit()}
        onCancel={() => crud.setModalOpen(false)}
      >
        <Form form={form} layout="vertical" onFinish={onSubmit} style={{ marginTop: 8 }}>
          <Form.Item name="code" label="品牌代码" rules={[{ required: true, message: '请输入品牌代码' }]}>
            <Input placeholder="如 FANUC" maxLength={20} />
          </Form.Item>
          <Form.Item name="name" label="品牌名称" rules={[{ required: true, message: '请输入品牌名称' }]}>
            <Input placeholder="品牌名称" maxLength={50} />
          </Form.Item>
          <Form.Item name="country" label="所属国家">
            <Input placeholder="如 日本" maxLength={50} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="品牌描述" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
