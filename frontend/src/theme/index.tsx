/**
 * 黑金矿山风主题（全站深色，对齐参考项目 MineGuard）：
 * - 底色 #0a0a0a / 面板 #1f1f1f / 抬升 #262626
 * - 主色金色 #fadb14（hover #ffc53d）
 * - 文字 #fafafa / #d9d9d9 / #8c8c8c
 * - 边框 #303030
 */
import type { ReactNode } from 'react'
import { App as AntApp, ConfigProvider, theme as antdTheme } from 'antd'
import zhCN from 'antd/locale/zh_CN'

const token = {
  colorPrimary: '#fadb14',
  colorInfo: '#fadb14',
  colorLink: '#fadb14',
  colorSuccess: '#389e0d',
  colorWarning: '#fa8c16',
  colorError: '#cf1322',
  colorBgBase: '#0a0a0a',
  colorBgContainer: '#1f1f1f',
  colorBgElevated: '#262626',
  colorBgLayout: '#0a0a0a',
  colorTextBase: '#fafafa',
  colorText: '#d9d9d9',
  colorTextSecondary: '#8c8c8c',
  colorTextTertiary: '#595959',
  colorBorder: '#303030',
  colorBorderSecondary: '#262626',
  borderRadius: 4,
  fontSize: 14,
}

// 组件级微调，让整体质感贴近参考项目
const components = {
  Button: {
    primaryColor: '#0a0a0a', // 金色按钮上的文字用深色
    defaultBg: '#1f1f1f',
    defaultBorderColor: '#303030',
    defaultColor: '#d9d9d9',
    defaultHoverBg: '#262626',
    defaultHoverBorderColor: '#595959',
    defaultHoverColor: '#fafafa',
    dangerColor: '#cf1322',
  },
  Layout: {
    siderBg: '#0a0a0a',
    headerBg: '#1f1f1f',
    bodyBg: '#0a0a0a',
  },
  Menu: {
    darkItemBg: '#0a0a0a',
    darkSubMenuItemBg: '#0a0a0a',
    darkItemColor: '#d9d9d9',
    darkItemHoverColor: '#fadb14',
    darkItemHoverBg: '#1f1f1f',
    darkItemSelectedColor: '#fadb14',
    darkItemSelectedBg: 'rgba(250, 219, 20, 0.12)',
    itemBorderRadius: 0,
    itemMarginInline: 0,
    itemHeight: 44,
  },
  Table: {
    headerBg: '#1f1f1f',
    headerColor: '#d9d9d9',
    headerSplitColor: '#303030',
    rowHoverBg: '#171717',
    borderColor: '#303030',
  },
  Modal: {
    contentBg: '#1f1f1f',
    headerBg: '#1f1f1f',
    titleColor: '#fafafa',
    footerBg: '#1f1f1f',
  },
  Select: {
    optionSelectedBg: 'rgba(250, 219, 20, 0.15)',
    optionSelectedColor: '#fadb14',
  },
  Pagination: {
    itemActiveBg: 'rgba(250, 219, 20, 0.12)',
  },
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: antdTheme.darkAlgorithm,
        token,
        components,
      }}
    >
      <AntApp>{children}</AntApp>
    </ConfigProvider>
  )
}
