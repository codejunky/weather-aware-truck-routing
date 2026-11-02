import { addDays, addHours, format, parseISO, roundToNearestMinutes } from 'date-fns'

export const DEPARTURE_WINDOW_DAYS = 7

export function toDateTimeLocal(date: Date): string {
  return format(date, "yyyy-MM-dd'T'HH:mm")
}

export function nextQuarterHour(now: Date): Date {
  return roundToNearestMinutes(now, { nearestTo: 15, roundingMethod: 'ceil' })
}

export function localInputToIso(value: string): string {
  return format(parseISO(value), "yyyy-MM-dd'T'HH:mm:ssxxx")
}

export function departureWindow(now: Date) {
  return { min: addHours(now, -1), max: addDays(now, DEPARTURE_WINDOW_DAYS) }
}

export function timeZoneAbbr(date: Date): string {
  const parts = new Intl.DateTimeFormat('en-US', { timeZoneName: 'short' }).formatToParts(date)
  return parts.find((p) => p.type === 'timeZoneName')?.value ?? ''
}
