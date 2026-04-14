import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { APIErrorException, ensureCsrfToken, request } from './api'

describe('APIErrorException', () => {
  it('sets name, message, and custom properties', () => {
    const err = new APIErrorException(
      'VALIDATION_ERROR',
      'validation',
      'Invalid input',
      { field: 'name' },
      'req-123',
      false
    )
    expect(err.name).toBe('APIErrorException')
    expect(err.message).toBe('Invalid input')
    expect(err.code).toBe('VALIDATION_ERROR')
    expect(err.category).toBe('validation')
    expect(err.details).toEqual({ field: 'name' })
    expect(err.requestId).toBe('req-123')
    expect(err.retryable).toBe(false)
  })

  it('defaults retryable to false', () => {
    const err = new APIErrorException('ERR', 'client', 'msg')
    expect(err.retryable).toBe(false)
  })
})

describe('ensureCsrfToken', () => {
  const originalSessionStorage = global.sessionStorage

  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
    originalSessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns existing token from sessionStorage', async () => {
    originalSessionStorage.setItem('csrf_token', 'existing-token')
    const token = await ensureCsrfToken()
    expect(token).toBe('existing-token')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('fetches and stores token when sessionStorage is empty', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ csrf_token: 'new-token' }),
    } as Response)

    const token = await ensureCsrfToken()
    expect(token).toBe('new-token')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/auth/csrf-token'),
      expect.objectContaining({ credentials: 'include' })
    )
    expect(originalSessionStorage.getItem('csrf_token')).toBe('new-token')
  })

  it('returns null when response has no csrf_token', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    } as Response)

    const token = await ensureCsrfToken()
    expect(token).toBeNull()
  })

  it('returns null on fetch error', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockRejectedValueOnce(new Error('Network error'))

    const token = await ensureCsrfToken()
    expect(token).toBeNull()
  })
})

describe('request', () => {
  const originalSessionStorage = globalThis.sessionStorage

  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
    originalSessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('retries on CSRF failure after clearing stale token', async () => {
    const mockFetch = vi.mocked(fetch)
    originalSessionStorage.setItem('csrf_token', 'stale-token')

    // First call: 403 CSRF failure
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      text: async () => JSON.stringify({ error: { message: 'CSRF token validation failed' } }),
    } as Response)

    // Second call: Fetch fresh CSRF token
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ csrf_token: 'new-token' }),
    } as Response)

    // Third call: Successful retry with new token
    mockFetch.mockResolvedValueOnce({
      ok: true,
      text: async () => JSON.stringify({ result: 'success' }),
    } as Response)

    const result = await request('POST', '/test', { data: 1 })
    expect(result.data).toEqual({ result: 'success' })

    // Check that sessionStorage was cleared and then updated
    expect(originalSessionStorage.getItem('csrf_token')).toBe('new-token')

    // Verify fetch calls
    expect(mockFetch).toHaveBeenCalledTimes(3)
    
    // First call used stale token
    expect(mockFetch.mock.calls[0][1]?.headers).toMatchObject({ 'X-CSRF-Token': 'stale-token' })
    
    // Second call was for the new token
    expect(mockFetch.mock.calls[1][0]).toContain('/auth/csrf-token')
    
    // Third call used fresh token
    expect(mockFetch.mock.calls[2][1]?.headers).toMatchObject({ 'X-CSRF-Token': 'new-token' })
  })
})
