/** 分页拉取全部数据（供下拉/引用数据使用） */
export async function fetchAll<T>(
  fetchPage: (params: { page: number; page_size: number }) => Promise<{ total: number; items: T[] }>,
  pageSize = 100,
): Promise<T[]> {
  let page = 1
  const acc: T[] = []
  for (;;) {
    const data = await fetchPage({ page, page_size: pageSize })
    acc.push(...data.items)
    if (acc.length >= data.total) break
    page += 1
  }
  return acc
}
