import Alert from '@mui/material/Alert'
import AlertTitle from '@mui/material/AlertTitle'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import Skeleton from '@mui/material/Skeleton'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import type { ApiError } from '@/api/client'
import type { TripPlan } from '@/api/schemas'
import { RiskChip } from '@/components/RiskChip'
import { visuallyHidden } from '@/lib/a11y'
import { formatEta } from '@/lib/format'
import { RISK_LEVELS } from '@/lib/risk'
import { RouteList } from './RouteList'

interface TripResultsProps {
  plan: TripPlan | null
  pending: boolean
  error: ApiError | null
  fieldErrorsShown: boolean
  onRetry: () => void
  selectedRouteId: string | null
  onSelectRoute: (id: string) => void
}

const ERROR_TITLES = new Map([
  ['routing.no_route', 'No route found'],
  ['network.unreachable', 'Server unreachable'],
])

function errorTitle(error: ApiError) {
  const title = ERROR_TITLES.get(error.code)
  if (title) return title
  if (error.code.startsWith('upstream.')) return 'A data provider is down'
  return 'Could not plan this trip'
}

function EmptyState() {
  return (
    <Box
      sx={{
        border: 1,
        borderStyle: 'dashed',
        borderColor: 'divider',
        borderRadius: 2,
        p: 2.5,
      }}
    >
      <Typography variant="subtitle1" component="p">
        No trip planned yet
      </Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
        Pick an origin and destination to compare routes. Each one is scored by the forecast at
        every checkpoint, timed to when the truck gets there.
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 2 }} aria-label="Risk levels">
        {RISK_LEVELS.map((level) => (
          <RiskChip key={level} level={level} size="small" />
        ))}
      </Box>
    </Box>
  )
}

function LoadingState() {
  return (
    <Stack spacing={1.5} aria-hidden>
      {[0, 1, 2].map((i) => (
        <Card key={i} variant="outlined" sx={{ p: 2, borderWidth: 2 }}>
          <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'center' }}>
            <Skeleton variant="rounded" width={34} height={36} />
            <Skeleton width="55%" height={28} />
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
            <Skeleton width="22%" />
            <Skeleton width="22%" />
            <Skeleton width="22%" />
          </Box>
          <Skeleton variant="rounded" height={10} sx={{ mt: 2 }} />
        </Card>
      ))}
    </Stack>
  )
}

export function TripResults({
  plan,
  pending,
  error,
  fieldErrorsShown,
  onRetry,
  selectedRouteId,
  onSelectRoute,
}: TripResultsProps) {
  let status = ''
  if (pending) status = 'Checking routes and forecasts…'
  else if (plan)
    status = `${plan.routes.length} routes found. Route ${plan.recommended_route_id} is recommended.`

  return (
    <Box component="section" aria-labelledby="routes-heading" aria-busy={pending}>
      <Box
        sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', mb: 1.5 }}
      >
        <Typography id="routes-heading" variant="h3" component="h2">
          Routes
        </Typography>
        {plan && !pending ? (
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {plan.routes.length} options, leaving {formatEta(plan.departure_at)}
          </Typography>
        ) : null}
      </Box>
      <Box role="status" sx={visuallyHidden}>
        {status}
      </Box>

      {pending ? (
        <>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1.5 }}>
            Checking routes and forecasts…
          </Typography>
          <LoadingState />
        </>
      ) : error && !fieldErrorsShown ? (
        <Alert
          severity="error"
          variant="outlined"
          action={
            error.retryable ? (
              <Button color="inherit" size="small" onClick={onRetry}>
                Retry
              </Button>
            ) : undefined
          }
        >
          <AlertTitle>{errorTitle(error)}</AlertTitle>
          <Box>{error.fields?.non_field_errors?.join(' ') ?? error.detail}</Box>
          {error.retryable ? (
            <Box sx={{ mt: 0.5, opacity: 0.85 }}>Your trip details are kept, so you can retry.</Box>
          ) : null}
        </Alert>
      ) : error ? (
        <Alert severity="warning" variant="outlined">
          {error.fields?.non_field_errors ? (
            <Box sx={{ mb: 0.5 }}>{error.fields.non_field_errors.join(' ')}</Box>
          ) : null}
          Fix the highlighted fields and plan again.
        </Alert>
      ) : plan ? (
        <Stack spacing={1.5}>
          {plan.notices.map((notice, i) => (
            <Alert key={i} severity="info" variant="outlined">
              {notice}
            </Alert>
          ))}
          <RouteList plan={plan} selectedRouteId={selectedRouteId} onSelect={onSelectRoute} />
        </Stack>
      ) : (
        <EmptyState />
      )}
    </Box>
  )
}
