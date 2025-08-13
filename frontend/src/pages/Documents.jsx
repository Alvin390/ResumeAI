import React, { useEffect, useState } from 'react'
import api from '../services/api'
import { useToast } from '../services/toast.jsx'

export default function Documents() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [cvs, setCvs] = useState([])
  const [covers, setCovers] = useState([])
  const toast = useToast()

  const load = async () => {
    setLoading(true); setError('')
    try {
      const [cvRes, coverRes] = await Promise.all([
        api.get('/cv/?doc_type=cv'),
        api.get('/cv/?doc_type=cover'),
      ])
      setCvs(cvRes.data || [])
      setCovers(coverRes.data || [])
      toast.info('Documents loaded')
    } catch (e) {
      setError('Failed to load documents')
      toast.error('Failed to load documents')
    } finally {
      setLoading(false)
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
    // strip known ext
    return name.replace(/\.(pdf|docx|txt)$/i, '') + `.${ext}`
  }

  return (
    <div style={{ maxWidth: 900, margin: '32px auto' }}>
      <h2>My Documents</h2>
      {loading ? <div>Loading…</div> : null}
      {error && <div style={{ color: 'red', marginBottom: 12 }}>{error}</div>}

      <section style={{ marginTop: 16 }}>
        <h3>CVs</h3>
        {cvs.length === 0 ? (
          <div>No CVs yet.</div>
        ) : (
          <ul>
            {cvs.map(d => (
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
        <h3>Cover Letters</h3>
        {covers.length === 0 ? (
          <div>No cover letters yet.</div>
        ) : (
          <ul>
            {covers.map(d => (
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
    </div>
  )
}
