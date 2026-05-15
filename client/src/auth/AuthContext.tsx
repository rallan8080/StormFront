import { createContext, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import type { TokenPair } from '../types/api'

type AuthContextValue = {
  token: string | null
  setTokens: (pair: TokenPair) => void
  clear: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

const STORAGE_KEY = 'stormfront.auth'

function readStoredToken(): string | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<TokenPair>
    return typeof parsed.accessToken === 'string' ? parsed.accessToken : null
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(readStoredToken)

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      setTokens: (pair) => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(pair))
        setToken(pair.accessToken)
      },
      clear: () => {
        localStorage.removeItem(STORAGE_KEY)
        setToken(null)
      },
    }),
    [token],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
