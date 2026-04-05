import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(username, password)
      navigate('/projects')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', fontFamily: 'system-ui' }}>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12, width: 300 }}>
        <h1 style={{ margin: 0 }}>EvoScientist PM</h1>
        {error && <p style={{ color: 'red', margin: 0 }}>{error}</p>}
        <input
          placeholder="Username" value={username} onChange={e => setUsername(e.target.value)}
          required style={{ padding: 8, fontSize: 14 }}
        />
        <input
          type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)}
          required style={{ padding: 8, fontSize: 14 }}
        />
        <button type="submit" disabled={loading} style={{ padding: 10, fontSize: 14, cursor: 'pointer' }}>
          {loading ? 'Logging in\u2026' : 'Log in'}
        </button>
      </form>
    </div>
  )
}
