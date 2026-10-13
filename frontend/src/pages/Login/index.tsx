import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { App, Button, Form, Input } from 'antd'
import { LockOutlined, MonitorOutlined, UserOutlined } from '@ant-design/icons'
import { login } from '../../api/auth'
import { useAuthStore } from '../../store/auth'

const bgStyle: React.CSSProperties = {
  minHeight: '100vh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: '#0a0a0a',
  backgroundImage:
    'radial-gradient(circle at 20% 30%, rgba(250, 219, 20, 0.06) 0%, transparent 40%),'
    + 'radial-gradient(circle at 80% 70%, rgba(250, 140, 22, 0.05) 0%, transparent 40%)',
}

export default function Login() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const location = useLocation()
  const token = useAuthStore((s) => s.token)
  const setAuth = useAuthStore((s) => s.setAuth)
  const [loading, setLoading] = useState(false)

  // 已登录则直接回跳
  if (token) return <Navigate to="/dashboard" replace />

  const from = (location.state as { from?: string } | null)?.from || '/dashboard'

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const data = await login(values)
      setAuth(data.access_token, data.user)
      message.success(`欢迎回来，${data.user.name || data.user.username}`)
      navigate(from, { replace: true })
    } catch (e: any) {
      message.error(e.response?.data?.message || e.response?.data?.detail || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={bgStyle}>
      <div
        style={{
          width: 400,
          padding: '40px 40px 32px',
          background: '#1f1f1f',
          border: '1px solid #303030',
          borderRadius: 8,
          boxShadow: '0 0 40px rgba(250, 219, 20, 0.1)',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <MonitorOutlined style={{ fontSize: 40, color: '#fadb14' }} />
          <h1
            style={{
              color: '#fadb14',
              fontSize: 28,
              margin: '12px 0 4px',
              letterSpacing: 2,
              fontWeight: 700,
            }}
          >
            RoboSuper Agent
          </h1>
          <p style={{ color: '#8c8c8c', fontSize: 13, margin: 0 }}>
            工业机器人运维智能体
          </p>
        </div>

        <Form onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              autoComplete="current-password"
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 12 }}>
            <Button
              type="primary"
              htmlType="submit"
              block
              loading={loading}
              style={{ fontWeight: 600 }}
            >
              登 录
            </Button>
          </Form.Item>
        </Form>

        <div style={{ textAlign: 'center', color: '#8c8c8c', fontSize: 12 }}>
          默认账号：admin / admin123
        </div>
      </div>
    </div>
  )
}
