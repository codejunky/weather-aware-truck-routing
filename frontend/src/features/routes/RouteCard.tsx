import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import RadioCheckedIcon from '@mui/icons-material/RadioButtonChecked'
import RadioUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import Typography from '@mui/material/Typography'
import { useId, type KeyboardEvent, type Ref } from 'react'
import type { Route } from '@/api/schemas'
import { RouteBadges } from '@/components/RouteBadges'
import { RouteStats } from '@/components/RouteStats'
import { RouteTitle } from '@/components/RouteTitle'
import { visuallyHidden } from '@/lib/a11y'
import { formatEta, formatMiles, formatNumber } from '@/lib/format'

interface RouteCardProps {
  route: Route
  recommended: boolean
  selected: boolean
  focusable: boolean
  onSelect: (id: string) => void
  onKeyDown: (event: KeyboardEvent<HTMLDivElement>) => void
  cardRef: Ref<HTMLDivElement>
}

const plural = (n: number, unit: string) => `${n} ${unit}${n === 1 ? '' : 's'}`

function spokenDuration(seconds: number) {
  const minutes = Math.round(seconds / 60)
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h === 0) return plural(m, 'minute')
  return m === 0 ? plural(h, 'hour') : `${plural(h, 'hour')} ${plural(m, 'minute')}`
}

function routeSummary(route: Route, recommended: boolean) {
  const { high_mi, severe_mi, no_travel_mi } = route.risk
  const risky = [
    [high_mi, 'high-risk'],
    [severe_mi, 'severe-risk'],
    [no_travel_mi, 'no-travel'],
  ] as const
  const riskParts = risky
    .filter(([miles]) => miles > 0)
    .map(([miles, label]) => `${formatNumber(miles)} ${label} miles`)

  return [
    `${formatNumber(route.distance_mi)} miles`,
    spokenDuration(route.duration_s),
    `arrives ${formatEta(route.arrival_at)}`,
    ...(riskParts.length ? riskParts : ['no high-risk miles']),
    route.blocked ? 'blocked' : null,
    route.truck_profile ? null : 'car route',
    recommended ? 'recommended' : null,
  ]
    .filter((part) => part !== null)
    .join(', ')
}

export function RouteCard({
  route,
  recommended,
  selected,
  focusable,
  onSelect,
  onKeyDown,
  cardRef,
}: RouteCardProps) {
  const titleId = useId()
  const summaryId = useId()

  return (
    <Card
      ref={cardRef}
      variant="outlined"
      role="radio"
      aria-checked={selected}
      aria-labelledby={titleId}
      aria-describedby={summaryId}
      tabIndex={focusable ? 0 : -1}
      onClick={() => {
        onSelect(route.id)
      }}
      onKeyDown={onKeyDown}
      sx={(theme) => {
        const primary = (theme.vars ?? theme).palette.primary
        const halo = theme.alpha(primary.main, 0.18)
        return {
          cursor: 'pointer',
          overflow: 'visible',
          borderWidth: 2,
          borderColor: selected ? primary.main : 'divider',
          boxShadow: selected ? `0 0 0 3px ${halo}` : 'none',
          transition: theme.transitions.create(['border-color', 'box-shadow'], {
            duration: theme.transitions.duration.shorter,
          }),
          '&:hover': selected ? {} : { borderColor: 'text.secondary' },
          '&:focus-visible': { outline: `3px solid ${primary.main}`, outlineOffset: 3 },
        }
      }}
    >
      <Box id={summaryId} sx={visuallyHidden}>
        {routeSummary(route, recommended)}
      </Box>

      {recommended ? (
        <Box
          sx={(theme) => {
            const primary = (theme.vars ?? theme).palette.primary.main
            return {
              px: 2,
              py: 1.25,
              borderTopLeftRadius: 8,
              borderTopRightRadius: 8,
              bgcolor: theme.alpha(primary, 0.07),
              borderBottom: 1,
              borderColor: 'divider',
              ...theme.applyStyles('dark', { bgcolor: theme.alpha(primary, 0.16) }),
            }
          }}
        >
          <Typography
            variant="subtitle2"
            component="p"
            sx={{ display: 'flex', alignItems: 'center', gap: 0.75, color: 'primary.main' }}
          >
            <CheckCircleIcon fontSize="small" aria-hidden />
            Recommended
          </Typography>
          {route.reasons.length > 0 ? (
            <Box component="ul" sx={{ m: 0, mt: 0.25, pl: 3.75, listStyle: 'none' }}>
              {route.reasons.map((reason, i) => (
                <Typography key={i} component="li" variant="body2">
                  {reason}
                </Typography>
              ))}
            </Box>
          ) : null}
        </Box>
      ) : null}

      <Box sx={{ p: 2, display: 'grid', gap: 1.75 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <RouteTitle route={route} id={titleId} heading />
          <Box
            aria-hidden
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              flexShrink: 0,
              color: selected ? 'primary.main' : 'text.secondary',
            }}
          >
            {selected ? (
              <>
                <Typography variant="caption" sx={{ fontWeight: 600 }}>
                  Selected
                </Typography>
                <RadioCheckedIcon fontSize="small" />
              </>
            ) : (
              <RadioUncheckedIcon fontSize="small" />
            )}
          </Box>
        </Box>

        <RouteBadges route={route} />

        <RouteStats route={route} spread />

        {route.blocked ? (
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {formatMiles(route.risk.no_travel_mi)} of this route is forecast at no-travel
            conditions.
          </Typography>
        ) : null}
        {!route.truck_profile ? (
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            No truck route was found here, so this uses car roads. Check height and weight limits
            before dispatch.
          </Typography>
        ) : null}
      </Box>
    </Card>
  )
}
