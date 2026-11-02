import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import type { HeatmapMetric } from '@/api/schemas'
import { hexToRgb, INK, INK_ON_DARK, RISK_LEVELS, riskLabel, rgbaCss } from '@/lib/risk'
import { METRICS, type Scheme } from './layers'

const stopCss = ([r, g, b, a]: readonly [number, number, number, number]) =>
  rgbaCss([r, g, b], a / 255)

export function Legend({ metric, scheme }: { metric: HeatmapMetric; scheme: Scheme }) {
  const ink = hexToRgb(scheme === 'dark' ? INK_ON_DARK : INK)
  if (metric === 'risk') {
    return (
      <Box
        component="ul"
        aria-label="Risk levels"
        sx={{ display: 'flex', flexWrap: 'wrap', columnGap: 1.25, rowGap: 0.25, m: 0, p: 0 }}
      >
        {RISK_LEVELS.map((level) => (
          <Typography
            key={level}
            component="li"
            variant="caption"
            sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}
          >
            <Box
              aria-hidden
              sx={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                bgcolor: `risk.${level}.main`,
                boxShadow: `0 0 0 1px ${rgbaCss(ink, 0.55)}`,
              }}
            />
            {riskLabel(level)}
          </Typography>
        ))}
      </Box>
    )
  }

  const spec = METRICS[metric]
  const [min, max] = spec.domain
  return (
    <Box
      role="img"
      aria-label={`${spec.label} scale from ${min} to ${max} ${spec.unit}`}
      sx={{ minWidth: 0 }}
    >
      <Box
        sx={{
          height: 8,
          borderRadius: 4,
          background: `linear-gradient(90deg, ${spec.stops[scheme].map(stopCss).join(', ')})`,
          boxShadow: `inset 0 0 0 1px ${rgbaCss(ink, 0.15)}`,
        }}
      />
      <Box
        aria-hidden
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          mt: 0.25,
          color: 'text.secondary',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {spec.ticks.map((tick, i) => (
          <Typography key={tick} variant="caption" sx={{ lineHeight: 1.2 }}>
            {tick}
            {i === spec.ticks.length - 1 ? ` ${spec.unit}` : ''}
          </Typography>
        ))}
      </Box>
    </Box>
  )
}
