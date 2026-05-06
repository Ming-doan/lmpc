import { useState, useCallback } from 'react'

const KEY = 'lmpc_token'

export function useAuth() {
  const [token, setTokenState] = useState<string | null>(() => localStorage.getItem(KEY))

  const setToken = useCallback((t: string) => {
    localStorage.setItem(KEY, t)
    setTokenState(t)
  }, [])

  const clearToken = useCallback(() => {
    localStorage.removeItem(KEY)
    setTokenState(null)
  }, [])

  return { token, setToken, clearToken, isAuthenticated: !!token }
}
