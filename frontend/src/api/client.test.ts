import { afterEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { jsonResponse, mockFetch } from '@/test/utils'
import { ApiError, getJson, postJson } from './client'
import { geocodeUrl } from './hooks'

const Schema = z.object({ ok: z.boolean() })

afterEach(() => {
  vi.restoreAllMocks()
})

async function caught(promise: Promise<unknown>) {
  try {
    await promise
  } catch (error) {
    return error
  }
  throw new Error('expected the request to fail')
}

describe('api client', () => {
  it('parses a valid body', async () => {
    mockFetch(() => jsonResponse(200, { ok: true }))
    await expect(getJson('/api/x', Schema)).resolves.toEqual({ ok: true })
  })

  it('turns a network failure into status 0', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    const error = await caught(getJson('/api/x', Schema))
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ code: 'network.unreachable', status: 0, retryable: true })
  })

  it('names a non-JSON error body by status', async () => {
    mockFetch(() => new Response('<html>Bad Gateway</html>', { status: 502 }))
    const error = await caught(postJson('/api/x', {}, Schema))
    expect(error).toMatchObject({ code: 'http.502', status: 502, retryable: true })
  })

  it('keeps the backend code, detail and flattened fields', async () => {
    mockFetch(() =>
      jsonResponse(400, {
        code: 'validation.invalid',
        detail: 'Invalid input.',
        fields: { origin: { lat: ['Too big.'] }, load_weight_lb: ['Too heavy.'] },
      }),
    )
    const error = await caught(postJson('/api/x', {}, Schema))
    expect(error).toMatchObject({
      code: 'validation.invalid',
      status: 400,
      retryable: false,
      fields: { 'origin.lat': ['Too big.'], load_weight_lb: ['Too heavy.'] },
    })
  })

  it('rejects a body that does not match the schema', async () => {
    mockFetch(() => jsonResponse(200, { ok: 'yes' }))
    const error = await caught(getJson('/api/x', Schema))
    expect(error).toMatchObject({ code: 'client.bad_response', status: 200 })
  })

  it('rethrows an abort from fetch', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new DOMException('Aborted', 'AbortError'))
    const error = await caught(getJson('/api/x', Schema))
    expect(error).not.toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ name: 'AbortError' })
  })

  it('rethrows an abort while reading the body', async () => {
    const response = jsonResponse(200, { ok: true })
    vi.spyOn(response, 'json').mockRejectedValue(new DOMException('Aborted', 'AbortError'))
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
    const error = await caught(getJson('/api/x', Schema))
    expect(error).toMatchObject({ name: 'AbortError' })
  })

  it('encodes the geocode query', () => {
    expect(geocodeUrl('St. Louis, MO & 5th/Main')).toBe(
      '/api/geocode?q=St.+Louis%2C+MO+%26+5th%2FMain',
    )
  })
})
