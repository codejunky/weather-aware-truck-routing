import { describe, expect, it } from 'vitest'
import { theme } from '@/theme'
import { RISK_COLORS, RISK_LEVELS, riskLabel, riskRgb } from './risk'

describe('risk', () => {
  it('lists the five levels in severity order', () => {
    expect(RISK_LEVELS).toEqual(['low', 'moderate', 'high', 'severe', 'no_travel'])
  })

  it.each(RISK_LEVELS)('riskRgb(%s) returns an rgb triple', (level) => {
    const rgb = riskRgb(level)
    expect(rgb).toHaveLength(3)
    rgb.forEach((c) => {
      expect(c).toBeGreaterThanOrEqual(0)
      expect(c).toBeLessThanOrEqual(255)
    })
  })

  it('derives rgb from the hex source', () => {
    expect(riskRgb('low')).toEqual([26, 122, 109])
    expect(riskRgb('no_travel')).toEqual([91, 33, 130])
  })

  it('feeds the theme from the same source', () => {
    expect(theme.palette.risk).toEqual(RISK_COLORS)
  })

  it('gives every level a distinct color', () => {
    const colors = new Set(RISK_LEVELS.map((l) => riskRgb(l).join(',')))
    expect(colors.size).toBe(5)
  })

  it('labels levels for display', () => {
    expect(riskLabel('no_travel')).toBe('No travel')
    expect(riskLabel('low')).toBe('Low')
  })
})
