import { describe, expect, it } from 'vitest'
import { GIB, formatGib, gibToBytes } from '../storage'

describe('storage units', () => {
  it('reads a typed GiB amount, either decimal mark, rounding bytes up', () => {
    expect(gibToBytes('5')).toBe(5 * GIB)
    expect(gibToBytes('2,5')).toBe(2.5 * GIB)
    expect(gibToBytes(' 0.1 ')).toBe(Math.ceil(0.1 * GIB))
  })
  it('refuses what is not a positive amount', () => {
    for (const bad of ['', '  ', '0', '-1', 'abc', '5GB']) expect(gibToBytes(bad)).toBeNull()
  })
  it('reads back the way it was typed', () => {
    expect(formatGib(5 * GIB)).toBe('5 GiB')
    expect(formatGib(2.5 * GIB)).toBe('2.5 GiB')
  })
})
