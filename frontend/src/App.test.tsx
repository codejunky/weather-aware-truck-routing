import { screen, waitFor } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TripRequestSchema } from '@/api/schemas'
import fixture from '@/test/fixtures/plan.json'
import {
  geocodeResponse,
  isGeocodeUrl,
  jsonResponse,
  mockFetch,
  PLACES,
  renderWithProviders,
  urlOf,
} from '@/test/utils'
import App from './App'

afterEach(() => {
  vi.restoreAllMocks()
})

async function pickPlace(user: UserEvent, label: string, query: string, option: string) {
  await user.type(screen.getByRole('combobox', { name: label }), query)
  await user.click(await screen.findByRole('option', { name: option }, { timeout: 2000 }))
}

async function fillAndSubmit(user: UserEvent) {
  await pickPlace(user, 'Origin', 'Chic', 'Chicago, IL')
  await pickPlace(user, 'Destination', 'Denv', 'Denver, CO')
  await user.click(screen.getByRole('button', { name: 'Plan routes' }))
}

function planCalls(spy: ReturnType<typeof mockFetch>) {
  return spy.mock.calls.filter(([input]) => urlOf(input).includes('/api/trips/plan'))
}

describe('trip planning', () => {
  it('TripForm submits contract payload', async () => {
    const user = userEvent.setup()
    const spy = mockFetch((url) =>
      isGeocodeUrl(url) ? geocodeResponse(url) : jsonResponse(200, fixture),
    )
    renderWithProviders(<App />)

    await fillAndSubmit(user)

    await waitFor(() => {
      expect(planCalls(spy)).toHaveLength(1)
    })
    const [, init] = planCalls(spy)[0] ?? []
    expect(init?.method).toBe('POST')
    const raw = init?.body
    if (typeof raw !== 'string') throw new Error('expected a JSON string body')
    const { departure_at, ...rest } = TripRequestSchema.strict().parse(JSON.parse(raw))
    expect(rest).toEqual({
      origin: PLACES.chicago,
      destination: PLACES.denver,
      load_weight_lb: 40000,
      sample_interval_mi: 25,
    })
    expect(departure_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00[+-]\d{2}:\d{2}$/)
    expect(await screen.findByRole('radio', { name: /^Route A\b/ })).toBeInTheDocument()
  })

  it('400 field error shown inline', async () => {
    const user = userEvent.setup()
    mockFetch((url) =>
      isGeocodeUrl(url)
        ? geocodeResponse(url)
        : jsonResponse(400, {
            code: 'validation.invalid',
            detail: 'Invalid input.',
            fields: { departure_at: ['Departure must be within the next 7 days.'] },
          }),
    )
    renderWithProviders(<App />)

    await fillAndSubmit(user)

    expect(await screen.findByText('Departure must be within the next 7 days.')).toBeVisible()
    expect(screen.getByLabelText(/Departure/)).toHaveAttribute('aria-invalid', 'true')
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
  })

  it('502 shows retry and retry refetches', async () => {
    const user = userEvent.setup()
    let planAttempts = 0
    const spy = mockFetch((url) => {
      if (isGeocodeUrl(url)) return geocodeResponse(url)
      planAttempts += 1
      return planAttempts === 1
        ? jsonResponse(502, {
            code: 'upstream.weather_unavailable',
            detail: 'The weather service is unavailable',
          })
        : jsonResponse(200, fixture)
    })
    renderWithProviders(<App />)

    await fillAndSubmit(user)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The weather service is unavailable')
    await user.click(screen.getByRole('button', { name: 'Retry' }))

    expect(await screen.findByRole('radio', { name: /^Route A\b/ })).toBeInTheDocument()
    expect(planCalls(spy)).toHaveLength(2)
    expect(planCalls(spy)[1]?.[1]?.body).toBe(planCalls(spy)[0]?.[1]?.body)
  })

  it('maps nested server errors to their top-level field', async () => {
    const user = userEvent.setup()
    mockFetch((url) =>
      isGeocodeUrl(url)
        ? geocodeResponse(url)
        : jsonResponse(400, {
            code: 'validation.invalid',
            detail: 'Invalid input.',
            fields: { origin: { lat: ['Ensure this value is less than or equal to 90.'] } },
          }),
    )
    renderWithProviders(<App />)

    await fillAndSubmit(user)

    expect(await screen.findByText('Ensure this value is less than or equal to 90.')).toBeVisible()
    expect(screen.getByRole('combobox', { name: 'Origin' })).toHaveAttribute('aria-invalid', 'true')
    expect(screen.queryByText(/object Object|\{'lat'/)).not.toBeInTheDocument()
  })

  it('falls back to an alert when no form field matches', async () => {
    const user = userEvent.setup()
    mockFetch((url) =>
      isGeocodeUrl(url)
        ? geocodeResponse(url)
        : jsonResponse(400, {
            code: 'validation.invalid',
            detail: 'Invalid input.',
            fields: { non_field_errors: ['Origin and destination must be different places.'] },
          }),
    )
    renderWithProviders(<App />)

    await fillAndSubmit(user)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Origin and destination must be different places.')
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
  })

  it('shows field errors inline and the non-field message in the alert', async () => {
    const user = userEvent.setup()
    mockFetch((url) =>
      isGeocodeUrl(url)
        ? geocodeResponse(url)
        : jsonResponse(400, {
            code: 'validation.invalid',
            detail: 'Invalid input.',
            fields: {
              load_weight_lb: ['Ensure this value is less than or equal to 80000.'],
              non_field_errors: ['Origin and destination must be different places.'],
            },
          }),
    )
    renderWithProviders(<App />)

    await fillAndSubmit(user)

    expect(
      await screen.findByText('Ensure this value is less than or equal to 80000.'),
    ).toBeVisible()
    expect(screen.getByLabelText(/Load weight/)).toHaveAttribute('aria-invalid', 'true')
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Origin and destination must be different places.')
    expect(alert).toHaveTextContent('Fix the highlighted fields')
  })
})
