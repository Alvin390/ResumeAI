import React, { useEffect, useState } from 'react'
import { Routes, Route, Link, useNavigate, Navigate, useLocation } from 'react-router-dom'
import api from './services/api'
import { useToast } from './services/toast.jsx'
import Login from './pages/Login.jsx'
import Profile from './pages/Profile.jsx'
import Generate from './pages/Generate.jsx'
import Editor from './pages/Editor.jsx'
import Documents from './pages/Documents.jsx'
import Layout from './components/Layout.jsx'
import { AnimatePresence, motion } from 'framer-motion'

function Home() {
  return (
    <div className="hero">
      <h2>Craft ATS-optimized CVs and tailored cover letters</h2>
      <p>Upload your CV, paste a job description, and let AI generate polished, on-brand documents. Versioned, exportable, and private.</p>
      <div className="cta">
        <Link to="/login" className="btn btn-primary">Login</Link>
        <Link to="/register" className="btn">Register</Link>
      </div>
    </div>
  )
}

function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState({ cvs: 0, covers: 0, generations: 0 })
  const [recentDocs, setRecentDocs] = useState([])
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const [cvRes, coverRes] = await Promise.all([
          api.get('/cv/?doc_type=cv'),
          api.get('/cv/?doc_type=cover')
        ])
        setStats({
          cvs: cvRes.data?.length || 0,
          covers: coverRes.data?.length || 0,
          generations: (cvRes.data?.length || 0) + (coverRes.data?.length || 0)
        })
        // Get 3 most recent documents
        const allDocs = [...(cvRes.data || []), ...(coverRes.data || [])]
        const recent = allDocs
          .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
          .slice(0, 3)
        setRecentDocs(recent)
      } catch (e) {
        console.error('Failed to load dashboard data:', e)
      } finally {
        setLoading(false)
      }
    }
    loadDashboard()
  }, [])

  const quickActions = [
    { title: 'Generate New', desc: 'Create CV & Cover Letter', icon: '✨', path: '/generate', color: 'var(--primary)' },
    { title: 'My Documents', desc: 'View all documents', icon: '📄', path: '/documents', color: 'var(--success)' },
    { title: 'Profile', desc: 'Update your profile', icon: '👤', path: '/profile', color: 'var(--muted)' }
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      style={{ maxWidth: 1080, margin: '0 auto' }}
    >
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ 
          fontSize: 32, 
          fontWeight: 700, 
          margin: '0 0 8px 0',
          background: 'linear-gradient(90deg, var(--primary), var(--success))',
          WebkitBackgroundClip: 'text',
          backgroundClip: 'text',
          color: 'transparent'
        }}>
          Welcome back!
        </h2>
        <p style={{ color: 'var(--muted)', margin: 0, fontSize: 16 }}>
          Ready to create your next professional document?
        </p>
      </div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 32 }}>
        <motion.div 
          className="card"
          whileHover={{ scale: 1.02 }}
          transition={{ duration: 0.2 }}
        >
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>📊</div>
            <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--primary)' }}>{loading ? '...' : stats.cvs}</div>
            <div style={{ fontSize: 14, color: 'var(--muted)' }}>CVs Created</div>
          </div>
        </motion.div>
        <motion.div 
          className="card"
          whileHover={{ scale: 1.02 }}
          transition={{ duration: 0.2 }}
        >
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>💼</div>
            <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--success)' }}>{loading ? '...' : stats.covers}</div>
            <div style={{ fontSize: 14, color: 'var(--muted)' }}>Cover Letters</div>
          </div>
        </motion.div>
        <motion.div 
          className="card"
          whileHover={{ scale: 1.02 }}
          transition={{ duration: 0.2 }}
        >
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>🎯</div>
            <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--text)' }}>{loading ? '...' : stats.generations}</div>
            <div style={{ fontSize: 14, color: 'var(--muted)' }}>Total Documents</div>
          </div>
        </motion.div>
      </div>

      <div className="grid-2" style={{ gap: 24, alignItems: 'start' }}>
        {/* Quick Actions */}
        <div>
          <h3 style={{ margin: '0 0 16px 0', fontSize: 20, fontWeight: 600 }}>Quick Actions</h3>
          <div className="stack">
            {quickActions.map((action, i) => (
              <motion.div
                key={action.path}
                className="card"
                whileHover={{ scale: 1.02, borderColor: action.color }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate(action.path)}
                style={{ cursor: 'pointer', transition: 'border-color 0.2s ease' }}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1 }}
              >
                <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <div style={{ 
                    fontSize: 24, 
                    width: 48, 
                    height: 48, 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    background: 'var(--bg-elev)',
                    borderRadius: 12,
                    border: `2px solid ${action.color}`
                  }}>
                    {action.icon}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, marginBottom: 4 }}>{action.title}</div>
                    <div style={{ fontSize: 14, color: 'var(--muted)' }}>{action.desc}</div>
                  </div>
                  <div style={{ color: 'var(--muted)', fontSize: 18 }}>→</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Recent Documents */}
        <div>
          <h3 style={{ margin: '0 0 16px 0', fontSize: 20, fontWeight: 600 }}>Recent Documents</h3>
          {loading ? (
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center', color: 'var(--muted)' }}>
                Loading recent documents...
              </div>
            </div>
          ) : recentDocs.length === 0 ? (
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center', color: 'var(--muted)' }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>📝</div>
                <div>No documents yet</div>
                <div style={{ fontSize: 14, marginTop: 8 }}>
                  <Link to="/generate" style={{ color: 'var(--primary)' }}>Create your first document</Link>
                </div>
              </div>
            </div>
          ) : (
            <div className="stack">
              {recentDocs.map((doc, i) => (
                <motion.div
                  key={doc.id}
                  className="card"
                  whileHover={{ scale: 1.01 }}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                >
                  <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ 
                      fontSize: 20,
                      width: 36,
                      height: 36,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: doc.doc_type === 'cv' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                      borderRadius: 8,
                      color: doc.doc_type === 'cv' ? 'var(--primary)' : 'var(--success)'
                    }}>
                      {doc.doc_type === 'cv' ? '📄' : '💼'}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>
                        v{doc.version} — {doc.file_name}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                        {new Date(doc.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <Link 
                      to={`/documents/${doc.id}/edit`}
                      className="btn"
                      style={{ fontSize: 12, padding: '6px 12px' }}
                    >
                      Edit
                    </Link>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function RequireAuth({ children }) {
  const hasJwt = !!(localStorage.getItem('access') || localStorage.getItem('token_key'))
  if (!hasJwt) {
    return <Navigate to="/login" replace />
  }
  return children
}

export default function App() {
  const [status, setStatus] = useState('loading...')
  const [authed, setAuthed] = useState(() => !!(localStorage.getItem('access') || localStorage.getItem('token_key')))
  const location = useLocation()
  useEffect(() => {
    const url = (import.meta.env.VITE_API_URL || 'http://localhost:8000/api') + '/health/'
    fetch(url, { credentials: 'omit' })
      .then(async (r) => {
        if (!r.ok) throw new Error('health error')
        const d = await r.json().catch(() => ({}))
        setStatus(d?.status || 'ok')
      })
      .catch(() => setStatus('error'))
  }, [])
  useEffect(() => {
    const sync = () => setAuthed(!!(localStorage.getItem('access') || localStorage.getItem('token_key')))
    window.addEventListener('storage', sync)
    window.addEventListener('auth-changed', sync)
    return () => {
      window.removeEventListener('storage', sync)
      window.removeEventListener('auth-changed', sync)
    }
  }, [])
  const handleLogout = () => {
    try { api.logout() } catch(_) {}
    if (typeof window !== 'undefined' && window.location) {
      window.location.replace('/login')
    }
  }
  return (
    <Layout authed={authed} status={status} onLogout={handleLogout}>
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<Home/>} />
          <Route path="/login" element={<Login/>} />
          <Route path="/register" element={<Register/>} />
          <Route path="/dashboard" element={<RequireAuth><Dashboard/></RequireAuth>} />
          <Route path="/generate" element={<RequireAuth><Generate/></RequireAuth>} />
          <Route path="/documents" element={<RequireAuth><Documents/></RequireAuth>} />
          <Route path="/profile" element={<RequireAuth><Profile/></RequireAuth>} />
          <Route path="/documents/:id/edit" element={<RequireAuth><Editor/></RequireAuth>} />
        </Routes>
      </AnimatePresence>
    </Layout>
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
  const [submitting, setSubmitting] = useState(false)
  const toast = useToast()
  // Determine backend origin for social auth redirects
  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
  let serverOrigin = 'http://localhost:8000'
  try { serverOrigin = new URL(apiBase).origin } catch (_) {}
  const onSubmit = async (e) => {
    e.preventDefault(); setError('')
    try {
      setSubmitting(true)
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
        toast.success('Account created. Please log in to continue')
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
          toast.success('Account created and profile initialized')
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
      toast.success('Account created. Please log in to continue')
      navigate('/login')
    } catch (err) {
      const data = err?.response?.data
      const msg = typeof data === 'string' ? data : (data?.detail || JSON.stringify(data))
      setError(msg || 'Registration failed')
      toast.error(msg || 'Registration failed')
    } finally {
      setSubmitting(false)
    }
  }
  return (
    <div style={{ maxWidth: 620, margin: '40px auto' }}>
      <div className="card">
        <div className="card-body">
          <h2 style={{ marginTop: 0, marginBottom: 8 }}>Create your account</h2>
          <p style={{ color: 'var(--muted)', marginTop: 0 }}>Register to generate CVs and cover letters faster with AI.</p>
          <form onSubmit={onSubmit} className="stack" noValidate>
            <div>
              <label className="label" htmlFor="reg-email">Email</label>
              <input id="reg-email" className="input" type="email" value={email} onChange={e=>setEmail(e.target.value)} required autoComplete="email" disabled={submitting} />
            </div>
            <div className="grid-2">
              <div>
                <label className="label" htmlFor="reg-full">Full name</label>
                <input id="reg-full" className="input" type="text" value={fullName} onChange={e=>setFullName(e.target.value)} autoComplete="name" disabled={submitting} />
              </div>
              <div>
                <label className="label" htmlFor="reg-phone">Phone</label>
                <input id="reg-phone" className="input" type="tel" value={phone} onChange={e=>setPhone(e.target.value)} autoComplete="tel" disabled={submitting} />
              </div>
            </div>
            <div className="grid-2">
              <div>
                <label className="label" htmlFor="reg-pass1">Password</label>
                <input id="reg-pass1" className="input" type="password" value={password1} onChange={e=>setPassword1(e.target.value)} required autoComplete="new-password" disabled={submitting} />
              </div>
              <div>
                <label className="label" htmlFor="reg-pass2">Confirm Password</label>
                <input id="reg-pass2" className="input" type="password" value={password2} onChange={e=>setPassword2(e.target.value)} required autoComplete="new-password" disabled={submitting} />
              </div>
            </div>
            <div>
              <label className="label" htmlFor="reg-photo">Profile Photo (optional)</label>
              <input id="reg-photo" type="file" accept="image/*" onChange={e=>setPhotoFile(e.target.files?.[0] || null)} disabled={submitting} />
            </div>
            {error && (
                            <div role="alert" style={{ color: 'var(--text)', background: 'var(--error-bg)', border: '1px solid var(--error)', padding: '10px 12px', borderRadius: 10 }}>
                {error}
              </div>
            )}
            <button type="submit" className="btn btn-primary" disabled={submitting} aria-busy={submitting}>
              {submitting ? 'Creating account…' : 'Create account'}
            </button>
          </form>
          <div className="divider" style={{ marginTop: 16, marginBottom: 8 }}>or sign up with</div>
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
