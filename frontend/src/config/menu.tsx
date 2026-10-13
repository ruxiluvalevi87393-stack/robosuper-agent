import type { ReactNode } from 'react'
import {
  ApartmentOutlined,
  AppstoreOutlined,
  ControlOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  DesktopOutlined,
  FileDoneOutlined,
  FileTextOutlined,
  HistoryOutlined,
  InboxOutlined,
  RobotOutlined,
  SearchOutlined,
  SettingOutlined,
  ShoppingOutlined,
  SlidersOutlined,
  TagsOutlined,
  TeamOutlined,
  ToolOutlined,
  UserOutlined,
} from '@ant-design/icons'

export interface AppMenuItem {
  key: string
  icon?: ReactNode
  label: ReactNode
  roles?: string[]
  children?: AppMenuItem[]
}

/** 业务菜单：key 即路由路径；roles 缺省 = 全部登录用户可见 */
export const menuItems: AppMenuItem[] = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '综合大屏' },
  { key: '/workspace', icon: <DesktopOutlined />, label: '排查工作台', roles: ['engineer', 'admin'] },
  {
    key: 'device-group',
    icon: <AppstoreOutlined />,
    label: '设备管理',
    children: [
      { key: '/brands', icon: <TagsOutlined />, label: '品牌管理' },
      { key: '/controllers', icon: <ControlOutlined />, label: '控制器管理' },
      { key: '/robot-models', icon: <ApartmentOutlined />, label: '机器人型号' },
      { key: '/robot-instances', icon: <RobotOutlined />, label: '机器人实例' },
    ],
  },
  {
    key: 'ops-group',
    icon: <ToolOutlined />,
    label: '运维管理',
    children: [
      { key: '/work-orders', icon: <FileDoneOutlined />, label: '工单管理' },
      { key: '/maintenance-logs', icon: <FileTextOutlined />, label: '维护日志' },
      { key: '/servo-params', icon: <SlidersOutlined />, label: '伺服参数' },
      { key: '/servo-param-history', icon: <HistoryOutlined />, label: '参数历史' },
    ],
  },
  {
    key: 'knowledge-group',
    icon: <DatabaseOutlined />,
    label: '知识库',
    children: [
      { key: '/knowledge/documents', icon: <FileTextOutlined />, label: '文档管理' },
      { key: '/knowledge/search', icon: <SearchOutlined />, label: '检索测试' },
    ],
  },
  {
    key: 'part-group',
    icon: <ShoppingOutlined />,
    label: '备件管理',
    children: [{ key: '/part-inventory', icon: <InboxOutlined />, label: '备件库存' }],
  },
  {
    key: 'system-group',
    icon: <SettingOutlined />,
    label: '系统管理',
    children: [{ key: '/users', icon: <TeamOutlined />, label: '用户管理', roles: ['admin'] }],
  },
  { key: '/profile', icon: <UserOutlined />, label: '个人中心' },
]

/** 按角色过滤后的菜单（roles 缺省 = 全部可见） */
export function getMenus(hasRole: (...roles: string[]) => boolean): AppMenuItem[] {
  const filterItems = (items: AppMenuItem[]): AppMenuItem[] =>
    items
      .filter((m) => !m.roles || hasRole(...m.roles))
      .map(({ roles, children, ...rest }) => ({
        ...rest,
        children: children ? filterItems(children) : undefined,
      }))
      .filter((m) => m.children === undefined || m.children.length > 0)
  return filterItems(menuItems)
}
