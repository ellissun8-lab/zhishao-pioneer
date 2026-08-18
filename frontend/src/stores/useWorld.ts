import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { WorldState } from '../types'

export function useWorld() {
  const [world, setWorld] = useState<WorldState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setWorld(await api.getWorld())
      setError(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '无法读取世界状态')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return { world, setWorld, loading, error, refresh }
}

