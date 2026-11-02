import Box from '@mui/material/Box'
import Divider from '@mui/material/Divider'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { lazy, Suspense, useMemo, useRef, useState } from 'react'
import { usePlanTrip } from '@/api/hooks'
import type { TripRequest } from '@/api/schemas'
import { MapFallback } from '@/components/MapFallback'
import { TripResults } from '@/features/routes/TripResults'
import { TripForm } from '@/features/trip-form/TripForm'
import { fieldErrorsFromServer } from '@/features/trip-form/validate'

const TripMap = lazy(() => import('@/features/map/TripMap').then((m) => ({ default: m.TripMap })))

const MOBILE_MAP_HEIGHT = '45vh'

export default function App() {
  const isMobile = useMediaQuery((theme) => theme.breakpoints.down('md'))
  const reduceMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

  const planTrip = usePlanTrip()
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null)
  const plan = planTrip.data ?? null
  const resultsRef = useRef<HTMLDivElement>(null)

  const serverErrors = useMemo(
    () => fieldErrorsFromServer(planTrip.error?.fields),
    [planTrip.error],
  )

  const submit = (trip: TripRequest) => {
    planTrip.mutate(trip, {
      onSuccess: (result) => {
        setSelectedRouteId(result.recommended_route_id)
        if (isMobile) {
          resultsRef.current?.scrollIntoView({
            block: 'start',
            behavior: reduceMotion ? 'auto' : 'smooth',
          })
        }
      },
    })
  }

  const retry = () => {
    if (planTrip.variables) submit(planTrip.variables)
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', md: 'row' },
        height: { md: '100dvh' },
        minHeight: '100dvh',
      }}
    >
      <Box
        component="main"
        sx={{
          position: 'relative',
          order: { xs: 1, md: 0 },
          width: { md: 400 },
          flexShrink: 0,
          borderRight: { md: 1 },
          borderColor: 'divider',
          bgcolor: 'background.paper',
          overflowY: { md: 'auto' },
          px: { xs: 2, sm: 3 },
          py: 3,
        }}
      >
        <Box component="header" sx={{ mb: 2.5 }}>
          <Typography variant="h1">Weather route planner</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.75 }}>
            Compare truck routes by forecast wind, rain and snow along the way.
          </Typography>
        </Box>
        <TripForm onSubmit={submit} pending={planTrip.isPending} serverErrors={serverErrors} />
        <Divider sx={{ my: 3 }} />
        <Box ref={resultsRef} sx={{ scrollMarginTop: `calc(${MOBILE_MAP_HEIGHT} + 16px)` }}>
          <TripResults
            plan={plan}
            pending={planTrip.isPending}
            error={planTrip.error}
            fieldErrorsShown={serverErrors !== undefined}
            onRetry={retry}
            selectedRouteId={selectedRouteId}
            onSelectRoute={setSelectedRouteId}
          />
        </Box>
      </Box>
      <Box
        component="section"
        aria-label="Map"
        sx={{
          order: { xs: 0, md: 1 },
          flex: { md: 1 },
          position: { xs: 'sticky', md: 'relative' },
          top: 0,
          zIndex: 1,
          height: { xs: MOBILE_MAP_HEIGHT, md: 'auto' },
          flexShrink: 0,
          borderBottom: { xs: 1, md: 0 },
          borderColor: 'divider',
        }}
      >
        <Suspense fallback={<MapFallback />}>
          <TripMap
            plan={plan}
            selectedRouteId={selectedRouteId}
            onSelectRoute={setSelectedRouteId}
          />
        </Suspense>
      </Box>
    </Box>
  )
}
