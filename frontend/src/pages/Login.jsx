import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import api from '../services/api'
import { useToast } from '../services/toast.jsx'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()
  const toast = useToast()
  // Determine backend origin for social auth redirects
  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
  let serverOrigin = 'http://localhost:8000'
  try { serverOrigin = new URL(apiBase).origin } catch (_) {}

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      setSubmitting(true)
      const { data } = await api.post('/auth/login/', { email, username: email, password })
      // Debug: log keys to help diagnose
      // eslint-disable-next-line no-console
      console.log('login response keys:', Object.keys(data || {}))
      const access = data.access || data.access_token || data.accessToken || data.token
      const refresh = data.refresh || data.refresh_token || data.refreshToken
      const key = data.key
      if (access) localStorage.setItem('access', access)
      if (refresh) localStorage.setItem('refresh', refresh)
      if (key) localStorage.setItem('token_key', key)
      if (access) {
        // Ensure subsequent requests include the token immediately
        api.defaults.headers.Authorization = `Bearer ${access}`
      } else if (key) {
        api.defaults.headers.Authorization = `Token ${key}`
      }
      // After successful login, auto-apply any pending profile updates
      try {
        const pendingRaw = localStorage.getItem('pending_profile')
        if (pendingRaw) {
          const pending = JSON.parse(pendingRaw || '{}')
          const body = {}
          if (pending.full_name) body.full_name = pending.full_name
          if (pending.phone) body.phone = pending.phone
          if (Object.keys(body).length > 0) {
            await api.patch('/profile/', body)
          }
          // Optional: pending photo upload if stored as base64 data URL in localStorage
          const pendingPhoto = localStorage.getItem('pending_photo')
          if (pendingPhoto) {
            try {
              const form = new FormData()
              // If pending_photo is a data URL, convert to Blob
              const toBlob = (dataUrl) => {
                const arr = dataUrl.split(',')
                const mime = arr[0].match(/:(.*?);/)[1]
                const bstr = atob(arr[1])
                let n = bstr.length
                const u8arr = new Uint8Array(n)
                while (n--) u8arr[n] = bstr.charCodeAt(n)
                return new Blob([u8arr], { type: mime })
              }
              const blob = pendingPhoto.startsWith('data:') ? toBlob(pendingPhoto) : new Blob([], { type: 'application/octet-stream' })
              form.append('photo', blob, 'profile-photo')
              await api.post('/profile/photo/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
            } catch (e) {
              // no-op if photo upload fails
            }
          }
          // Clean up pending data
          localStorage.removeItem('pending_profile')
          localStorage.removeItem('pending_photo')
        }
      } catch (e) {
        // Ignore profile apply errors to not block login UX
      }
      try {
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new Event('auth-changed'))
          window.dispatchEvent(new Event('storage'))
        }
      } catch(_) {}
      navigate('/dashboard')
      toast.success('Logged in successfully')
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Login failed'
      setError(msg)
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 520, margin: '40px auto' }}>
      <div className="card">
        <div className="card-body">
          <h2 style={{ marginTop: 0, marginBottom: 8 }}>Login</h2>
          <p style={{ color: 'var(--muted)', marginTop: 0 }}>Welcome back. Enter your credentials to continue.</p>
          <form onSubmit={onSubmit} className="stack" noValidate>
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input
                id="email"
                className="input"
                value={email}
                onChange={e => setEmail(e.target.value)}
                type="email"
                required
                autoComplete="email"
                disabled={submitting}
                aria-invalid={!!error}
              />
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <input
                id="password"
                className="input"
                value={password}
                onChange={e => setPassword(e.target.value)}
                type="password"
                required
                autoComplete="current-password"
                disabled={submitting}
                aria-invalid={!!error}
              />
            </div>
            {error && (
                            <div role="alert" style={{ color: 'var(--text)', background: 'var(--error-bg)', border: '1px solid var(--error)', padding: '10px 12px', borderRadius: 10 }}>
                {error}
              </div>
            )}
            <button type="submit" className="btn btn-primary" disabled={submitting} aria-busy={submitting}>
              {submitting ? 'Logging in…' : 'Login'}
            </button>
          </form>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 14 }}>
            <span style={{ color: 'var(--muted)', fontSize: 13 }}>No account?</span>
            <Link to="/register" className="btn btn-ghost">Register</Link>
          </div>
          <div className="divider" style={{ marginTop: 16, marginBottom: 8 }}>or continue with</div>
          <div className="grid-2-equal">
            <a className="btn btn-google" href={`${serverOrigin}/accounts/google/login/`} rel="noopener noreferrer">
              <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20.4 11.8c.1-.5.1-1 0-1.5H12v3.7h5.2c-.2 1.3-1.6 3.8-5.2 3.8-3.1 0-5.6-2.6-5.6-5.7S8.9 6.3 12 6.3c1.8 0 3 .8 3.7 1.5l2.5-2.4C16.8 3.9 14.6 3 12 3 7.5 3 3.8 6.6 3.8 11.1S7.5 19.2 12 19.2c6.9 0 7.9-4.9 7.4-7.4z" fill="#EA4335"/><path d="M12 3c-3.3 0-6.1 1.8-7.7 4.1l3 2.2C8.5 8 10.5 6.3 12 6.3c1.8 0 3 .8 3.7 1.5l2.5-2.4C16.8 3.9 14.6 3 12 3z" fill="#34A853"/><path d="M12 21c3.5 0 6.6-1.8 8.4-4.5l-3-2.3c-.9 1.9-2.9 3.2-5.2 3.2-3.6 0-5-2.5-5.2-3.8H3.8c.5 2.5 1.5 7.4 7.4 7.4.1 0 .1 0 .2 0z" fill="#4285F4"/><path d="M12 13.9c-3.6 0-5-2.5-5.2-3.8H3.8c.5 2.5 1.5 7.4 7.4 7.4.1 0 .1 0 .2 0 3.5 0 6.6-1.8 8.4-4.5l-3-2.3c-.9 1.9-2.9 3.2-5.2 3.2z" fill="#FBBC05"/>
              </svg>
              Continue with Google
            </a>
            <a className="btn btn-linkedin" href={`${serverOrigin}/accounts/linkedin_oauth2/login/`} rel="noopener noreferrer">
              <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20 2H4a2 2 0 00-2 2v16a2 2 0 002 2h16a2 2 0 002-2V4a2 2 0 00-2-2zM8 18H5V8h3v10zM6.5 6.5A1.5 1.5 0 118 5a1.5 1.5 0 01-1.5 1.5zM18 18h-3v-5.09c0-1.1-.79-2.01-1.75-2.01S11.5 11.8 11.5 13v5h-3V8h3v1.32c.6-.94 1.66-1.57 2.75-1.57C16.88 7.75 18 9.12 18 11.41V18z" fill="currentColor"/>
              </svg>
              Continue with LinkedIn
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
