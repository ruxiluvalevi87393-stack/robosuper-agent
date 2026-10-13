import { useEffect, useRef, useState } from 'react'
import { fetchAll } from '../api/helpers'
import { listBrands } from '../api/brand'
import { listControllers } from '../api/controller'
import { listRobotModels } from '../api/robotModel'
import { listRobotInstances } from '../api/robotInstance'
import { listUsers } from '../api/user'
import type { BrandOut } from '../api/brand'
import type { ControllerOut } from '../api/controller'
import type { RobotModelOut } from '../api/robotModel'
import type { RobotInstanceOut } from '../api/robotInstance'
import type { UserOut } from '../store/auth'

export interface OptionItem {
  value: number | string
  label: string
}

function useFetchAll<T>(
  fetcher: () => Promise<T[]>,
  map: (item: T) => OptionItem,
): OptionItem[] {
  const [options, setOptions] = useState<OptionItem[]>([])
  // fetcher/map 由页面内联传入（每次渲染都是新函数），用 ref 持有最新值，仅挂载时查询一次
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher
  const mapRef = useRef(map)
  mapRef.current = map
  useEffect(() => {
    let alive = true
    fetcherRef
      .current()
      .then((items) => alive && setOptions(items.map(mapRef.current)))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])
  return options
}

export const useBrandOptions = () =>
  useFetchAll<BrandOut>(
    () => fetchAll((p) => listBrands(p)),
    (b) => ({ value: b.id, label: `${b.name}（${b.code}）` }),
  )

export const useControllerOptions = () =>
  useFetchAll<ControllerOut>(
    () => fetchAll((p) => listControllers(p)),
    (c) => ({ value: c.id, label: c.name }),
  )

export const useRobotModelOptions = () =>
  useFetchAll<RobotModelOut>(
    () => fetchAll((p) => listRobotModels(p)),
    (m) => ({ value: m.id, label: `${m.name}（${m.code}）` }),
  )

export const useRobotInstanceOptions = () =>
  useFetchAll<RobotInstanceOut>(
    () => fetchAll((p) => listRobotInstances(p)),
    (i) => ({ value: i.id, label: i.asset_no + (i.name ? ` · ${i.name}` : '') }),
  )

/** 用户下拉仅 admin 可拉取；非 admin 返回空 */
export function useUserOptions(enabled = true): OptionItem[] {
  const [options, setOptions] = useState<OptionItem[]>([])
  useEffect(() => {
    if (!enabled) {
      setOptions([])
      return
    }
    let alive = true
    fetchAll((p) => listUsers(p))
      .then((items) =>
        alive &&
        setOptions(
          items
            .filter((u: UserOut) => u.is_active)
            .map((u) => ({ value: u.id, label: `${u.name || u.username}（${u.username}）` })),
        ),
      )
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [enabled])
  return options
}
