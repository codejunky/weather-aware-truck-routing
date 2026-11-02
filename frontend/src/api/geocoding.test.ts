import { afterEach, describe, expect, it, vi } from 'vitest'
import { jsonResponse } from '@/test/utils'
import { photonUrl, searchPlaces, toPlaces } from './geocoding'

function feature(properties: Record<string, string>, coordinates: number[] = [-104.99, 39.74]) {
  return { geometry: { coordinates }, properties: { countrycode: 'US', ...properties } }
}

describe('photonUrl', () => {
  it('encodes the query and asks for a few extra results to filter', () => {
    expect(photonUrl('St. Louis, MO & 5th/Main')).toBe(
      'https://photon.komoot.io/api/?q=St.+Louis%2C+MO+%26+5th%2FMain&limit=8',
    )
  })
})

describe('toPlaces', () => {
  it('keeps US places only and swaps Photon lon/lat order', () => {
    const places = toPlaces({
      features: [
        feature({ name: 'Paris', state: 'Texas' }, [-95.55, 33.66]),
        feature({ name: 'Paris', countrycode: 'FR' }, [2.35, 48.86]),
      ],
    })
    expect(places).toEqual([{ label: 'Paris, Texas', lat: 33.66, lon: -95.55 }])
  })

  it('adds the city when it differs from the name and skips repeats', () => {
    const places = toPlaces({
      features: [
        feature({ name: 'Union Station', city: 'Denver', state: 'Colorado' }),
        feature({ name: 'Denver', city: 'Denver', state: 'Colorado' }),
        feature({ name: 'Denver', city: 'Denver', state: 'Colorado' }),
      ],
    })
    expect(places.map((p) => p.label)).toEqual([
      'Union Station, Denver, Colorado',
      'Denver, Colorado',
    ])
  })

  it('skips features without usable coordinates or a name', () => {
    const places = toPlaces({
      features: [
        { geometry: null, properties: { name: 'Nowhere', countrycode: 'US' } },
        feature({ name: 'Half' }, [1]),
        feature({}),
      ],
    })
    expect(places).toEqual([])
  })

  it('returns at most six places', () => {
    const features = Array.from({ length: 8 }, (_, i) => feature({ name: `Town ${i}` }))
    expect(toPlaces({ features })).toHaveLength(6)
  })
})

describe('searchPlaces', () => {
  afterEach(() => vi.restoreAllMocks())

  it('calls Photon directly from the browser', async () => {
    const spy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(jsonResponse(200, { features: [feature({ name: 'Denver' })] }))
    const places = await searchPlaces('Denver')
    expect(spy).toHaveBeenCalledWith(photonUrl('Denver'), expect.anything())
    expect(places).toEqual([{ label: 'Denver', lat: 39.74, lon: -104.99 }])
  })

  it('rejects a response that is not Photon GeoJSON', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(200, { results: [] }))
    await expect(searchPlaces('Denver')).rejects.toMatchObject({ code: 'client.bad_response' })
  })
})
