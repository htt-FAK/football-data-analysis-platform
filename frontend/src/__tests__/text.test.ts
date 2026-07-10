/**
 * text.ts 工具函数单元测试
 *
 * 覆盖 repairPossiblyMojibake (UTF-8 乱码修复) 和 repairTextList (列表修复)
 */
import { describe, it, expect } from 'vitest'
import { repairPossiblyMojibake, repairTextList } from '../lib/text'

describe('repairPossiblyMojibake', () => {
  // 空值/边界输入 —— null, undefined, 空字符串都应返回 ""
  it('returns empty string for null or undefined input', () => {
    expect(repairPossiblyMojibake(null)).toBe('')
    expect(repairPossiblyMojibake(undefined)).toBe('')
    expect(repairPossiblyMojibake('')).toBe('')
  })

  // 非乱码文本原样返回 —— 纯 ASCII 不含 MOJIBAKE_HINT 字符
  it('returns non-mojibake text unchanged', () => {
    expect(repairPossiblyMojibake('hello world')).toBe('hello world')
    expect(repairPossiblyMojibake('Manchester United')).toBe('Manchester United')
    expect(repairPossiblyMojibake('123-456')).toBe('123-456')
  })

  // UTF-8 mojibake 修复 —— "é" 的 UTF-8 字节 [0xC3, 0xA9] 被误读为 Latin-1 时显示为 "Ã©"
  it('decodes UTF-8 mojibake correctly', () => {
    // \u00C3 = Ã, \u00A9 = © → UTF-8 字节 [0xC3, 0xA9] → "é"
    const mojibakeE = '\u00C3\u00A9'
    expect(repairPossiblyMojibake(mojibakeE)).toBe('é')

    // "ñ" 的 UTF-8 字节 [0xC3, 0xB1] → \u00C3\u00B1
    const mojibakeN = '\u00C3\u00B1'
    expect(repairPossiblyMojibake(mojibakeN)).toBe('ñ')

    // "ü" 的 UTF-8 字节 [0xC3, 0xBC] → \u00C3\u00BC
    const mojibakeU = '\u00C3\u00BC'
    expect(repairPossiblyMojibake(mojibakeU)).toBe('ü')
  })

  // CJK 字符不应被当成乱码 —— charCode > 0xFF, 直接 passthrough
  it('preserves CJK characters unchanged', () => {
    expect(repairPossiblyMojibake('中文测试')).toBe('中文测试')
    expect(repairPossiblyMojibake('日本代表')).toBe('日本代表')
    expect(repairPossiblyMojibake('한국어')).toBe('한국어')
  })
})

describe('repairTextList', () => {
  // 过滤空字符串并修复 mojibake
  it('filters empty strings and repairs mojibake in list', () => {
    const mojibake = '\u00C3\u00A9' // → "é"
    const result = repairTextList(['hello', '', mojibake, 'world', ''])
    expect(result).toEqual(['hello', 'é', 'world'])
    // 确认空字符串被完全过滤
    expect(result).not.toContain('')
  })

  // null / undefined 输入应安全降级为空数组
  it('handles null and undefined input gracefully', () => {
    expect(repairTextList(null)).toEqual([])
    expect(repairTextList(undefined)).toEqual([])
    // 数组内的 null/undefined 经 repairPossiblyMojibake → "" → 被 filter(Boolean) 过滤
    expect(repairTextList([null, undefined, ''])).toEqual([])
  })
})
