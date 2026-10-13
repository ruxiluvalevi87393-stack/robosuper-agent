import { createBrowserRouter, Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuthStore } from '../store/auth'
import BasicLayout from '../layouts/BasicLayout'
import Login from '../pages/Login'
import Dashboard from '../pages/Dashboard'
import BrandList from '../pages/System/Brand'
import ControllerList from '../pages/System/Controller'
import RobotModelList from '../pages/System/RobotModel'
import RobotInstanceList from '../pages/System/RobotInstance'
import ServoParamList from '../pages/System/ServoParam'
import PartInventoryList from '../pages/System/PartInventory'
import WorkOrderList from '../pages/System/WorkOrder'
import MaintenanceLogList from '../pages/System/MaintenanceLog'
import ServoParamHistoryList from '../pages/System/ServoParamHistory'
import UserList from '../pages/System/User'
import KnowledgeBase from '../pages/System/KnowledgeBase'
import KnowledgeChunks from '../pages/System/KnowledgeChunks'
import KnowledgeSearch from '../pages/System/KnowledgeSearch'
import Profile from '../pages/Profile'
import Workspace from '../pages/Workspace'

/** 未登录跳登录页，并记录来源路径便于登录后回跳 */
function RequireAuth({ children }: { children: ReactNode }) {
  const token = useAuthStore((s) => s.token)
  const location = useLocation()
  if (!token) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }
  return <>{children}</>
}

/** 角色守卫：无权限跳综合大屏 */
function RequireRole({ roles, children }: { roles: string[]; children: ReactNode }) {
  const role = useAuthStore((s) => s.user?.role)
  if (!role || !roles.includes(role)) {
    return <Navigate to="/dashboard" replace />
  }
  return <>{children}</>
}

const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  {
    path: '/',
    element: (
      <RequireAuth>
        <BasicLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', handle: { title: '综合大屏' }, element: <Dashboard /> },
      {
        path: 'workspace',
        handle: { title: '排查工作台' },
        element: (
          <RequireRole roles={['engineer', 'admin']}>
            <Workspace />
          </RequireRole>
        ),
      },
      { path: 'brands', handle: { title: '品牌管理' }, element: <BrandList /> },
      { path: 'controllers', handle: { title: '控制器管理' }, element: <ControllerList /> },
      { path: 'robot-models', handle: { title: '机器人型号' }, element: <RobotModelList /> },
      { path: 'robot-instances', handle: { title: '机器人实例' }, element: <RobotInstanceList /> },
      { path: 'servo-params', handle: { title: '伺服参数' }, element: <ServoParamList /> },
      { path: 'servo-param-history', handle: { title: '伺服参数历史' }, element: <ServoParamHistoryList /> },
      { path: 'part-inventory', handle: { title: '备件库存' }, element: <PartInventoryList /> },
      { path: 'work-orders', handle: { title: '工单管理' }, element: <WorkOrderList /> },
      { path: 'maintenance-logs', handle: { title: '维护日志' }, element: <MaintenanceLogList /> },
      {
        path: 'knowledge/documents',
        handle: { title: '知识库文档管理' },
        element: <KnowledgeBase />,
      },
      {
        path: 'knowledge/documents/:docId/chunks',
        handle: { title: '分块管理' },
        element: <KnowledgeChunks />,
      },
      { path: 'knowledge/search', handle: { title: '知识库检索测试' }, element: <KnowledgeSearch /> },
      {
        path: 'users',
        handle: { title: '用户管理' },
        element: (
          <RequireRole roles={['admin']}>
            <UserList />
          </RequireRole>
        ),
      },
      { path: 'profile', handle: { title: '个人中心' }, element: <Profile /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])

export default router
