import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import api from '../services/api'
import { useToast } from '../services/toast.jsx'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const toast = useToast()

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    try {
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
    }
  }

  return (
    <div style={{ maxWidth: 420, margin: '40px auto', fontFamily: 'sans-serif' }}>
      <h2>Login</h2>
      <form onSubmit={onSubmit}>
        <div style={{ marginBottom: 12 }}>
          <label>Email</label>
          <input value={email} onChange={e => setEmail(e.target.value)} type="email" required style={{ width: '100%' }} autoComplete="email" />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label>Password</label>
          <input value={password} onChange={e => setPassword(e.target.value)} type="password" required style={{ width: '100%' }} autoComplete="current-password" />
        </div>
        {error && <div style={{ color: 'red', marginBottom: 12 }}>{error}</div>}
        <button type="submit">Login</button>
      </form>
      <p style={{ marginTop: 12 }}>No account? <Link to="/register">Register</Link></p>
      <hr style={{ margin: '16px 0' }} />
      <a href="http://localhost:8000/accounts/google/login/">Login with Google</a><br />
      <a href="http://localhost:8000/accounts/linkedin_oauth2/login/">Login with LinkedIn</a>
    </div>
  )
}
