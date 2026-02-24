import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { APIErrorException, ensureCsrfToken } from './api'

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
