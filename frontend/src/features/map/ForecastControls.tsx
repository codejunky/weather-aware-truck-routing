import PauseIcon from '@mui/icons-material/Pause'
import PlayIcon from '@mui/icons-material/PlayArrow'
import Box from '@mui/material/Box'
import FormControlLabel from '@mui/material/FormControlLabel'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import Slider from '@mui/material/Slider'
import Switch from '@mui/material/Switch'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { memo, type Ref } from 'react'
import type { HeatmapMetric } from '@/api/schemas'
import { formatForecastHour, formatForecastHourParts } from '@/lib/format'
import { METRICS, type Scheme } from './layers'
import { Legend } from './Legend'
import { OVERLAY_SHADOW } from './overlay'
import { useForecastPlayback } from './useForecastPlayback'

const METRIC_KEYS = Object.keys(METRICS) as HeatmapMetric[]
const TOUCH = { xs: 44, md: 36 }

interface ForecastControlsProps {
  start: string
  hour: number
  maxHour: number
  onHourChange: (hour: number) => void
  metric: HeatmapMetric
  onMetricChange: (metric: HeatmapMetric) => void
  scheme: Scheme
  heatmapOn: boolean
  onHeatmapChange: (on: boolean) => void
  heatmapFaded: boolean
  ref?: Ref<HTMLDivElement>
}

export const ForecastControls = memo(function ForecastControls({
  start,
  hour,
  maxHour,
  onHourChange,
  metric,
  onMetricChange,
  scheme,
  heatmapOn,
  onHeatmapChange,
  heatmapFaded,
  ref,
}: ForecastControlsProps) {
  const reduceMotion = useMediaQuery('(prefers-reduced-motion: reduce)')
  const playback = useForecastPlayback({
    hour,
    onHourChange,
    max: maxHour,
    enabled: !reduceMotion,
  })
  const { offset, when } = formatForecastHourParts(start, hour)
  const marks = [0, 12, 24, 36, 48].filter((h) => h <= maxHour).map((value) => ({ value }))

  return (
    <Paper
      ref={ref}
      component="section"
      aria-label="Forecast controls"
      elevation={0}
      sx={(theme) => ({
        position: 'absolute',
        zIndex: 2,
        bottom: { xs: 0, md: 16 },
        left: { xs: 0, md: '50%' },
        right: { xs: 0, md: 'auto' },
        transform: { md: 'translateX(-50%)' },
        width: { md: 'min(680px, calc(100% - 32px))' },
        borderRadius: { xs: 0, md: 1 },
        border: { xs: 0, md: 1 },
        borderTop: { xs: 1 },
        borderColor: 'divider',
        px: { xs: 1.5, md: 2 },
        pt: { xs: 0.75, md: 1 },
        pb: { xs: 1, md: 1.25 },
        '--panel-shadow': `0 8px 24px ${OVERLAY_SHADOW.light}`,
        boxShadow: { xs: 'none', md: 'var(--panel-shadow)' },
        ...theme.applyStyles('dark', { '--panel-shadow': `0 8px 24px ${OVERLAY_SHADOW.dark}` }),
      })}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: { xs: 1, md: 1.5 } }}>
        <IconButton
          onClick={playback.toggle}
          disabled={reduceMotion}
          aria-label={
            reduceMotion
              ? 'Autoplay off while reduced motion is on'
              : playback.playing
                ? 'Pause forecast'
                : 'Play forecast'
          }
          sx={{
            width: 44,
            height: 44,
            flexShrink: 0,
            bgcolor: 'primary.main',
            color: 'primary.contrastText',
            '&:hover': { bgcolor: 'primary.dark' },
            '&.Mui-disabled': { bgcolor: 'action.disabledBackground' },
          }}
        >
          {playback.playing ? <PauseIcon /> : <PlayIcon />}
        </IconButton>
        <Box aria-hidden sx={{ width: { xs: 92, md: 112 }, flexShrink: 0 }}>
          <Typography
            variant="h4"
            component="p"
            sx={{ fontVariantNumeric: 'tabular-nums', lineHeight: 1.05 }}
          >
            {offset}
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>
            {when}
          </Typography>
        </Box>
        <Slider
          value={hour}
          min={0}
          max={maxHour}
          step={1}
          marks={marks}
          onChange={(_, value) => {
            playback.stop()
            onHourChange(value)
          }}
          aria-label="Forecast hour"
          getAriaValueText={(value) => formatForecastHour(start, value)}
          sx={{ mx: 1, '& .MuiSlider-mark': { height: 6, width: 2, borderRadius: 1 } }}
        />
      </Box>

      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          columnGap: 2,
          rowGap: 0.5,
          mt: 0.5,
        }}
      >
        <ToggleButtonGroup
          exclusive
          size="small"
          value={metric}
          onChange={(_, value: HeatmapMetric | null) => {
            if (value) onMetricChange(value)
          }}
          aria-label="Heatmap metric"
        >
          {METRIC_KEYS.map((key) => (
            <ToggleButton key={key} value={key} sx={{ px: 1.5, py: 0.5, minHeight: TOUCH }}>
              {METRICS[key].label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={heatmapOn}
              onChange={(e) => {
                onHeatmapChange(e.target.checked)
              }}
            />
          }
          label={<Typography variant="body2">Heatmap</Typography>}
          sx={{ mr: 0, ml: -0.5, minHeight: TOUCH, pr: 1 }}
        />
        <Box sx={{ flex: '1 1 200px', minWidth: 0 }}>
          {heatmapOn && heatmapFaded ? (
            <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>
              Zoom out to see the forecast heatmap
            </Typography>
          ) : (
            <Box sx={{ opacity: heatmapOn ? 1 : 0.45 }}>
              <Legend metric={metric} scheme={scheme} />
            </Box>
          )}
        </Box>
      </Box>
    </Paper>
  )
})
