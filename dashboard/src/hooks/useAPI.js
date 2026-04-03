import { useState, useEffect, useCallback } from 'react'

export function useAPI(fetchFn, deps = [], interval = null) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const result = await fetchFn()
      setData(result)
      setError(null)
    } catch (err) {
      setError(err.message || 'Failed to fetch')
    } finally {
      setLoading(false)
    }
  }, deps)

  useEffect(() => {
    load()
    if (interval) {
      const id = setInterval(load, interval)
      return () => clearInterval(id)
    }
  }, [load, interval])

  return { data, loading, error, refetch: load }
}
