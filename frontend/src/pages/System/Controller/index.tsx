import { App, Button, Form, Input, Modal, Select, Table } from 'antd'
import type { TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import PageHeader from '../../../components/PageHeader'
import FilterBar from '../../../components/FilterBar'
import Pager from '../../../components/Pager'
import { createController, deleteController, listControllers, updateController } from '../../../api/controller'
import type { ControllerCreatePayload, ControllerOut, ControllerQuery, ControllerUpdatePayload } from '../../../api/controller'
import { useCrud } from '../../../hooks/useCrud'
import { usePermission } from '../../../hooks/usePermission'
import { useBrandOptions } from '../../../hooks/useOptions'

export default function ControllerList() {
  const { modal } = App.useApp()
  const { hasRole } = usePermission()
  const canWrite = hasRole('admin')
  const [form] = Form.useForm()
  const [queryForm] = Form.useForm()
  const brandOptions = useBrandOptions()
  const brandMap = new Map(brandOptions.map((o) => [o.value, o.label]))

  const crud = useCrud<ControllerOut, ControllerQuery, ControllerCreatePayload, ControllerUpdatePayload>(
    { list: listControllers, create: createController, update: updateController, remove: deleteController },
    { keyword: undefined, brand_id: undefined },
  )

  const onOpenCreate = () => {
    form.resetFields()
    crud.openCreate()
  }

  const onOpenEdit = (row: ControllerOut) => {
    form.resetFields()
    form.setFieldsValue(row)
    crud.openEdit(row)
  }

  const onSubmit = async () => {
    const values = form.getFieldsValue()
    await crud.save(values)
  }

  const onDelete = (row: ControllerOut) => {
    modal.confirm({
      title: '删除控制器',
      content: `确定删除控制器「${row.name}」？若有型号关联将无法删除。`,
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => crud.remove(row.id),
    })
  }

  const columns: TableColumnsType<ControllerOut> = [
    {
      title: '所属品牌',
      dataIndex: 'brand_id',
      width: 160,
      render: (v: number) => brandMap.get(v) || v,
    },
    { title: '控制器代码', dataIndex: 'code', width: 140 },
    { title: '名称', dataIndex: 'name', width: 200 },
    { title: '系列', dataIndex: 'series', width: 120, render: (v: string) => v || '-' },
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
            render: (_: unknown, r: ControllerOut) => (
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
        title="控制器管理"
        actions={
          canWrite && (
            <Button type="primary" icon={<PlusOutlined />} onClick={onOpenCreate}>
              新增控制器
            </Button>
          )
        }
      />

      <FilterBar
        form={queryForm}
        onSearch={() => crud.onSearch(queryForm.getFieldsValue() as ControllerQuery)}
        onReset={() => {
          queryForm.resetFields()
          crud.onReset()
        }}
      >
        <Form.Item label="关键词" name="keyword">
          <Input placeholder="代码/名称" allowClear style={{ width: 220 }} />
        </Form.Item>
        <Form.Item label="品牌" name="brand_id">
          <Select placeholder="全部" allowClear options={brandOptions} style={{ width: 180 }} />
        </Form.Item>
      </FilterBar>

      <div className="table-card">
        <Table<ControllerOut>
          rowKey="id"
          loading={crud.loading}
          dataSource={crud.list}
          columns={columns}
          pagination={false}
          scroll={{ x: 900 }}
        />
        <Pager
          current={crud.page}
          pageSize={crud.pageSize}
          total={crud.total}
          onChange={crud.onPageChange}
        />
      </div>

      <Modal
        title={crud.isEdit ? '编辑控制器' : '新增控制器'}
        width={520}
        open={crud.modalOpen}
        confirmLoading={crud.submitting}
        okText="确定"
        cancelText="取消"
        forceRender
        onOk={() => form.submit()}
        onCancel={() => crud.setModalOpen(false)}
      >
        <Form form={form} layout="vertical" onFinish={onSubmit} style={{ marginTop: 8 }}>
          <Form.Item name="brand_id" label="所属品牌" rules={[{ required: true, message: '请选择品牌' }]}>
            <Select placeholder="选择品牌" showSearch optionFilterProp="label" options={brandOptions} />
          </Form.Item>
          <Form.Item name="code" label="控制器代码" rules={[{ required: true, message: '请输入控制器代码' }]}>
            <Input placeholder="品牌内唯一" maxLength={30} />
          </Form.Item>
          <Form.Item name="name" label="控制器名称" rules={[{ required: true, message: '请输入控制器名称' }]}>
            <Input placeholder="控制器名称" maxLength={100} />
          </Form.Item>
          <Form.Item name="series" label="系列">
            <Input placeholder="如 R-30iB" maxLength={50} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="控制器描述" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
