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

// Response interceptor to transform errors
apiClient.interceptors.response.use(
  (response) => response,
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

