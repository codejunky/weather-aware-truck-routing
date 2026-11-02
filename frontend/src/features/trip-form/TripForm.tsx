import PlaceIcon from '@mui/icons-material/PlaceOutlined'
import TripOriginIcon from '@mui/icons-material/TripOrigin'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import FormHelperText from '@mui/material/FormHelperText'
import InputAdornment from '@mui/material/InputAdornment'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Typography from '@mui/material/Typography'
import { useEffect, useRef, useState, type RefObject, type SubmitEvent } from 'react'
import { SAMPLE_INTERVALS, type Place, type SampleInterval, type TripRequest } from '@/api/schemas'
import { PlaceAutocomplete } from '@/components/PlaceAutocomplete'
import {
  DEPARTURE_WINDOW_DAYS,
  departureWindow,
  localInputToIso,
  nextQuarterHour,
  timeZoneAbbr,
  toDateTimeLocal,
} from '@/lib/time'
import {
  MAX_LOAD_LB,
  TRIP_FIELDS,
  validateTrip,
  type FieldErrors,
  type TripField,
} from './validate'

interface TripFormProps {
  onSubmit: (trip: TripRequest) => void
  pending: boolean
  serverErrors?: FieldErrors
}

type InputRefs = Partial<Record<TripField, RefObject<HTMLInputElement | null>>>

function focusFirstError(inputs: InputRefs, errors: FieldErrors) {
  for (const field of TRIP_FIELDS) {
    const input = inputs[field]?.current
    if (errors[field] && input) {
      input.focus()
      return
    }
  }
}

export function TripForm({ onSubmit, pending, serverErrors }: TripFormProps) {
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [departure, setDeparture] = useState(() => toDateTimeLocal(nextQuarterHour(new Date())))
  const [weight, setWeight] = useState('40000')
  const [sampleInterval, setSampleInterval] = useState<SampleInterval>(25)
  const [clientErrors, setClientErrors] = useState<FieldErrors>({})
  const [edited, setEdited] = useState<{ since?: FieldErrors; fields: TripField[] }>({
    fields: [],
  })

  const originRef = useRef<HTMLInputElement>(null)
  const destinationRef = useRef<HTMLInputElement>(null)
  const departureRef = useRef<HTMLInputElement>(null)
  const weightRef = useRef<HTMLInputElement>(null)
  const inputRefs = (): InputRefs => ({
    origin: originRef,
    destination: destinationRef,
    departure_at: departureRef,
    load_weight_lb: weightRef,
  })

  // Server errors stay until the user edits that field or the next request replaces them.
  const editedSinceServer = edited.since === serverErrors ? edited.fields : []
  const errors: FieldErrors = {}
  for (const field of TRIP_FIELDS) {
    errors[field] =
      clientErrors[field] ?? (editedSinceServer.includes(field) ? undefined : serverErrors?.[field])
  }

  useEffect(() => {
    if (serverErrors) focusFirstError(inputRefs(), serverErrors)
  }, [serverErrors])

  const clear = (field: TripField) => {
    setClientErrors((prev) => (prev[field] ? { ...prev, [field]: undefined } : prev))
    setEdited((prev) => ({
      since: serverErrors,
      fields: prev.since === serverErrors ? [...prev.fields, field] : [field],
    }))
  }

  const handleSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()
    const found = validateTrip({ origin, destination, departure, weight }, new Date())
    setClientErrors(found)
    if (!origin || !destination || Object.values(found).some(Boolean)) {
      focusFirstError(inputRefs(), found)
      return
    }
    onSubmit({
      origin,
      destination,
      departure_at: localInputToIso(departure),
      load_weight_lb: Number(weight),
      sample_interval_mi: sampleInterval,
    })
  }

  const now = new Date()
  const bounds = departureWindow(now)

  return (
    <Box component="form" noValidate onSubmit={handleSubmit} aria-label="Trip details">
      <Stack spacing={2}>
        <PlaceAutocomplete
          label="Origin"
          value={origin}
          onChange={(place) => {
            setOrigin(place)
            clear('origin')
          }}
          icon={<TripOriginIcon fontSize="small" sx={{ color: 'text.secondary' }} />}
          error={errors.origin}
          inputRef={originRef}
        />
        <PlaceAutocomplete
          label="Destination"
          value={destination}
          onChange={(place) => {
            setDestination(place)
            clear('destination')
          }}
          icon={<PlaceIcon fontSize="small" sx={{ color: 'text.secondary' }} />}
          error={errors.destination}
          inputRef={destinationRef}
        />
        <TextField
          label="Departure"
          type="datetime-local"
          value={departure}
          onChange={(e) => {
            setDeparture(e.target.value)
            clear('departure_at')
          }}
          inputRef={departureRef}
          error={Boolean(errors.departure_at)}
          helperText={
            errors.departure_at ??
            `Your local time (${timeZoneAbbr(now)}), up to ${DEPARTURE_WINDOW_DAYS} days out`
          }
          slotProps={{
            inputLabel: { shrink: true },
            htmlInput: { min: toDateTimeLocal(bounds.min), max: toDateTimeLocal(bounds.max) },
          }}
        />
        <TextField
          label="Load weight"
          type="number"
          value={weight}
          onChange={(e) => {
            setWeight(e.target.value)
            clear('load_weight_lb')
          }}
          inputRef={weightRef}
          error={Boolean(errors.load_weight_lb)}
          helperText={errors.load_weight_lb}
          slotProps={{
            input: { endAdornment: <InputAdornment position="end">lb</InputAdornment> },
            htmlInput: { min: 1, max: MAX_LOAD_LB, step: 500, inputMode: 'numeric' },
          }}
        />
        <Box>
          <Typography
            id="interval-label"
            variant="body2"
            sx={{ mb: 0.75, color: 'text.secondary' }}
          >
            Check the forecast every
          </Typography>
          <ToggleButtonGroup
            exclusive
            fullWidth
            size="small"
            color="primary"
            value={sampleInterval}
            onChange={(_, next: SampleInterval | null) => {
              if (next) setSampleInterval(next)
            }}
            aria-labelledby="interval-label"
          >
            {SAMPLE_INTERVALS.map((mi) => (
              <ToggleButton key={mi} value={mi} sx={{ minHeight: 44, fontWeight: 600 }}>
                {mi} mi
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
          {errors.sample_interval_mi ? (
            <FormHelperText error>{errors.sample_interval_mi}</FormHelperText>
          ) : null}
        </Box>
        <Button
          type="submit"
          variant="contained"
          size="large"
          loading={pending}
          loadingPosition="start"
        >
          {pending ? 'Planning routes…' : 'Plan routes'}
        </Button>
      </Stack>
    </Box>
  )
}
