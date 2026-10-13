import { useState } from 'react'
import { App, Button, Descriptions, Form, Input, Tag } from 'antd'
import dayjs from 'dayjs'
import PageHeader from '../../components/PageHeader'
import { changePassword } from '../../api/auth'
import { useAuthStore } from '../../store/auth'
import { getApiErrorMessage } from '../../utils/error'

const roleLabels: Record<string, string> = {
  admin: '管理员',
  engineer: '工程师',
  viewer: '只读',
}

export default function Profile() {
  const { message } = App.useApp()
  const user = useAuthStore((s) => s.user)
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)

  const onSubmit = async () => {
    setLoading(true)
    try {
      const values = await form.validateFields()
      await changePassword({ old_password: values.old_password, new_password: values.new_password })
      message.success('密码修改成功')
      form.resetFields()
    } catch (e: any) {
      if (e?.errorFields) return // 校验失败
      message.error(getApiErrorMessage(e, '密码修改失败'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <PageHeader title="个人中心" />

      <div className="table-card" style={{ maxWidth: 720 }}>
        <Descriptions
          column={1}
          labelStyle={{ width: 120, color: '#8c8c8c' }}
          contentStyle={{ color: '#fafafa' }}
          items={[
            { key: 'username', label: '用户名', children: user?.username || '-' },
            {
              key: 'name',
              label: '姓名',
              children: user?.name || '-',
            },
            {
              key: 'role',
              label: '角色',
              children: <Tag color="gold">{roleLabels[user?.role || ''] || user?.role}</Tag>,
            },
            { key: 'email', label: '邮箱', children: user?.email || '-' },
            { key: 'phone', label: '手机号', children: user?.phone || '-' },
            {
              key: 'created_at',
              label: '创建时间',
              children: user?.created_at
                ? dayjs(user.created_at).format('YYYY-MM-DD HH:mm')
                : '-',
            },
          ]}
        />
      </div>

      <div className="table-card" style={{ maxWidth: 720, marginTop: 12 }}>
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
          修改密码
        </h2>
        <Form form={form} layout="vertical" style={{ maxWidth: 420 }} onFinish={onSubmit}>
          <Form.Item
            name="old_password"
            label="原密码"
            rules={[{ required: true, message: '请输入原密码' }]}
          >
            <Input.Password placeholder="原密码" autoComplete="current-password" />
          </Form.Item>
          <Form.Item
            name="new_password"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码至少 6 位' },
            ]}
          >
            <Input.Password placeholder="至少 6 位" autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认新密码"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) {
                    return Promise.resolve()
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password placeholder="再次输入新密码" autoComplete="new-password" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={loading}>
              确认修改
            </Button>
          </Form.Item>
        </Form>
      </div>
    </div>
  )
}
