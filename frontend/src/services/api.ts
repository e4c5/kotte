/**
 * API client for backend communication.
 */

import axios, { AxiosInstance, AxiosError } from 'axios'

export interface APIError {
  error: {
    code: string
    category: string
    message: string
    details?: Record<string, unknown>
    request_id: string
    timestamp: string
    retryable: boolean
  }
}

export class APIErrorException extends Error {
  constructor(
    public code: string,
    public category: string,
    message: string,
    public details?: Record<string, unknown>,
    public requestId?: string,
    public retryable: boolean = false
  ) {
    super(message)
    this.name = 'APIErrorException'
  }
}

// Create axios instance with defaults
const apiClient: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  withCredentials: true, // Important for session cookies
  headers: {
    'Content-Type': 'application/json',
  },
})

/** Fetch and store CSRF token using the same client so cookies are sent. Exported for use by fetch-based APIs (e.g. stream). */
export async function ensureCsrfToken(): Promise<string | null> {
  let token = sessionStorage.getItem('csrf_token')
  if (token) return token
  try {
    const response = await apiClient.get<{ csrf_token: string }>('/auth/csrf-token')
    token = response.data?.csrf_token ?? null
    if (token) sessionStorage.setItem('csrf_token', token)
    return token
  } catch {
    return null
  }
}

// Request interceptor to add CSRF token
apiClient.interceptors.request.use(
  async (config) => {
    const method = config.method?.toLowerCase()
    const needsCsrf = method && ['post', 'put', 'patch', 'delete'].includes(method)
    if (!needsCsrf) return config

    let csrfToken = sessionStorage.getItem('csrf_token')
    if (!csrfToken) {
      csrfToken = await ensureCsrfToken()
    }
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: update stored token, and on 403 CSRF refetch token and retry once
apiClient.interceptors.response.use(
  (response) => {
    if (response.data?.csrf_token) {
      sessionStorage.setItem('csrf_token', response.data.csrf_token)
    }
    return response
  },
  async (error: AxiosError<APIError>) => {
    const apiError = error.response?.data?.error
    const isCsrfFailure =
      error.response?.status === 403 &&
      apiError?.message === 'CSRF token validation failed'

    if (isCsrfFailure && error.config && !(error.config as { _csrfRetry?: boolean })._csrfRetry) {
      const token = await ensureCsrfToken()
      if (token) {
        (error.config as { _csrfRetry?: boolean })._csrfRetry = true
        error.config.headers['X-CSRF-Token'] = token
        return apiClient.request(error.config)
      }
    }

    if (apiError) {
      throw new APIErrorException(
        apiError.code,
        apiError.category,
        apiError.message,
        apiError.details,
        apiError.request_id,
        apiError.retryable
      )
    }
    throw error
  }
)

export default apiClient

