import { describe, expect, it } from 'vitest'
import { PLACES } from '@/test/utils'
import { fieldErrorsFromServer, validateTrip } from './validate'

const now = new Date(2026, 10, 2, 8, 0)
const valid = {
  origin: PLACES.chicago,
  destination: PLACES.denver,
  departure: '2026-11-02T09:00',
  weight: '40000',
}

describe('validateTrip', () => {
  it('accepts a complete trip', () => {
    expect(validateTrip(valid, now)).toEqual({})
  })

  it('requires both places', () => {
    const errors = validateTrip({ ...valid, origin: null, destination: null }, now)
    expect(Object.keys(errors).sort()).toEqual(['destination', 'origin'])
  })

  it('keeps departure between an hour ago and seven days out', () => {
    expect(validateTrip({ ...valid, departure: '2026-11-02T06:30' }, now)).toHaveProperty(
      'departure_at',
    )
    expect(validateTrip({ ...valid, departure: '2026-11-09T08:30' }, now)).toHaveProperty(
      'departure_at',
    )
    expect(validateTrip({ ...valid, departure: '2026-11-02T07:15' }, now)).toEqual({})
  })

  it('limits load weight to 1..80,000 lb', () => {
    expect(validateTrip({ ...valid, weight: '0' }, now)).toHaveProperty('load_weight_lb')
    expect(validateTrip({ ...valid, weight: '80001' }, now)).toHaveProperty('load_weight_lb')
    expect(validateTrip({ ...valid, weight: '' }, now)).toHaveProperty('load_weight_lb')
    expect(validateTrip({ ...valid, weight: '80000' }, now)).toEqual({})
  })
})

describe('fieldErrorsFromServer', () => {
  it('folds dotted keys into their top-level field', () => {
    expect(
      fieldErrorsFromServer({
        'origin.lat': ['Too big.'],
        'origin.lon': ['Too small.'],
        load_weight_lb: ['Too heavy.'],
      }),
    ).toEqual({ origin: 'Too big. Too small.', load_weight_lb: 'Too heavy.' })
  })

  it('returns undefined when no form field matches', () => {
    expect(fieldErrorsFromServer({ non_field_errors: ['Nope.'] })).toBeUndefined()
    expect(fieldErrorsFromServer(undefined)).toBeUndefined()
  })
})
