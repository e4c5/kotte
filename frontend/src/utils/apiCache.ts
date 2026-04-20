/**
 * Simple in-memory cache for API requests.
 */

interface CacheEntry<T> {
  data: T
  timestamp: number
  ttl: number
}

class ApiCache {
  // Heterogeneous values keyed by string — the per-call generic on `get<T>` /
  // `set<T>` carries the actual type back to callers; widening the map's value
  // type to `unknown` here would force a cast at every call site.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private readonly cache: Map<string, CacheEntry<any>> = new Map()

  get<T>(key: string): T | null {
    const entry = this.cache.get(key)
    if (!entry) return null

    const now = Date.now()
    if (now - entry.timestamp > entry.ttl) {
      this.cache.delete(key)
      return null
    }

    return entry.data
  }

  set<T>(key: string, data: T, ttlMs: number): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl: ttlMs,
    })
  }

  delete(key: string): void {
    this.cache.delete(key)
  }

  clear(prefix?: string): void {
    if (prefix) {
      for (const key of this.cache.keys()) {
        if (key.startsWith(prefix)) {
          this.cache.delete(key)
        }
      }
    } else {
      this.cache.clear()
    }
  }
}

export const apiCache = new ApiCache()
