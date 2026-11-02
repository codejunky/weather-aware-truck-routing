import { useMutation, useQuery } from '@tanstack/react-query'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { postJson, type ApiError } from './client'
import { searchPlaces } from './geocoding'
import { TripPlanSchema, type TripPlan, type TripRequest } from './schemas'

export const GEOCODE_MIN_CHARS = 3

export function usePlanTrip() {
  return useMutation<TripPlan, ApiError, TripRequest>({
    mutationFn: (trip) => postJson('/api/trips/plan', trip, TripPlanSchema),
  })
}

export function useGeocode(query: string) {
  const typed = query.trim()
  const q = useDebouncedValue(typed, 300)
  const enabled = q.length >= GEOCODE_MIN_CHARS
  const geocode = useQuery({
    queryKey: ['geocode', q],
    queryFn: ({ signal }) => searchPlaces(q, signal),
    enabled,
    staleTime: 5 * 60_000,
  })

  const settled = typed === q && !geocode.isFetching
  return {
    places: settled ? (geocode.data ?? []) : [],
    searching: typed.length >= GEOCODE_MIN_CHARS && !settled,
    failed: settled && geocode.isError,
  }
}
