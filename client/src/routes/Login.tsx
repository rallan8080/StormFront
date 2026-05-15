import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { http, HttpError } from '../api/http'
import { useAuth } from '../auth/AuthContext'
import type { TokenPair } from '../types/api'

export default function Login() {
  const { setTokens } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setPending(true)
    try {
      const pair = await http<TokenPair>('/auth/login', {
        method: 'POST',
        body: { email, password },
      })
      setTokens(pair)
      navigate('/characters', { replace: true })
    } catch (err) {
      setError(
        err instanceof HttpError && err.status === 401
          ? 'Invalid email or password.'
          : err instanceof Error
            ? err.message
            : 'Login failed.',
      )
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex h-full items-center justify-center px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-4 rounded-lg border border-zinc-800 bg-zinc-900 p-6"
      >
        <h1 className="text-lg font-semibold text-zinc-100">Sign in to StormFront</h1>

        <label className="block">
          <span className="text-xs text-zinc-400">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1 outline-none focus:border-emerald-500"
          />
        </label>

        <label className="block">
          <span className="text-xs text-zinc-400">Password</span>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1 outline-none focus:border-emerald-500"
          />
        </label>

        {error && <p className="text-sm text-rose-400">{error}</p>}

        <button
          type="submit"
          disabled={pending}
          className="w-full rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-zinc-950 hover:bg-emerald-500 disabled:opacity-50"
        >
          {pending ? 'Signing in…' : 'Sign in'}
        </button>

        <p className="text-xs text-zinc-500">
          New here?{' '}
          <Link to="/register" className="text-emerald-400 hover:underline">
            Create an account
          </Link>
        </p>
      </form>
    </div>
  )
}
