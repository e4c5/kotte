/**
 * Authentication API client.
 */

import apiClient from './api'

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  user_id: string
  username: string
  authenticated: boolean
}

export interface LogoutResponse {
  logged_out: boolean
}

export interface UserInfo {
  user_id: string
  username: string
}

export const authAPI = {
  login: async (request: LoginRequest): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>('/auth/login', request)
    return response.data
  },

  logout: async (): Promise<LogoutResponse> => {
    const response = await apiClient.post<LogoutResponse>('/auth/logout', {})
    return response.data
  },

  getCurrentUser: async (): Promise<UserInfo> => {
    const response = await apiClient.get<UserInfo>('/auth/me')
    return response.data
  },
}


