import ScaleIcon from '@mui/icons-material/ScaleOutlined'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import { RiskChip } from '@/components/RiskChip'
import { formatEta, formatWind } from '@/lib/format'
import type { CheckpointDatum } from './layers'

export function CheckpointTooltipContent({ datum }: { datum: CheckpointDatum }) {
  const { checkpoint: cp, routeId } = datum
  const { weather } = cp

  const rows = [
    {
      name: 'Wind',
      level: cp.factors.wind,
      value: formatWind(weather.wind_mph, weather.gust_mph),
    },
    { name: 'Rain', level: cp.factors.rain, value: `${weather.rain_in_hr.toFixed(2)} in/hr` },
    { name: 'Snow', level: cp.factors.snow, value: `${weather.snow_in_hr.toFixed(2)} in/hr` },
  ]

  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h5" component="p" sx={{ fontVariantNumeric: 'tabular-nums' }}>
            Mile {Math.round(cp.mile)}
            <Box component="span" sx={{ color: 'text.secondary', fontWeight: 600, ml: 0.75 }}>
              Route {routeId}
            </Box>
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            ETA {formatEta(cp.eta)}
          </Typography>
        </Box>
        <RiskChip level={cp.level} size="small" />
      </Box>

      <Box
        component="dl"
        sx={{
          display: 'grid',
          gridTemplateColumns: 'auto auto 1fr',
          alignItems: 'center',
          columnGap: 1,
          rowGap: 0.5,
          m: 0,
          mt: 1.25,
        }}
      >
        {rows.map((row) => (
          <Box key={row.name} sx={{ display: 'contents' }}>
            <Typography component="dt" variant="caption" sx={{ fontWeight: 600 }}>
              {row.name}
            </Typography>
            <Box component="dd" sx={{ m: 0 }}>
              <RiskChip level={row.level} size="small" />
            </Box>
            <Typography
              component="dd"
              variant="caption"
              sx={{ m: 0, color: 'text.secondary', fontVariantNumeric: 'tabular-nums' }}
            >
              {row.value}
            </Typography>
          </Box>
        ))}
      </Box>

      {cp.load_adjusted && (
        <Typography
          variant="caption"
          sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 1, color: 'text.primary' }}
        >
          <ScaleIcon sx={{ fontSize: 16 }} aria-hidden />
          Wind tier raised for this load weight
        </Typography>
      )}
    </>
  )
}
