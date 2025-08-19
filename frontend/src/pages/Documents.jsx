import React, { useEffect, useState } from 'react'
import api from '../services/api'
import { useToast } from '../services/toast.jsx'
import { DocumentsSkeleton } from '../components/Skeleton.jsx'
import { motion } from 'framer-motion'
import { FileText, Briefcase, Download, Edit, Calendar, User } from 'lucide-react'

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
      // toast.info('Documents loaded') // Remove noisy toast
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
          <motion.div 
            className="card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="card-body" style={{ textAlign: 'center', padding: 'var(--space-10)' }}>
              <FileText size={48} style={{ color: 'var(--muted)', marginBottom: 16 }} />
              <div style={{ color: 'var(--muted)', fontSize: 'var(--text-base)' }}>No CVs yet.</div>
              <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)', marginTop: 8 }}>
                Upload your first CV from the Profile page
              </div>
            </div>
          </motion.div>
        ) : (
          <div className="stack">
            {cvs.map((d, index) => (
              <motion.div 
                key={d.id} 
                className="card"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                whileHover={{ scale: 1.01 }}
              >
                <div className="card-body" style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
                  {/* File Type Icon */}
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

                  {/* Document Info */}
                  <div style={{ flex: 1, minWidth: 240 }}>
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
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <User size={14} />
                        CV Document
                      </div>
                    </div>
                  </div>

                  {/* Action Buttons */}
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
      </section>

      <section style={{ marginTop: 24 }}>
        <h3 style={{ marginTop: 0 }}>Cover Letters</h3>
        {covers.length === 0 ? (
          <motion.div 
            className="card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="card-body" style={{ textAlign: 'center', padding: 'var(--space-10)' }}>
              <Briefcase size={48} style={{ color: 'var(--muted)', marginBottom: 16 }} />
              <div style={{ color: 'var(--muted)', fontSize: 'var(--text-base)' }}>No cover letters yet.</div>
              <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)', marginTop: 8 }}>
                Generate your first cover letter from the Generate page
              </div>
            </div>
          </motion.div>
        ) : (
          <div className="stack">
            {covers.map((d, index) => (
              <motion.div 
                key={d.id} 
                className="card"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                whileHover={{ scale: 1.01 }}
              >
                <div className="card-body" style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
                  {/* File Type Icon */}
                  <div style={{
                    width: 48,
                    height: 48,
                    borderRadius: 12,
                    background: 'linear-gradient(135deg, var(--success), #059669)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    flexShrink: 0
                  }}>
                    <Briefcase size={24} />
                  </div>

                  {/* Document Info */}
                  <div style={{ flex: 1, minWidth: 240 }}>
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
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Briefcase size={14} />
                        Cover Letter
                      </div>
                    </div>
                  </div>

                  {/* Action Buttons */}
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
                      className="btn btn-success"
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
      </section>
    </div>
  )
}
