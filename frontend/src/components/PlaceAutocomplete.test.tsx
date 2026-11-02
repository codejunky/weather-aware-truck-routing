import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Place } from '@/api/schemas'
import { geocodeResponse, mockFetch, renderWithProviders } from '@/test/utils'
import { PlaceAutocomplete } from './PlaceAutocomplete'

afterEach(() => {
  vi.restoreAllMocks()
})

function Harness() {
  const [place, setPlace] = useState<Place | null>(null)
  return <PlaceAutocomplete label="Origin" value={place} onChange={setPlace} />
}

describe('PlaceAutocomplete', () => {
  it('asks for more letters before searching', async () => {
    const user = userEvent.setup()
    const spy = mockFetch(geocodeResponse)
    renderWithProviders(<Harness />)

    await user.type(screen.getByRole('combobox', { name: 'Origin' }), 'Ch')
    expect(await screen.findByText('Keep typing…')).toBeInTheDocument()
    expect(spy).not.toHaveBeenCalled()
  })

  it('drops options from a previous query as soon as the query changes', async () => {
    const user = userEvent.setup()
    mockFetch(geocodeResponse)
    renderWithProviders(<Harness />)
    const input = screen.getByRole('combobox', { name: 'Origin' })

    await user.type(input, 'Chic')
    expect(await screen.findByRole('option', { name: 'Chicago, IL' })).toBeInTheDocument()

    await user.clear(input)
    await user.type(input, 'Denv')
    expect(screen.queryByRole('option', { name: 'Chicago, IL' })).not.toBeInTheDocument()
    expect(screen.getByText('Searching…')).toBeInTheDocument()

    await user.keyboard('{Enter}')
    expect(input).toHaveValue('Denv')

    expect(await screen.findByRole('option', { name: 'Denver, CO' })).toBeInTheDocument()
  })

  it('says nothing matched only after the search settles', async () => {
    const user = userEvent.setup()
    mockFetch(geocodeResponse)
    renderWithProviders(<Harness />)

    await user.type(screen.getByRole('combobox', { name: 'Origin' }), 'Zzzz')
    expect(screen.getByText('Searching…')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('No US places match')).toBeInTheDocument()
    })
  })
})
