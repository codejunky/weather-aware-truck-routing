import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'

export function Stat({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <Box>
      <Typography component="dt" variant="caption" sx={{ color: 'text.secondary' }}>
        {label}
      </Typography>
      <Typography
        component="dd"
        variant="subtitle1"
        sx={{ m: 0, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}
      >
        {value}
        {unit ? (
          <Box
            component="span"
            sx={{ ml: 0.5, typography: 'caption', fontWeight: 600, color: 'text.secondary' }}
          >
            {unit}
          </Box>
        ) : null}
      </Typography>
    </Box>
  )
}
