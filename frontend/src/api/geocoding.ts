import { z } from 'zod'
import { getJson } from './client'
import type { Place } from './schemas'

// Called from the browser so each visitor uses their own IP; Photon throttles shared host IPs.
const PHOTON_URL = 'https://photon.komoot.io/api/'
const FETCH_LIMIT = 8
const MAX_RESULTS = 6

const PhotonSchema = z.object({
  features: z.array(
    z.object({
      geometry: z.object({ coordinates: z.array(z.number()) }).nullish(),
      properties: z.object({
        name: z.string().nullish(),
        city: z.string().nullish(),
        state: z.string().nullish(),
        countrycode: z.string().nullish(),
      }),
    }),
  ),
})

type PhotonFeature = z.infer<typeof PhotonSchema>['features'][number]

export function photonUrl(query: string) {
  return `${PHOTON_URL}?${new URLSearchParams({ q: query, limit: String(FETCH_LIMIT) })}`
}

function label({ name, city, state }: PhotonFeature['properties']) {
  const parts: string[] = []
  for (const part of [name, city, state]) {
    if (part && !parts.includes(part)) parts.push(part)
  }
  return parts.join(', ')
}

export function toPlaces({ features }: z.infer<typeof PhotonSchema>): Place[] {
  const places: Place[] = []
  const seen = new Set<string>()
  for (const feature of features) {
    const coords = feature.geometry?.coordinates ?? []
    const [lon, lat] = coords
    if (feature.properties.countrycode !== 'US' || coords.length !== 2) continue
    if (lon === undefined || lat === undefined) continue
    const text = label(feature.properties)
    if (!text || seen.has(text)) continue
    seen.add(text)
    places.push({ label: text, lat, lon })
    if (places.length === MAX_RESULTS) break
  }
  return places
}

export function searchPlaces(query: string, signal?: AbortSignal) {
  return getJson(photonUrl(query), PhotonSchema.transform(toPlaces), signal)
}
