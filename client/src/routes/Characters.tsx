import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { http, HttpError } from '../api/http'
import { useAuth } from '../auth/AuthContext'
import type { Player } from '../types/api'

export default function Characters() {
  const { token, clear } = useAuth()
  const navigate = useNavigate()
  const [characters, setCharacters] = useState<Player[] | null>(null)
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  // Load existing characters once.
  useEffect(() => {
    if (!token) return
    let cancelled = false
    http<Player[]>('/characters', { token }).then(
      (rows) => {
        if (!cancelled) setCharacters(rows)
      },
      (err: unknown) => {
        if (cancelled) return
        if (err instanceof HttpError && err.status === 401) {
          clear()
          navigate('/', { replace: true })
          return
        }
        setError(err instanceof Error ? err.message : 'Failed to load characters.')
      },
    )
    return () => {
      cancelled = true
    }
  }, [token, clear, navigate])

  const create = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setCreating(true)
    try {
      const created = await http<Player>('/characters', {
        method: 'POST',
        body: { name },
        token,
      })
      setCharacters((prev) => (prev ? [...prev, created] : [created]))
      setName('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create character.')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-lg flex-col gap-4 px-4 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-100">Your characters</h1>
        <button
          onClick={() => {
            clear()
            navigate('/', { replace: true })
          }}
          className="text-xs text-zinc-500 hover:text-zinc-300"
        >
          Sign out
        </button>
      </div>

      {characters === null && <p className="text-sm text-zinc-500">Loading…</p>}

      {characters && characters.length > 0 && (
        <ul className="space-y-2">
          {characters.map((c) => (
            <li
              key={c.id}
              className="flex items-center justify-between rounded border border-zinc-800 bg-zinc-900 px-3 py-2"
            >
              <div>
                <div className="text-zinc-100">{c.name}</div>
                <div className="text-xs text-zinc-500">currently in {c.currentRoomId}</div>
              </div>
              <button
                onClick={() => navigate('/play')}
                className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-zinc-950 hover:bg-emerald-500"
              >
                Play
              </button>
            </li>
          ))}
        </ul>
      )}

      {characters && characters.length === 0 && (
        <p className="text-sm text-zinc-400">
          You don&apos;t have any characters yet. Make one below to start playing.
        </p>
      )}

      <form
        onSubmit={create}
        className="space-y-2 rounded border border-zinc-800 bg-zinc-900 p-4"
      >
        <h2 className="text-sm font-medium text-zinc-200">Create a new character</h2>
        <label className="block">
          <span className="text-xs text-zinc-400">Name</span>
          <input
            type="text"
            required
            minLength={3}
            maxLength={24}
            pattern="^[A-Za-z][A-Za-z0-9_-]*$"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1 outline-none focus:border-emerald-500"
            placeholder="e.g. Ada"
          />
          <span className="mt-1 block text-[10px] text-zinc-600">
            3–24 chars, must start with a letter.
          </span>
        </label>

        {error && <p className="text-sm text-rose-400">{error}</p>}

        <button
          type="submit"
          disabled={creating}
          className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-zinc-950 hover:bg-emerald-500 disabled:opacity-50"
        >
          {creating ? 'Creating…' : 'Create character'}
        </button>
      </form>
    </div>
  )
}
