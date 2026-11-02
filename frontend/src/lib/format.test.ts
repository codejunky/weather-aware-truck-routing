import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import {
  formatDuration,
  formatEta,
  formatForecastHour,
  formatForecastHourParts,
  formatMiles,
} from './format'

describe('formatDuration', () => {
  it('formats hours and minutes', () => {
    expect(formatDuration(55200)).toBe('15h 20m')
  })

  it('drops hours under one hour', () => {
    expect(formatDuration(2700)).toBe('45m')
  })

  it('rounds seconds to the nearest minute', () => {
    expect(formatDuration(3629)).toBe('1h 0m')
  })
})

describe('formatMiles', () => {
  it('uses a thousands separator and rounds', () => {
    expect(formatMiles(1234.6)).toBe('1,235 mi')
  })
})

describe('formatEta', () => {
  beforeAll(() => {
    vi.stubEnv('TZ', 'America/Chicago')
  })

  afterAll(() => {
    vi.unstubAllEnvs()
  })

  it('renders weekday, 12-hour time and zone', () => {
    expect(formatEta('2026-11-02T14:40:00')).toBe('Mon 2:40 PM CST')
  })

  it('converts offset timestamps into the viewer zone', () => {
    expect(formatEta('2026-07-01T20:00:00Z')).toBe('Wed 3:00 PM CDT')
  })

  it('formatForecastHour offsets from the heatmap start', () => {
    expect(formatForecastHour('2026-11-03T08:00:00', 14)).toBe('+14h · Tue 10 PM')
    expect(formatForecastHour('2026-11-03T08:00:00', 0)).toBe('+0h · Tue 8 AM')
  })

  it('formatForecastHourParts splits offset and wall time', () => {
    expect(formatForecastHourParts('2026-11-03T08:00:00', 14)).toEqual({
      offset: '+14h',
      when: 'Tue 10 PM',
    })
    expect(formatForecastHourParts('2026-11-03T08:00:00', 48).offset).toBe('+48h')
  })
})
