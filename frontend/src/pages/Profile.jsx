import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import { useToast } from '../services/toast.jsx'
import { ProfileSkeleton } from '../components/Skeleton.jsx'
import FileUpload from '../components/FileUpload.jsx'
import { motion, AnimatePresence } from 'framer-motion'
import { Camera, User, Upload, X, Mail, Phone, Calendar, Shield, FileText, Download, Edit3, Settings } from 'lucide-react'

export default function Profile() {
  const [profile, setProfile] = useState(null)
  const [docs, setDocs] = useState([])
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [photoPreview, setPhotoPreview] = useState('')
  const [pwSaving, setPwSaving] = useState(false)
  const [photoRemoving, setPhotoRemoving] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null)
  const [optimisticProfile, setOptimisticProfile] = useState(null)
  const navigate = useNavigate()
  const toast = useToast()

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } },
  }

  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: { y: 0, opacity: 1, transition: { duration: 0.5, ease: 'easeOut' } },
  }

  const load = async () => {
    try {
      const [p, d] = await Promise.all([
        api.get('/profile/'),
        api.get('/cv/'),
      ])
      setProfile(p.data)
      setDocs(d.data)
      // toast.info('Profile loaded') // Remove noisy toast
      // Try to fetch photo with auth if available
      try {
        const img = await api.get('/profile/photo/', { responseType: 'blob' })
        const url = URL.createObjectURL(img.data)
        setPhotoPreview(url)
      } catch (_) {}
    } catch (e) {
      const status = e?.response?.status
      if (status === 401) {
        navigate('/login')
        return
      }
      setError('Failed to load profile or documents')
      toast.error('Failed to load profile or documents')
    }
  }

  useEffect(() => { load() }, [])

  const download = async (docId, filename, fmt) => {
    try {
      const qs = fmt ? `?fmt=${encodeURIComponent(fmt)}` : ''
      const res = await api.get(`/documents/${docId}/download/${qs}`, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      const name = fmt ? withExt(filename, fmt) : filename
      link.setAttribute('download', name)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      toast.success('Download started')
    } catch (e) {
      toast.error('Download failed')
    }
  }

  const withExt = (name, ext) => {
    if (!name) return `document.${ext}`
    const lower = name.toLowerCase()
    if ((ext === 'pdf' && lower.endsWith('.pdf')) || (ext === 'docx' && lower.endsWith('.docx'))) return name
    return name.replace(/\.(pdf|docx|txt)$/i, '') + `.${ext}`
  }

  const onUpload = async (file) => {
    setError('')
    try {
      setUploading(true)
      const form = new FormData()
      form.append('file', file)
      await api.post('/cv/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      await load()
      toast.success('CV uploaded successfully')
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) { navigate('/login'); return }
      setError(err?.response?.data?.detail || 'Upload failed')
      toast.error(err?.response?.data?.detail || 'Upload failed')
    } finally { setUploading(false) }
  }

  return (
    <motion.div
      style={{ maxWidth: 1200, margin: '32px auto', padding: '0 16px' }}
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header */}
      <motion.div 
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          marginBottom: 32
        }}
        variants={itemVariants}
      >
        <div style={{
          width: 48,
          height: 48,
          borderRadius: 12,
          background: 'linear-gradient(135deg, var(--primary), var(--primary-700))',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white'
        }}>
          <User size={24} />
        </div>
        <div>
          <h1 style={{ 
            margin: 0, 
            fontSize: 'var(--text-3xl)', 
            fontWeight: 700,
            background: 'linear-gradient(135deg, var(--primary), var(--primary-700))',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text'
          }}>
            My Profile
          </h1>
          <p style={{ margin: 0, color: 'var(--muted)', fontSize: 'var(--text-base)' }}>
            Manage your account settings and preferences
          </p>
        </div>
      </motion.div>

      {error && (
        <motion.div 
          className="card"
          style={{ marginBottom: 24, borderColor: 'var(--error)', background: 'var(--error-bg)' }}
          variants={itemVariants}
        >
          <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <X size={20} style={{ color: 'var(--error)' }} />
            <span style={{ color: 'var(--error)' }}>{error}</span>
          </div>
        </motion.div>
      )}

      {profile ? (
        <div style={{ display: 'grid', gap: 24, gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))' }}>
          {/* Profile Information Card */}
          <motion.div 
            className="card"
            style={{ gridColumn: 'span 2' }}
            variants={itemVariants}
          >
            <div className="card-body" style={{ padding: 32 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 32 }}>
                {/* Enhanced Photo Display */}
                <div style={{ position: 'relative' }}>
                  <motion.div
                    style={{
                      width: 140,
                      height: 140,
                      borderRadius: '50%',
                      overflow: 'hidden',
                      background: photoPreview ? 'transparent' : 'var(--bg-hover)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      border: '4px solid var(--border)',
                      position: 'relative',
                      boxShadow: '0 8px 32px rgba(0,0,0,0.12)'
                    }}
                    whileHover={{ scale: 1.05 }}
                    transition={{ type: 'spring', stiffness: 300 }}
                  >
                    {photoPreview ? (
                      <img 
                        src={photoPreview} 
                        alt="Profile" 
                        style={{ 
                          width: '100%', 
                          height: '100%', 
                          objectFit: 'cover' 
                        }} 
                      />
                    ) : (
                      <User size={56} style={{ color: 'var(--muted)' }} />
                    )}
                
                    {/* Photo Upload Overlay */}
                    <motion.label
                      htmlFor="photo-upload"
                      style={{
                        position: 'absolute',
                        bottom: -4,
                        right: -4,
                        width: 40,
                        height: 40,
                        borderRadius: '50%',
                        background: 'linear-gradient(135deg, var(--primary), var(--primary-700))',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        border: '4px solid var(--bg)',
                        color: 'white',
                        boxShadow: '0 4px 16px rgba(0,0,0,0.2)'
                      }}
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.95 }}
                    >
                      <Camera size={18} />
                    </motion.label>
                
                <input
                  id="photo-upload"
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  onChange={async (e) => {
                    const file = e.target.files[0]
                    if (!file) return
                    
                    setError('')
                    // Optimistic local preview
                    try {
                      if (photoPreview) URL.revokeObjectURL(photoPreview)
                    } catch (_) {}
                    const localUrl = URL.createObjectURL(file)
                    setPhotoPreview(localUrl)
                    
                    const form = new FormData()
                    form.append('photo', file)
                    try {
                      await api.post('/profile/photo/', form)
                      const p = await api.get('/profile/')
                      setProfile(p.data)
                      
                      // Refresh preview
                      try {
                        const img = await api.get('/profile/photo/', { responseType: 'blob' })
                        const url = URL.createObjectURL(img.data)
                        try { if (localUrl) URL.revokeObjectURL(localUrl) } catch (_) {}
                        setPhotoPreview(url)
                      } catch (_) {}
                      toast.success('Photo uploaded successfully')
                    } catch (err) {
                      setError(err?.response?.data?.detail || 'Photo upload failed')
                      toast.error(err?.response?.data?.detail || 'Photo upload failed')
                    }
                    e.target.value = '' // Reset input
                  }}
                />
              </motion.div>
              
                  {/* Remove Photo Button */}
                  <AnimatePresence>
                    {photoPreview && (
                      <motion.button
                        onClick={async () => {
                          setPhotoRemoving(true)
                          try {
                            // Optimistic update
                            setPhotoPreview('')
                            await api.delete('/profile/photo/')
                            toast.success('Photo removed successfully')
                          } catch (err) {
                            // Revert optimistic update on error
                            try {
                              const img = await api.get('/profile/photo/', { responseType: 'blob' })
                              const url = URL.createObjectURL(img.data)
                              setPhotoPreview(url)
                            } catch (_) {}
                            toast.error('Failed to remove photo')
                          } finally {
                            setPhotoRemoving(false)
                          }
                        }}
                        className="btn btn-sm"
                        disabled={photoRemoving}
                        style={{
                          position: 'absolute',
                          top: -8,
                          right: -8,
                          width: 24,
                          height: 24,
                          borderRadius: '50%',
                          background: photoRemoving ? 'var(--muted)' : 'var(--danger)',
                          color: 'white',
                          border: 'none',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: 12,
                          cursor: photoRemoving ? 'not-allowed' : 'pointer',
                          opacity: photoRemoving ? 0.6 : 1
                        }}
                        whileHover={!photoRemoving ? { scale: 1.1 } : {}}
                        whileTap={!photoRemoving ? { scale: 0.9 } : {}}
                      >
                        {photoRemoving ? (
                          <motion.div
                            animate={{ rotate: 360 }}
                            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                          >
                            <Settings size={10} />
                          </motion.div>
                        ) : (
                          <X size={12} />
                        )}
                      </motion.button>
                    )}
                  </AnimatePresence>
                </div>
            
                {/* Profile Information */}
                <div style={{ flex: 1 }}>
                  <div style={{ marginBottom: 24 }}>
                    <h3 style={{ 
                      margin: '0 0 16px 0', 
                      fontSize: 'var(--text-2xl)', 
                      fontWeight: 700,
                      color: 'var(--text)'
                    }}>
                      {profile.full_name || 'Your Name'}
                    </h3>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{
                          width: 32,
                          height: 32,
                          borderRadius: 8,
                          background: 'var(--bg-hover)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}>
                          <Mail size={16} style={{ color: 'var(--primary)' }} />
                        </div>
                        <div>
                          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)' }}>Email</div>
                          <div style={{ fontSize: 'var(--text-base)', fontWeight: 500 }}>
                            {(optimisticProfile || profile)?.user?.email || 'Not provided'}
                          </div>
                        </div>
                      </div>
                      
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{
                          width: 32,
                          height: 32,
                          borderRadius: 8,
                          background: 'var(--bg-hover)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}>
                          <Phone size={16} style={{ color: 'var(--primary)' }} />
                        </div>
                        <div>
                          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)' }}>Phone</div>
                          <div style={{ fontSize: 'var(--text-base)', fontWeight: 500 }}>
                            {(optimisticProfile || profile)?.phone || 'Not provided'}
                          </div>
                        </div>
                      </div>
                      
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{
                          width: 32,
                          height: 32,
                          borderRadius: 8,
                          background: 'var(--bg-hover)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}>
                          <Calendar size={16} style={{ color: 'var(--muted)' }} />
                        </div>
                        <div>
                          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)' }}>Member since</div>
                          <div style={{ fontSize: 'var(--text-base)', fontWeight: 500 }}>
                            {new Date(profile.created_at).toLocaleDateString('en-US', { 
                              year: 'numeric', 
                              month: 'long', 
                              day: 'numeric' 
                            })}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                    <motion.label
                      htmlFor="photo-upload"
                      className="btn btn-primary"
                      style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                    >
                      <Upload size={16} />
                      {photoPreview ? 'Change Photo' : 'Upload Photo'}
                    </motion.label>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Edit Profile Card */}
          <motion.div className="card" variants={itemVariants}>
            <div className="card-body" style={{ padding: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                <div style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  background: 'linear-gradient(135deg, var(--info), #2563eb)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white'
                }}>
                  <Edit3 size={20} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: 'var(--text-xl)', fontWeight: 600 }}>
                    Edit Profile
                  </h3>
                  <p style={{ margin: 0, color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>
                    Update your personal information
                  </p>
                </div>
              </div>
              
              <form onSubmit={async (e) => {
                e.preventDefault(); setError(''); setSaving(true)
                const fd = new FormData(e.currentTarget)
                
                // Optimistic update
                const newData = {
                  full_name: fd.get('full_name') || '',
                  phone: fd.get('phone') || '',
                  user: {
                    ...profile.user,
                    email: fd.get('email') || '',
                    username: fd.get('username') || ''
                  }
                }
                setOptimisticProfile({ ...profile, ...newData })
                
                try {
                  // Update profile information
                  await api.patch('/profile/', { 
                    full_name: newData.full_name, 
                    phone: newData.phone
                  })
                  
                  // Update user information (email, username) if changed
                  const email = newData.user.email
                  const username = newData.user.username
                  if (email !== profile.user?.email || username !== profile.user?.username) {
                    await api.patch('/auth/user/', { 
                      email: email,
                      username: username
                    })
                  }
                  
                  const p = await api.get('/profile/')
                  setProfile(p.data)
                  setOptimisticProfile(null)
                  toast.success('Profile updated successfully')
                } catch (err) {
                  // Revert optimistic update on error
                  setOptimisticProfile(null)
                  const errorMsg = err?.response?.data?.detail || err?.response?.data?.email?.[0] || err?.response?.data?.username?.[0] || 'Failed to save profile'
                  setError(errorMsg)
                  toast.error(errorMsg)
                } finally { setSaving(false) }
              }}>
                <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))' }}>
                  <div>
                    <label className="label" htmlFor="full_name">Full Name *</label>
                    <input 
                      id="full_name"
                      className="input" 
                      name="full_name" 
                      placeholder="Enter your full name" 
                      defaultValue={(optimisticProfile || profile)?.full_name || ''} 
                      required
                    />
                  </div>
                  <div>
                    <label className="label" htmlFor="username">Username *</label>
                    <input 
                      id="username"
                      className="input" 
                      name="username" 
                      placeholder="Enter your username" 
                      defaultValue={(optimisticProfile || profile)?.user?.username || ''} 
                      required
                    />
                  </div>
                  <div>
                    <label className="label" htmlFor="email">Email Address *</label>
                    <input 
                      id="email"
                      className="input" 
                      name="email" 
                      type="email"
                      placeholder="Enter your email address" 
                      defaultValue={(optimisticProfile || profile)?.user?.email || ''} 
                      required
                    />
                  </div>
                  <div>
                    <label className="label" htmlFor="phone">Phone Number</label>
                    <input 
                      id="phone"
                      className="input" 
                      name="phone" 
                      type="tel"
                      placeholder="Enter your phone number" 
                      defaultValue={(optimisticProfile || profile)?.phone || ''} 
                    />
                  </div>
                  <motion.button 
                    className="btn btn-primary" 
                    type="submit" 
                    disabled={saving} 
                    style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: 8, 
                      justifyContent: 'center',
                      gridColumn: '1 / -1',
                      marginTop: 8
                    }}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    {saving ? (
                      <>
                        <motion.div
                          animate={{ rotate: 360 }}
                          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                        >
                          <Settings size={16} />
                        </motion.div>
                        Saving...
                      </>
                    ) : (
                      <>
                        <Edit3 size={16} />
                        Update Profile
                      </>
                    )}
                  </motion.button>
                </div>
              </form>
            </div>
          </motion.div>

          {/* Security Card */}
          <motion.div className="card" variants={itemVariants}>
            <div className="card-body" style={{ padding: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                <div style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  background: 'linear-gradient(135deg, var(--warning), #d97706)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white'
                }}>
                  <Shield size={20} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: 'var(--text-xl)', fontWeight: 600 }}>
                    Security
                  </h3>
                  <p style={{ margin: 0, color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>
                    Update your account password
                  </p>
                </div>
              </div>
              
              <form onSubmit={async (e) => {
                e.preventDefault(); setError(''); setPwSaving(true)
                const fd = new FormData(e.currentTarget)
                const old_password = fd.get('old_password') || ''
                const new_password1 = fd.get('new_password1') || ''
                const new_password2 = fd.get('new_password2') || ''
                try {
                  await api.post('/auth/password/change/', { old_password, new_password1, new_password2 })
                  e.currentTarget.reset()
                  toast.success('Password changed successfully')
                } catch (err) {
                  const data = err?.response?.data
                  const msg = typeof data === 'string' ? data : (data?.detail || JSON.stringify(data))
                  setError(msg || 'Password change failed')
                  toast.error(msg || 'Password change failed')
                } finally { setPwSaving(false) }
              }}>
                <div style={{ display: 'grid', gap: 16 }}>
                  <div>
                    <label className="label" htmlFor="old_password">Current Password</label>
                    <input 
                      id="old_password"
                      className="input" 
                      name="old_password" 
                      type="password" 
                      placeholder="Enter current password" 
                      autoComplete="current-password" 
                      required 
                    />
                  </div>
                  <div>
                    <label className="label" htmlFor="new_password1">New Password</label>
                    <input 
                      id="new_password1"
                      className="input" 
                      name="new_password1" 
                      type="password" 
                      placeholder="Enter new password" 
                      autoComplete="new-password" 
                      required 
                    />
                  </div>
                  <div>
                    <label className="label" htmlFor="new_password2">Confirm New Password</label>
                    <input 
                      id="new_password2"
                      className="input" 
                      name="new_password2" 
                      type="password" 
                      placeholder="Confirm new password" 
                      autoComplete="new-password" 
                      required 
                    />
                  </div>
                  <motion.button 
                    className="btn btn-warning" 
                    type="submit" 
                    disabled={pwSaving}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center' }}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    {pwSaving ? (
                      <>
                        <motion.div
                          animate={{ rotate: 360 }}
                          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                        >
                          <Settings size={16} />
                        </motion.div>
                        Updating...
                      </>
                    ) : (
                      <>
                        <Shield size={16} />
                        Update Password
                      </>
                    )}
                  </motion.button>
                </div>
              </form>
            </div>
          </motion.div>

          {/* CV Upload Card */}
          <motion.div className="card" variants={itemVariants}>
            <div className="card-body" style={{ padding: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                <div style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  background: 'linear-gradient(135deg, var(--success), #059669)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white'
                }}>
                  <Upload size={20} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: 'var(--text-xl)', fontWeight: 600 }}>
                    Upload CV
                  </h3>
                  <p style={{ margin: 0, color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>
                    Upload your resume for AI processing
                  </p>
                </div>
              </div>
              
              <FileUpload
                label=""
                onFileSelect={onUpload}
                uploading={uploading}
                accept=".pdf,.doc,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword"
              />
            </div>
          </motion.div>

          {/* CV Versions Card */}
          <motion.div className="card" style={{ gridColumn: 'span 2' }} variants={itemVariants}>
            <div className="card-body" style={{ padding: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                <div style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  background: 'linear-gradient(135deg, var(--primary), var(--primary-700))',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white'
                }}>
                  <FileText size={20} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: 'var(--text-xl)', fontWeight: 600 }}>
                    My CV Versions
                  </h3>
                  <p style={{ margin: 0, color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>
                    Manage and download your uploaded CVs
                  </p>
                </div>
              </div>
              
              {docs.length === 0 ? (
                <motion.div 
                  style={{ 
                    textAlign: 'center', 
                    padding: 'var(--space-10)',
                    background: 'var(--bg-hover)',
                    borderRadius: 12,
                    border: '2px dashed var(--border)'
                  }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  <FileText size={48} style={{ color: 'var(--muted)', marginBottom: 16 }} />
                  <div style={{ fontSize: 'var(--text-base)', fontWeight: 500, marginBottom: 8 }}>
                    No CVs uploaded yet
                  </div>
                  <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>
                    Upload your first CV to get started with AI-powered resume generation
                  </div>
                </motion.div>
              ) : (
                <div style={{ display: 'grid', gap: 12 }}>
                  {docs.map((d, index) => (
                    <motion.div 
                      key={d.id} 
                      className="card"
                      style={{
                        padding: 16,
                        marginBottom: 12,
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border)',
                        borderRadius: 12,
                        cursor: 'pointer'
                      }}
                      whileHover={{ scale: 1.02, y: -2, boxShadow: '0 8px 25px rgba(0,0,0,0.1)' }}
                      whileTap={{ scale: 0.98 }}
                      transition={{ duration: 0.2, ease: 'easeOut' }}
                    >
                      <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 16, padding: 16 }}>
                        <div style={{
                          width: 48,
                          height: 48,
                          borderRadius: 12,
                          background: 'linear-gradient(135deg, var(--primary), var(--primary-700))',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'white',
                          flexShrink: 0
                        }}>
                          <FileText size={24} />
                        </div>
                        
                        <div style={{ flex: 1 }}>
                          <div style={{ 
                            fontWeight: 600, 
                            fontSize: 'var(--text-base)',
                            marginBottom: 4,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8
                          }}>
                            v{d.version} — {d.file_name}
                            <span className="status-badge status-completed">
                              <span>✓</span>
                              Ready
                            </span>
                          </div>
                          <div style={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            gap: 16, 
                            color: 'var(--muted)', 
                            fontSize: 'var(--text-sm)' 
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                              <Calendar size={14} />
                              {new Date(d.created_at).toLocaleDateString()}
                            </div>
                          </div>
                        </div>
                        
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <motion.button 
                            className="btn"
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            onClick={() => download(d.id, d.file_name, null)}
                            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                          >
                            <Download size={14} />
                            Original
                          </motion.button>
                          <motion.button 
                            className="btn btn-primary"
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            onClick={() => download(d.id, d.file_name, 'pdf')}
                            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                          >
                            <Download size={14} />
                            PDF
                          </motion.button>
                          <motion.button 
                            className="btn"
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            onClick={() => download(d.id, d.file_name, 'docx')}
                            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                          >
                            <Download size={14} />
                            DOCX
                          </motion.button>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </div>
      ) : (
        <ProfileSkeleton />
      )}
    </motion.div>
  )
}
