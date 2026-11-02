import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { localInputToIso, nextQuarterHour, toDateTimeLocal } from './time'

beforeAll(() => {
  vi.stubEnv('TZ', 'America/Chicago')
})

afterAll(() => {
  vi.unstubAllEnvs()
})

describe('localInputToIso', () => {
  it('appends the local standard-time offset', () => {
    expect(localInputToIso('2026-11-02T08:00')).toBe('2026-11-02T08:00:00-06:00')
  })

  it('uses the daylight offset in summer', () => {
    expect(localInputToIso('2026-07-01T08:00')).toBe('2026-07-01T08:00:00-05:00')
  })
})

describe('nextQuarterHour', () => {
  it('rounds up to the next quarter hour', () => {
    expect(toDateTimeLocal(nextQuarterHour(new Date(2026, 10, 2, 8, 7, 30)))).toBe(
      '2026-11-02T08:15',
    )
  })

  it('keeps a time already on the quarter', () => {
    expect(toDateTimeLocal(nextQuarterHour(new Date(2026, 10, 2, 8, 45)))).toBe('2026-11-02T08:45')
  })
})
