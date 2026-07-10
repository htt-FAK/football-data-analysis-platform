/**
 * vitest 全局 setup — mock 浏览器 API, 避免测试发起真实网络请求
 *
 * 由 vite.config.ts 的 setupFiles 引用, 在所有测试前自动执行
 */
import { vi } from 'vitest'
import '@testing-library/jest-dom'

/* ---------- fetch ---------- */
// 默认返回空 JSON, 测试用例可逐个覆盖 vi.mocked(fetch).mockResolvedValueOnce(...)
if (typeof globalThis.fetch === 'undefined') {
  ;(globalThis as unknown as Record<string, unknown>).fetch = vi
    .fn()
    .mockResolvedValue(new Response('{}', { status: 200 }))
} else {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response('{}', { status: 200 })),
  )
}

/* ---------- localStorage ---------- */
// jsdom 已内置 localStorage, 这里仅做兜底
if (typeof globalThis.localStorage === 'undefined') {
  const store: Record<string, string> = {}
  ;(globalThis as unknown as Record<string, unknown>).localStorage = {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = String(value)
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      Object.keys(store).forEach((k) => delete store[k])
    },
    key: (index: number) => Object.keys(store)[index] ?? null,
    get length() {
      return Object.keys(store).length
    },
  } as Storage
}
