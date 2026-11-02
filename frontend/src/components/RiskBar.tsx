import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import type { RouteRisk } from '@/api/schemas'
import { formatMiles } from '@/lib/format'
import { RISK_LEVELS, riskLabel, type RiskLevel } from '@/lib/risk'

const milesFor = (risk: RouteRisk, level: RiskLevel) => risk[`${level}_mi`]

export function RiskBar({ risk }: { risk: RouteRisk }) {
  const segments = RISK_LEVELS.map((level) => ({ level, miles: milesFor(risk, level) })).filter(
    (s) => s.miles > 0,
  )
  const total = segments.reduce((sum, s) => sum + s.miles, 0)
  const summary = segments.map((s) => `${riskLabel(s.level)} ${formatMiles(s.miles)}`).join(', ')

  return (
    <Box>
      <Box
        role="img"
        aria-label={`Miles by risk: ${summary}`}
        sx={{
          display: 'flex',
          gap: '2px',
          height: 10,
          borderRadius: 5,
          overflow: 'hidden',
          bgcolor: 'divider',
        }}
      >
        {segments.map((s) => (
          <Box
            key={s.level}
            sx={(theme) => ({
              flexGrow: s.miles / total,
              flexBasis: 0,
              minWidth: 4,
              bgcolor: theme.palette.risk[s.level].main,
            })}
          />
        ))}
      </Box>
      <Box
        component="ul"
        aria-hidden
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          columnGap: 1.5,
          rowGap: 0.25,
          m: 0,
          mt: 0.75,
          p: 0,
          listStyle: 'none',
        }}
      >
        {segments.map((s) => (
          <Typography
            key={s.level}
            component="li"
            variant="caption"
            sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}
          >
            <Box
              sx={(theme) => ({
                width: 8,
                height: 8,
                borderRadius: '2px',
                bgcolor: theme.palette.risk[s.level].main,
              })}
            />
            {riskLabel(s.level)}
            <Box
              component="span"
              sx={{ color: 'text.primary', fontVariantNumeric: 'tabular-nums' }}
            >
              {formatMiles(s.miles)}
            </Box>
          </Typography>
        ))}
      </Box>
    </Box>
  )
}
