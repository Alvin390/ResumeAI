import React, { useEffect, useState } from 'react'
import api from '../services/api'
import { useToast } from '../services/toast.jsx'
import { DocumentsSkeleton } from '../components/Skeleton.jsx'

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
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 8 }}>My Documents</h2>
      {loading && <DocumentsSkeleton />}
      {error && (
        <div className="card" style={{ marginBottom: 16, borderColor: 'var(--error)' }}>
          <div className="card-body" style={{ color: 'var(--text)' }}>{error}</div>
        </div>
      )}

      <section style={{ marginTop: 8 }}>
        <h3 style={{ marginTop: 0 }}>CVs</h3>
        {cvs.length === 0 ? (
          <div className="card"><div className="card-body">No CVs yet.</div></div>
        ) : (
          <div className="stack">
            {cvs.map(d => (
              <div key={d.id} className="card">
                <div className="card-body" style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 240 }}>
                    <div style={{ fontWeight: 600 }}>v{d.version} — {d.file_name}</div>
                    <div style={{ color: 'var(--muted)', fontSize: 13 }}>{new Date(d.created_at).toLocaleString()}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn" onClick={() => download(d.id, d.file_name, null)}>Original</button>
                    <button className="btn" onClick={() => download(d.id, d.file_name, 'pdf')}>PDF</button>
                    <button className="btn" onClick={() => download(d.id, d.file_name, 'docx')}>DOCX</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section style={{ marginTop: 24 }}>
        <h3 style={{ marginTop: 0 }}>Cover Letters</h3>
        {covers.length === 0 ? (
          <div className="card"><div className="card-body">No cover letters yet.</div></div>
        ) : (
          <div className="stack">
            {covers.map(d => (
              <div key={d.id} className="card">
                <div className="card-body" style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 240 }}>
                    <div style={{ fontWeight: 600 }}>v{d.version} — {d.file_name}</div>
                    <div style={{ color: 'var(--muted)', fontSize: 13 }}>{new Date(d.created_at).toLocaleString()}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn" onClick={() => download(d.id, d.file_name, null)}>Original</button>
                    <button className="btn" onClick={() => download(d.id, d.file_name, 'pdf')}>PDF</button>
                    <button className="btn" onClick={() => download(d.id, d.file_name, 'docx')}>DOCX</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
