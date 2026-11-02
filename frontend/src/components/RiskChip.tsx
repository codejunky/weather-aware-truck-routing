import Chip, { type ChipProps } from '@mui/material/Chip'
import { riskLabel, type RiskLevel } from '@/lib/risk'

interface RiskChipProps extends Omit<ChipProps, 'label' | 'color' | 'sx'> {
  level: RiskLevel
}

export function RiskChip({ level, ...rest }: RiskChipProps) {
  return (
    <Chip
      label={riskLabel(level)}
      {...rest}
      sx={(theme) => ({
        bgcolor: theme.palette.risk[level].main,
        color: theme.palette.risk[level].contrastText,
      })}
    />
  )
}
