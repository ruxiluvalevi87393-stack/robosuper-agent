import { useEffect, useMemo, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { App, Button, Dropdown, Layout, Menu, Tag } from 'antd'
import {
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MonitorOutlined,
  UserOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { useAuthStore } from '../store/auth'
import { usePermission } from '../hooks/usePermission'
import { usePageTitle } from '../hooks/usePageTitle'
import { getMenus, menuItems } from '../config/menu'
import type { AppMenuItem } from '../config/menu'

const { Sider, Header, Content } = Layout

const roleLabel: Record<string, string> = {
  admin: '管理员',
  engineer: '工程师',
  viewer: '只读',
}

/** 返回当前路径所属的所有分组 key（用于自动展开对应子菜单） */
function groupKeysOf(path: string): string[] {
  return menuItems
    .filter((m) => m.children?.some((c) => c.key === path))
    .map((m) => m.key)
}

export default function BasicLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { message, modal } = App.useApp()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const { hasRole } = usePermission()
  const title = usePageTitle()

  const [collapsed, setCollapsed] = useState(false)
  const [openKeys, setOpenKeys] = useState<string[]>(() => groupKeysOf(location.pathname))

  const items = useMemo<AppMenuItem[]>(() => getMenus(hasRole), [hasRole])

  // 路由变化时自动展开对应分组
  useEffect(() => {
    const needed = groupKeysOf(location.pathname)
    setOpenKeys((prev) => [...new Set([...prev, ...needed])])
  }, [location.pathname])

  const onMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key.startsWith('/')) navigate(key)
  }

  const onLogout = () => {
    modal.confirm({
      title: '提示',
      content: '确定退出登录吗？',
      okText: '退出',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        logout()
        message.success('已退出登录')
        navigate('/login', { replace: true })
      },
    })
  }

  const userMenu: MenuProps['items'] = [
    { key: 'profile', icon: <UserOutlined />, label: '个人中心' },
    { type: 'divider' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
  ]

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider
        width={220}
        collapsedWidth={64}
        collapsed={collapsed}
        trigger={null}
        theme="dark"
        style={{ borderRight: '1px solid #303030', display: 'flex', flexDirection: 'column' }}
      >
        <div className="sidebar-logo" onClick={() => navigate('/dashboard')}>
          <MonitorOutlined style={{ fontSize: 24, color: '#fadb14' }} />
          {!collapsed && <span className="sidebar-logo-text">RoboSuper</span>}
        </div>
        <Menu
          className="sidebar-menu"
          theme="dark"
          mode="inline"
          inlineCollapsed={collapsed}
          selectedKeys={[location.pathname]}
          openKeys={collapsed ? undefined : openKeys}
          onOpenChange={setOpenKeys}
          onClick={onMenuClick}
          items={items as MenuProps['items']}
        />
      </Sider>
      <Layout>
        <Header className="topbar">
          <div className="topbar-left">
            <span className="collapse-btn" onClick={() => setCollapsed(!collapsed)}>
              {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </span>
            <span className="page-title">{title || 'RoboSuper Agent'}</span>
          </div>
          <div className="topbar-right">
            <Dropdown menu={{ items: userMenu, onClick: ({ key }) => key === 'profile' ? navigate('/profile') : onLogout() }}>
              <span className="user-info">
                <UserOutlined />
                <span>{user?.username || '--'}</span>
                <Tag color="gold" style={{ marginInlineEnd: 0 }}>
                  {roleLabel[user?.role || ''] || user?.role}
                </Tag>
              </span>
            </Dropdown>
          </div>
        </Header>
        <Content className="main-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
