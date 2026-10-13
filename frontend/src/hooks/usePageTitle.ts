import { useMatches } from 'react-router-dom'

/** 取当前路由 handle.title 作为页面标题 */
export function usePageTitle(): string {
  const matches = useMatches()
  const current = [...matches].reverse().find((m) => (m.handle as { title?: string } | undefined)?.title)
  return (current?.handle as { title?: string } | undefined)?.title || ''
}
