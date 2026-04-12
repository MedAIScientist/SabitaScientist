import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

export function Setup() {
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
      await api.createAdmin(username, password)
      await login(username, password)
      navigate('/projects')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Setup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', fontFamily: 'system-ui' }}>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12, width: 320 }}>
        <h1 style={{ margin: 0 }}>Welcome to EvoScientist PM</h1>
        <p style={{ color: '#666', margin: 0 }}>Create the first admin account to get started.</p>
        {error && <p style={{ color: 'red', margin: 0 }}>{error}</p>}
        <input
          placeholder="Admin username" value={username} onChange={e => setUsername(e.target.value)}
          required style={{ padding: 8, fontSize: 21 }}
        />
        <input
          type="password" placeholder="Password (min 6 chars)" value={password} onChange={e => setPassword(e.target.value)}
          required minLength={6} style={{ padding: 8, fontSize: 21 }}
        />
        <button type="submit" disabled={loading} style={{ padding: 10, fontSize: 21, cursor: 'pointer' }}>
          {loading ? 'Creating\u2026' : 'Create admin account'}
        </button>
      </form>
    </div>
  )
}
