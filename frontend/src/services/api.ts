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

// Request interceptor to add CSRF token
apiClient.interceptors.request.use(
  async (config) => {
    // Get CSRF token from session storage or fetch it
    let csrfToken = sessionStorage.getItem('csrf_token')
    
    if (!csrfToken) {
      try {
        // Fetch CSRF token
        const response = await axios.get('/api/v1/auth/csrf-token', {
          withCredentials: true,
        })
        csrfToken = response.data.csrf_token
        if (csrfToken) {
          sessionStorage.setItem('csrf_token', csrfToken)
        }
      } catch (error) {
        // If CSRF fetch fails, continue without token (might be first request)
        console.warn('Failed to fetch CSRF token:', error)
      }
    }
    
    // Add CSRF token to protected methods
    if (csrfToken && config.method && ['post', 'put', 'patch', 'delete'].includes(config.method.toLowerCase())) {
      config.headers['X-CSRF-Token'] = csrfToken
    }
    
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor to transform errors and update CSRF token
apiClient.interceptors.response.use(
  (response) => {
    // Update CSRF token if provided in response
    if (response.data?.csrf_token) {
      sessionStorage.setItem('csrf_token', response.data.csrf_token)
    }
    return response
  },
  (error: AxiosError<APIError>) => {
    if (error.response?.data?.error) {
      const apiError = error.response.data.error
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

