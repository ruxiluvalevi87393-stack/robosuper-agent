import { useCallback, useEffect, useState } from 'react'
import { App, Button, Form, Input, Modal, Pagination, Radio, Select, Switch, Table, Tag } from 'antd'
import type { TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import PageHeader from '../../../components/PageHeader'
import { createUser, deleteUser, listUsers, updateUser } from '../../../api/user'
import type { UserCreatePayload, UserQuery, UserUpdatePayload } from '../../../api/user'
import type { UserOut } from '../../../store/auth'

const roleLabels: Record<string, string> = {
  admin: '管理员',
  engineer: '工程师',
  viewer: '只读',
}

const roleTagColor: Record<string, string> = {
  admin: 'gold',
  engineer: 'cyan',
  viewer: 'default',
}

const roleOptions = [
  { value: 'admin', label: '管理员' },
  { value: 'engineer', label: '工程师' },
  { value: 'viewer', label: '只读' },
]

const defaultFilters: UserQuery = { keyword: undefined, role: undefined, is_active: undefined }

export default function UserList() {
  const { message, modal } = App.useApp()
  const [queryForm] = Form.useForm()
  const [form] = Form.useForm()
  const [resetForm] = Form.useForm()

  const [list, setList] = useState<UserOut[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [filters, setFilters] = useState<UserQuery>(defaultFilters)

  const [modalOpen, setModalOpen] = useState(false)
  const [isEdit, setIsEdit] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const [resetOpen, setResetOpen] = useState(false)
  const [resetId, setResetId] = useState<number | null>(null)
  const [resetting, setResetting] = useState(false)

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listUsers({
        page,
        page_size: pageSize,
        keyword: filters.keyword || undefined,
        role: filters.role || undefined,
        is_active: filters.is_active,
      })
      setList(data.items)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, filters])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const onSearch = () => {
    setPage(1)
    setFilters(queryForm.getFieldsValue() as UserQuery)
  }

  const onReset = () => {
    queryForm.resetFields()
    setPage(1)
    setFilters({ ...defaultFilters })
  }

  const openCreate = () => {
    setIsEdit(false)
    setEditingId(null)
    form.resetFields()
    form.setFieldsValue({ role: 'viewer', is_active: true })
    setModalOpen(true)
  }

  const openEdit = (record: UserOut) => {
    setIsEdit(true)
    setEditingId(record.id)
    form.resetFields()
    form.setFieldsValue({
      username: record.username,
      password: undefined,
      role: record.role,
      name: record.name,
      email: record.email,
      phone: record.phone,
      is_active: record.is_active,
    })
    setModalOpen(true)
  }

  const onSubmit = async () => {
    setSubmitting(true)
    try {
      const values = form.getFieldsValue()
      if (isEdit) {
        const payload: UserUpdatePayload = { ...values }
        if (!payload.password) delete payload.password
        await updateUser(editingId!, payload)
        message.success('更新成功')
      } else {
        await createUser(values as UserCreatePayload)
        message.success('创建成功')
      }
      setModalOpen(false)
      fetchList()
    } catch {
      // 校验或拦截器已提示
    } finally {
      setSubmitting(false)
    }
  }

  const onToggleStatus = async (record: UserOut, checked: boolean) => {
    try {
      await updateUser(record.id, { is_active: checked })
      message.success(checked ? '已启用' : '已禁用')
    } catch {
      // 失败时通过刷新回滚开关状态
    } finally {
      fetchList()
    }
  }

  const onDelete = (record: UserOut) => {
    modal.confirm({
      title: '删除用户',
      content: `确定删除用户「${record.username}」？删除后不可恢复。`,
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        await deleteUser(record.id)
        message.success('删除成功')
        fetchList()
      },
    })
  }

  const openReset = (record: UserOut) => {
    setResetId(record.id)
    resetForm.resetFields()
    resetForm.setFieldsValue({ username: record.username })
    setResetOpen(true)
  }

  const submitReset = async () => {
    setResetting(true)
    try {
      const values = await resetForm.validateFields()
      await updateUser(resetId!, { password: values.password })
      message.success('密码已重置')
      setResetOpen(false)
      fetchList()
    } catch {
      // 校验或拦截器已提示
    } finally {
      setResetting(false)
    }
  }

  const columns: TableColumnsType<UserOut> = [
    { title: '用户名', dataIndex: 'username', width: 140 },
    {
      title: '角色',
      dataIndex: 'role',
      width: 110,
      render: (_, r) => (
        <Tag color={roleTagColor[r.role] || 'default'}>{roleLabels[r.role] || r.role}</Tag>
      ),
    },
    { title: '姓名', dataIndex: 'name', width: 120, render: (v: string) => v || '-' },
    { title: '邮箱', dataIndex: 'email', ellipsis: true, render: (v: string) => v || '-' },
    { title: '手机号', dataIndex: 'phone', width: 140, render: (v: string) => v || '-' },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 80,
      render: (_, r) => <Switch checked={r.is_active} onChange={(c) => onToggleStatus(r, c)} />,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'op',
      width: 190,
      fixed: 'right',
      render: (_, r) => (
        <div style={{ display: 'flex', gap: 8, whiteSpace: 'nowrap' }}>
          <Button size="small" type="primary" onClick={() => openEdit(r)}>
            编辑
          </Button>
          <Button size="small" onClick={() => openReset(r)}>
            重置密码
          </Button>
          <Button size="small" danger onClick={() => onDelete(r)}>
            删除
          </Button>
        </div>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="用户管理"
        actions={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新增用户
          </Button>
        }
      />

      <div className="filter-card">
        <Form form={queryForm} layout="inline">
          <Form.Item label="关键词" name="keyword">
            <Input placeholder="用户名/邮箱/手机号" allowClear style={{ width: 240 }} />
          </Form.Item>
          <Form.Item label="角色" name="role">
            <Select placeholder="全部" allowClear options={roleOptions} style={{ width: 140 }} />
          </Form.Item>
          <Form.Item label="状态" name="is_active">
            <Select
              placeholder="全部"
              allowClear
              options={[
                { value: true, label: '启用' },
                { value: false, label: '禁用' },
              ]}
              style={{ width: 120 }}
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 16 }}>
            <Button type="primary" onClick={onSearch}>
              查询
            </Button>
            <Button style={{ marginLeft: 8 }} onClick={onReset}>
              重置
            </Button>
          </Form.Item>
        </Form>
      </div>

      <div className="table-card">
        <Table<UserOut>
          rowKey="id"
          loading={loading}
          dataSource={list}
          columns={columns}
          pagination={false}
          scroll={{ x: 1000 }}
        />
        <div className="pager">
          <Pagination
            current={page}
            pageSize={pageSize}
            total={total}
            showSizeChanger
            showQuickJumper
            showTotal={(t) => `共 ${t} 条`}
            pageSizeOptions={[10, 20, 50]}
            onChange={(p, ps) => {
              setPage(p)
              setPageSize(ps)
            }}
          />
        </div>
      </div>

      <Modal
        title={isEdit ? '编辑用户' : '新增用户'}
        width={560}
        open={modalOpen}
        confirmLoading={submitting}
        okText="确定"
        cancelText="取消"
        forceRender
        onOk={() => form.submit()}
        onCancel={() => setModalOpen(false)}
      >
        <Form form={form} layout="vertical" onFinish={onSubmit} style={{ marginTop: 8 }}>
          <Form.Item
            name="username"
            label="用户名"
            rules={isEdit ? [] : [{ required: true, message: '请输入用户名' }]}
          >
            <Input placeholder="用户名" disabled={isEdit} />
          </Form.Item>
          <Form.Item
            name="password"
            label={isEdit ? '新密码' : '密码'}
            rules={
              isEdit
                ? [{ min: 6, message: '密码至少 6 位' }]
                : [
                    { required: true, message: '请输入密码' },
                    { min: 6, message: '密码至少 6 位' },
                  ]
            }
          >
            <Input.Password placeholder={isEdit ? '留空则不修改密码' : '至少 6 位'} autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
            <Select options={roleOptions} />
          </Form.Item>
          <Form.Item name="name" label="姓名">
            <Input placeholder="姓名" />
          </Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ type: 'email', message: '邮箱格式不正确' }]}>
            <Input placeholder="邮箱" />
          </Form.Item>
          <Form.Item name="phone" label="手机号">
            <Input placeholder="手机号" />
          </Form.Item>
          <Form.Item name="is_active" label="状态">
            <Radio.Group
              options={[
                { label: '启用', value: true },
                { label: '禁用', value: false },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="重置密码"
        width={440}
        open={resetOpen}
        confirmLoading={resetting}
        okText="确定"
        cancelText="取消"
        forceRender
        onOk={() => resetForm.submit()}
        onCancel={() => setResetOpen(false)}
      >
        <Form form={resetForm} layout="vertical" onFinish={submitReset} style={{ marginTop: 8 }}>
          <Form.Item name="username" label="用户名">
            <Input disabled />
          </Form.Item>
          <Form.Item
            name="password"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码至少 6 位' },
            ]}
          >
            <Input.Password placeholder="至少 6 位" autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
