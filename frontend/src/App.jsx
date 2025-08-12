import React, { useEffect, useState } from 'react'
import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import api from './services/api'
import Login from './pages/Login.jsx'
import Profile from './pages/Profile.jsx'
import Generate from './pages/Generate.jsx'
import Editor from './pages/Editor.jsx'

function Home() {
  return (
    <div>
      <h2>Welcome to ResumeAI</h2>
      <p>Please <Link to="/login">Login</Link> or <Link to="/register">Register</Link>.</p>
    </div>
  )
}

function Dashboard() {
  const navigate = useNavigate()
  const logout = () => {
    localStorage.removeItem('access'); localStorage.removeItem('refresh');
    navigate('/login')
  }
  return (
    <div>
      <h2>Dashboard</h2>
      <p>You're logged in.</p>
      <button onClick={logout}>Logout</button>
    </div>
  )
}

export default function App() {
  const [status, setStatus] = useState('loading...')
  useEffect(() => {
    api.get('/health/').then(r => setStatus(r.data.status)).catch(() => setStatus('error'))
  }, [])
  return (
    <div style={{fontFamily:'sans-serif', padding: 24}}>
      <header style={{display:'flex', gap:12, alignItems:'center'}}>
        <h1 style={{marginRight:16}}>ResumeAI</h1>
        <Link to="/">Home</Link>
        <Link to="/login">Login</Link>
        <Link to="/register">Register</Link>
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/generate">Generate</Link>
        <Link to="/profile">Profile</Link>
        <span style={{marginLeft:'auto'}}>Health: {status}</span>
      </header>
      <main style={{marginTop:16}}>
        <Routes>
          <Route path="/" element={<Home/>} />
          <Route path="/login" element={<Login/>} />
          <Route path="/register" element={<Register/>} />
          <Route path="/dashboard" element={<Dashboard/>} />
          <Route path="/generate" element={<Generate/>} />
          <Route path="/profile" element={<Profile/>} />
          <Route path="/documents/:id/edit" element={<Editor/>} />
        </Routes>
      </main>
    </div>
  )
}

function Register() {
  const [email, setEmail] = useState('')
  const [password1, setPassword1] = useState('')
  const [password2, setPassword2] = useState('')
  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('')
  const [photoFile, setPhotoFile] = useState(null)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const onSubmit = async (e) => {
    e.preventDefault(); setError('')
    try {
      const resp = await api.post('/auth/registration/', { email, password1, password2 })
      const data = resp?.data || {}
      // dj-rest-auth often returns 204 No Content on success
      if (resp?.status === 204) {
        localStorage.setItem('pending_profile', JSON.stringify({ full_name: fullName, phone }))
        // If a photo was chosen, persist it as a data URL for upload after login
        if (photoFile) {
          const toDataUrl = (file) => new Promise((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = () => resolve(reader.result)
            reader.onerror = reject
            reader.readAsDataURL(file)
          })
          try {
            const dataUrl = await toDataUrl(photoFile)
            if (typeof dataUrl === 'string') localStorage.setItem('pending_photo', dataUrl)
          } catch {}
        }
        navigate('/login')
        return
      }
      // Try to extract any tokens that may be returned on registration
      const access = data?.access || data?.access_token || data?.accessToken || data?.token
      const refresh = data?.refresh || data?.refresh_token || data?.refreshToken
      const key = data?.key
      if (access) localStorage.setItem('access', access)
      if (refresh) localStorage.setItem('refresh', refresh)
      if (key) localStorage.setItem('token_key', key)
      if (access) {
        api.defaults.headers.Authorization = `Bearer ${access}`
      } else if (key) {
        api.defaults.headers.Authorization = `Token ${key}`
      }

      // If we have an auth token now, apply profile updates immediately
      if (access || key) {
        try {
          if (fullName || phone) {
            await api.patch('/profile/', { full_name: fullName, phone: phone })
          }
          if (photoFile) {
            const form = new FormData()
            form.append('photo', photoFile)
            await api.post('/profile/photo/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
          }
          navigate('/profile')
          return
        } catch (e2) {
          // Fall through to login
        }
      }
      // Otherwise, store pending profile basics to apply right after login
      localStorage.setItem('pending_profile', JSON.stringify({ full_name: fullName, phone }))
      if (photoFile) {
        const toDataUrl = (file) => new Promise((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(reader.result)
          reader.onerror = reject
          reader.readAsDataURL(file)
        })
        try {
          const dataUrl = await toDataUrl(photoFile)
          if (typeof dataUrl === 'string') localStorage.setItem('pending_photo', dataUrl)
        } catch {}
      }
      navigate('/login')
    } catch (err) {
      const data = err?.response?.data
      const msg = typeof data === 'string' ? data : (data?.detail || JSON.stringify(data))
      setError(msg || 'Registration failed')
    }
  }
  return (
    <div style={{ maxWidth: 420, margin: '40px auto' }}>
      <h2>Register</h2>
      <form onSubmit={onSubmit}>
        <div style={{ marginBottom: 12 }}>
          <label>Email</label>
          <input type="email" value={email} onChange={e=>setEmail(e.target.value)} required style={{width:'100%'}} autoComplete="email"/>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label>Full name</label>
          <input type="text" value={fullName} onChange={e=>setFullName(e.target.value)} style={{width:'100%'}} autoComplete="name"/>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label>Phone</label>
          <input type="tel" value={phone} onChange={e=>setPhone(e.target.value)} style={{width:'100%'}} autoComplete="tel"/>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label>Password</label>
          <input type="password" value={password1} onChange={e=>setPassword1(e.target.value)} required style={{width:'100%'}} autoComplete="new-password"/>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label>Confirm Password</label>
          <input type="password" value={password2} onChange={e=>setPassword2(e.target.value)} required style={{width:'100%'}} autoComplete="new-password"/>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label>Profile Photo (optional)</label>
          <input type="file" accept="image/*" onChange={e=>setPhotoFile(e.target.files?.[0] || null)} />
        </div>
        {error && <div style={{ color: 'red', marginBottom: 12 }}>{error}</div>}
        <button type="submit">Create account</button>
      </form>
    </div>
  )
}
