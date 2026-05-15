import { Navigate, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'

import { useAuth } from './auth/AuthContext'
import Characters from './routes/Characters'
import Game from './routes/Game'
import Login from './routes/Login'
import Register from './routes/Register'

function RequireAuth({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  return token ? <>{children}</> : <Navigate to="/" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/characters"
        element={
          <RequireAuth>
            <Characters />
          </RequireAuth>
        }
      />
      <Route
        path="/play"
        element={
          <RequireAuth>
            <Game />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
