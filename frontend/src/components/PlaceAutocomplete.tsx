import Autocomplete from '@mui/material/Autocomplete'
import CircularProgress from '@mui/material/CircularProgress'
import InputAdornment from '@mui/material/InputAdornment'
import TextField from '@mui/material/TextField'
import { useState, type ReactNode, type Ref } from 'react'
import { GEOCODE_MIN_CHARS, useGeocode } from '@/api/hooks'
import type { Place } from '@/api/schemas'

interface PlaceAutocompleteProps {
  label: string
  value: Place | null
  onChange: (place: Place | null) => void
  icon?: ReactNode
  error?: string
  inputRef?: Ref<HTMLInputElement>
}

const samePlace = (a: Place, b: Place) => a.label === b.label && a.lat === b.lat && a.lon === b.lon

export function PlaceAutocomplete({
  label,
  value,
  onChange,
  icon,
  error,
  inputRef,
}: PlaceAutocompleteProps) {
  const [input, setInput] = useState('')
  const showingValue = value !== null && input === value.label
  const { places, searching, failed } = useGeocode(showingValue ? '' : input)

  const options = showingValue ? [value] : places

  let noOptionsText = 'No US places match'
  if (input.trim().length < GEOCODE_MIN_CHARS) noOptionsText = 'Keep typing…'
  else if (failed) noOptionsText = 'Search is unavailable right now'

  return (
    <Autocomplete
      value={value}
      onChange={(_, place) => {
        onChange(place)
      }}
      inputValue={input}
      onInputChange={(_, next) => {
        setInput(next)
      }}
      options={options}
      filterOptions={(x) => x}
      getOptionLabel={(o) => o.label}
      getOptionKey={(o) => `${o.label}|${o.lat}|${o.lon}`}
      isOptionEqualToValue={samePlace}
      loading={searching}
      loadingText="Searching…"
      noOptionsText={noOptionsText}
      autoHighlight
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          inputRef={inputRef}
          error={Boolean(error)}
          helperText={error}
          slotProps={{
            ...params.slotProps,
            input: {
              ...params.slotProps.input,
              startAdornment: icon ? (
                <InputAdornment position="start">{icon}</InputAdornment>
              ) : null,
              endAdornment: (
                <>
                  {searching ? <CircularProgress color="inherit" size={18} aria-hidden /> : null}
                  {params.slotProps.input.endAdornment}
                </>
              ),
            },
          }}
        />
      )}
    />
  )
}
