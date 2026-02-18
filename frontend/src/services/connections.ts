/**
 * API service for saved database connections.
 */

import api from './api';

export interface SavedConnection {
  id: string;
  name: string;
  host: string;
  port: number;
  database: string;
  created_at: string;
  updated_at: string;
}

export interface SavedConnectionDetail extends SavedConnection {
  username: string;
  password: string;
  sslmode?: string;
}

export interface SaveConnectionRequest {
  name: string;
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
  sslmode?: string;
}

/**
 * Save a database connection (encrypted).
 */
export async function saveConnection(
  connection: SaveConnectionRequest
): Promise<SavedConnection> {
  const response = await api.post<SavedConnection>('/connections', connection);
  return response.data;
}

/**
 * List all saved connections for the current user.
 */
export async function listConnections(): Promise<SavedConnection[]> {
  const response = await api.get<SavedConnection[]>('/connections');
  return response.data;
}

/**
 * Get a saved connection with decrypted credentials.
 */
export async function getConnection(connectionId: string): Promise<SavedConnectionDetail> {
  const response = await api.get<SavedConnectionDetail>(
    `/connections/${connectionId}`
  );
  return response.data;
}

/**
 * Delete a saved connection.
 */
export async function deleteConnection(connectionId: string): Promise<void> {
  await api.delete(`/connections/${connectionId}`);
}

