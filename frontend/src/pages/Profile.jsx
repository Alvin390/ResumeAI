import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import { useToast } from '../services/toast.jsx'

export default function Profile() {
  const [profile, setProfile] = useState(null)
  const [docs, setDocs] = useState([])
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [photoPreview, setPhotoPreview] = useState('')
  const [pwSaving, setPwSaving] = useState(false)
  const navigate = useNavigate()
  const toast = useToast()

  const load = async () => {
    try {
      const [p, d] = await Promise.all([
        api.get('/profile/'),
        api.get('/cv/'),
      ])
      setProfile(p.data)
      setDocs(d.data)
      toast.info('Profile loaded')
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

  const onUpload = async (e) => {
    e.preventDefault()
    setError('')
    const file = e.target.file.files[0]
    if (!file) { setError('Please choose a file'); return }
    try {
      setUploading(true)
      const form = new FormData()
      form.append('file', file)
      await api.post('/cv/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      e.target.reset()
      await load()
      toast.success('CV uploaded')
    } catch (err) {
      const status = err?.response?.status
      if (status === 401) { navigate('/login'); return }
      setError(err?.response?.data?.detail || 'Upload failed')
      toast.error(err?.response?.data?.detail || 'Upload failed')
    } finally { setUploading(false) }
  }

  return (
    <div style={{ maxWidth: 720, margin: '32px auto' }}>
      <h2>Profile</h2>
      {error && <div style={{ color: 'red', marginBottom: 12 }}>{error}</div>}
      {profile ? (
        <div style={{ marginBottom: 24 }}>
          <div><b>Full name:</b> {profile.full_name || '—'}</div>
          <div><b>Phone:</b> {profile.phone || '—'}</div>
          {photoPreview ? (
            <div style={{ marginTop: 8 }}>
              <img src={photoPreview} alt="profile" style={{ width: 96, height: 96, objectFit: 'cover', borderRadius: 8 }} />
            </div>
          ) : null}
          <form style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center' }} onSubmit={async (e) => {
            e.preventDefault(); setError(''); setSaving(true)
            const fd = new FormData(e.currentTarget)
            try {
              await api.patch('/profile/', { full_name: fd.get('full_name') || '', phone: fd.get('phone') || '' })
              const p = await api.get('/profile/')
              setProfile(p.data)
              toast.success('Profile updated')
            } catch (err) {
              setError(err?.response?.data?.detail || 'Failed to save')
              toast.error(err?.response?.data?.detail || 'Failed to save')
            } finally { setSaving(false) }
          }}>
            <input name="full_name" placeholder="Full name" defaultValue={profile.full_name || ''} />
            <input name="phone" placeholder="Phone" defaultValue={profile.phone || ''} />
            <button type="submit" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
          </form>
          <form style={{ marginTop: 8 }} onSubmit={async (e) => {
            e.preventDefault(); setError('')
            const file = e.currentTarget.photo.files[0]
            if (!file) { setError('Choose a photo'); return }
            // Optimistic local preview
            try {
              if (photoPreview) URL.revokeObjectURL(photoPreview)
            } catch (_) {}
            const localUrl = URL.createObjectURL(file)
            setPhotoPreview(localUrl)
            const form = new FormData(); form.append('photo', file)
            try {
              // Let axios set multipart boundary automatically
              await api.post('/profile/photo/', form)
              const p = await api.get('/profile/')
              setProfile(p.data); e.currentTarget.reset()
              // refresh preview
              try {
                const img = await api.get('/profile/photo/', { responseType: 'blob' })
                const url = URL.createObjectURL(img.data)
                try { if (localUrl) URL.revokeObjectURL(localUrl) } catch (_) {}
                setPhotoPreview(url)
              } catch (_) {}
              toast.success('Photo uploaded')
            } catch (err) {
              // Revert preview on failure
              try { if (localUrl) URL.revokeObjectURL(localUrl) } catch (_) {}
              setError(err?.response?.data?.detail || 'Photo upload failed')
              toast.error(err?.response?.data?.detail || 'Photo upload failed')
            }
          }}>
            <input name="photo" type="file" accept="image/*" />
            <button type="submit">Upload Photo</button>
          </form>
          <div><b>Member since:</b> {new Date(profile.created_at).toLocaleString()}</div>
        </div>
      ) : (
        <div>Loading profile...</div>
      )}

      <section style={{ marginTop: 16 }}>
        <h3>Upload CV</h3>
        <form onSubmit={onUpload}>
          <input name="file" type="file" accept=".pdf,.doc,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword" />
          <button type="submit" disabled={uploading} style={{ marginLeft: 8 }}>{uploading ? 'Uploading...' : 'Upload'}</button>
        </form>
      </section>

      <section style={{ marginTop: 24 }}>
        <h3>My CV Versions</h3>
        {docs.length === 0 ? (
          <div>No CVs uploaded yet.</div>
        ) : (
          <ul>
            {docs.map(d => (
              <li key={d.id} style={{ marginBottom: 8 }}>
                v{d.version} — {d.file_name} — {new Date(d.created_at).toLocaleString()} —
                <button style={{ marginLeft: 8 }} onClick={() => download(d.id, d.file_name, null)}>Original</button>
                <button style={{ marginLeft: 8 }} onClick={() => download(d.id, d.file_name, 'pdf')}>PDF</button>
                <button style={{ marginLeft: 8 }} onClick={() => download(d.id, d.file_name, 'docx')}>DOCX</button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section style={{ marginTop: 24 }}>
        <h3>Change Password</h3>
        <form onSubmit={async (e) => {
          e.preventDefault(); setError(''); setPwSaving(true)
          const fd = new FormData(e.currentTarget)
          const old_password = fd.get('old_password') || ''
          const new_password1 = fd.get('new_password1') || ''
          const new_password2 = fd.get('new_password2') || ''
          try {
            await api.post('/auth/password/change/', { old_password, new_password1, new_password2 })
            e.currentTarget.reset()
            toast.success('Password changed')
          } catch (err) {
            const data = err?.response?.data
            const msg = typeof data === 'string' ? data : (data?.detail || JSON.stringify(data))
            setError(msg || 'Password change failed')
            toast.error(msg || 'Password change failed')
          } finally { setPwSaving(false) }
        }} style={{ display: 'grid', gap: 8, maxWidth: 360 }}>
          <input name="old_password" type="password" placeholder="Current password" autoComplete="current-password" required />
          <input name="new_password1" type="password" placeholder="New password" autoComplete="new-password" required />
          <input name="new_password2" type="password" placeholder="Confirm new password" autoComplete="new-password" required />
          <button type="submit" disabled={pwSaving}>{pwSaving ? 'Updating…' : 'Update Password'}</button>
        </form>
      </section>
    </div>
  )
}
