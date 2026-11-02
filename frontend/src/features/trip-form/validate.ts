import type { FieldMessages } from '@/api/client'
import type { Place } from '@/api/schemas'
import { formatNumber } from '@/lib/format'
import { DEPARTURE_WINDOW_DAYS, departureWindow } from '@/lib/time'

interface TripFormValues {
  origin: Place | null
  destination: Place | null
  departure: string
  weight: string
}

export const TRIP_FIELDS = [
  'origin',
  'destination',
  'departure_at',
  'load_weight_lb',
  'sample_interval_mi',
] as const

export type TripField = (typeof TRIP_FIELDS)[number]

export type FieldErrors = Partial<Record<TripField, string>>

export const MAX_LOAD_LB = 80_000

const isTripField = (key: string): key is TripField =>
  (TRIP_FIELDS as readonly string[]).includes(key)

export function validateTrip(values: TripFormValues, now: Date): FieldErrors {
  const errors: FieldErrors = {}
  if (!values.origin) errors.origin = 'Choose a starting point from the list.'
  if (!values.destination) errors.destination = 'Choose a destination from the list.'

  const departure = new Date(values.departure)
  const { min, max } = departureWindow(now)
  if (Number.isNaN(departure.getTime())) {
    errors.departure_at = 'Enter a departure date and time.'
  } else if (departure < min || departure > max) {
    errors.departure_at = `Departure must be between an hour ago and ${DEPARTURE_WINDOW_DAYS} days from now.`
  }

  const weight = Number(values.weight)
  if (
    values.weight.trim() === '' ||
    !Number.isInteger(weight) ||
    weight < 1 ||
    weight > MAX_LOAD_LB
  ) {
    errors.load_weight_lb = `Enter a whole number from 1 to ${formatNumber(MAX_LOAD_LB)} lb.`
  }
  return errors
}

export function fieldErrorsFromServer(fields: FieldMessages | undefined): FieldErrors | undefined {
  if (!fields) return undefined
  const grouped: Partial<Record<TripField, string[]>> = {}
  for (const [key, messages] of Object.entries(fields)) {
    const field = key.split('.')[0] ?? key
    if (isTripField(field)) grouped[field] = [...(grouped[field] ?? []), ...messages]
  }
  const errors: FieldErrors = {}
  for (const field of TRIP_FIELDS) {
    const messages = grouped[field]
    if (messages?.length) errors[field] = messages.join(' ')
  }
  return Object.keys(errors).length > 0 ? errors : undefined
}
