import { addHours, format, parseISO } from 'date-fns'
import { timeZoneAbbr } from './time'

const milesFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

export function formatNumber(value: number): string {
  return milesFormatter.format(value)
}

export function formatMiles(miles: number): string {
  return `${milesFormatter.format(miles)} mi`
}

export function formatWind(windMph: number, gustMph: number | null): string {
  const gusts = gustMph === null ? 'n/a' : gustMph.toFixed(0)
  return `${windMph.toFixed(0)} mph, gusts ${gusts}`
}

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`
}

export function formatEtaParts(iso: string) {
  const date = parseISO(iso)
  return { time: format(date, 'EEE h:mm a'), zone: timeZoneAbbr(date) }
}

export function formatEta(iso: string): string {
  const { time, zone } = formatEtaParts(iso)
  return `${time} ${zone}`.trim()
}

export function formatForecastHourParts(startIso: string, hour: number) {
  return { offset: `+${hour}h`, when: format(addHours(parseISO(startIso), hour), 'EEE h a') }
}

export function formatForecastHour(startIso: string, hour: number): string {
  const { offset, when } = formatForecastHourParts(startIso, hour)
  return `${offset} · ${when}`
}
