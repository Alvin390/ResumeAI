import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import { useToast } from '../services/toast.jsx'
import { GenerateSkeleton } from '../components/Skeleton.jsx'
import TemplateSelector from '../components/TemplateSelector.jsx'
import { motion, AnimatePresence } from 'framer-motion'
import { Loader2, CheckCircle, AlertCircle, Clock, Zap, FileText, Briefcase } from 'lucide-react'

export default function Generate() {
  const [jd, setJd] = useState('')
  const [cvList, setCvList] = useState([])
  const [selectedCv, setSelectedCv] = useState('')
  const [template, setTemplate] = useState('classic')
  const [jobId, setJobId] = useState(null)
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const [result, setResult] = useState({ cover_id: null, cv_id: null })
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const toast = useToast()
  const templates = useMemo(() => ([
    { id: 'classic', title: 'Classic', desc: 'Balanced, clean typographic layout' },
    { id: 'modern', title: 'Modern', desc: 'Bold headings with accent color' },
    { id: 'compact', title: 'Compact', desc: 'Space-efficient, concise structure' },
  ]), [])

  useEffect(() => {
    // Explicit auth guard: if no token present, go to login
    const access = localStorage.getItem('access')
    const key = localStorage.getItem('token_key')
    if (!access && !key) {
      console.warn('[Generate] No auth token found, redirecting to /login')
      navigate('/login')
      return
    }
    // Load user's CVs for selection
    api.get('/cv/')
      .then(r => {
        setCvList(r.data)
        setLoading(false)
      })
      .catch((e) => {
        setLoading(false)
        if (e?.response?.status === 401) {
          console.warn('[Generate] GET /cv/ unauthorized → redirect to /login')
          navigate('/login')
        } else {
          toast.error('Failed to load CV list')
        }
      })
    // Restore last result if present
    try {
      const raw = sessionStorage.getItem('gen:last')
      if (raw) {
        const parsed = JSON.parse(raw)
        if (parsed?.jobId) setJobId(parsed.jobId)
        if (parsed?.result) setResult(parsed.result)
        if (parsed?.status) setStatus(parsed.status)
      }
    } catch (_) {}
  }, [])

  useEffect(() => {
    if (!jobId) return
    setStatus('queued')
    let alive = true
    const interval = setInterval(async () => {
      try {
        const { data } = await api.get(`/generations/${jobId}/status/`)
        setStatus(data.status)
        // console.log('[Generate] polled status', data)
        if (data.result_cover_letter || data.result_generated_cv || data.status === 'error') {
          clearInterval(interval)
          if (!alive) return
          setResult({
            cover_id: data.result_cover_letter || null,
            cv_id: data.result_generated_cv || null,
          })
          try {
            sessionStorage.setItem('gen:last', JSON.stringify({ jobId, status: data.status, result: {
              cover_id: data.result_cover_letter || null,
              cv_id: data.result_generated_cv || null,
            }}))
          } catch (_) {}
          if (data.status === 'error') {
            toast.error('Generation failed, check logs')
          } else {
            toast.success('Generation completed')
          }
        }
      } catch (e) {
        // stop polling if unauthorized
        if (e?.response?.status === 401) {
          console.warn('[Generate] Poll unauthorized → redirect to /login')
          clearInterval(interval)
          navigate('/login')
        } else {
          console.warn('[Generate] Poll error', e)
        }
      }
    }, 1500)
    return () => { alive = false; clearInterval(interval) }
  }, [jobId, navigate])

  const onStart = async (e) => {
    e.preventDefault()
    setError('')
    setResult({ cover_id: null, cv_id: null })
    try {
      if (!jd.trim()) { setError('Job description is required'); console.warn('[Generate] Empty JD blocked'); return }
      console.log('[Generate] Creating job description...')
      const { data: jdResp } = await api.post('/jobs/', { text: jd })
      console.log('[Generate] JD created id=', jdResp.id)
      const payload = {
        job_description_id: jdResp.id,
        job_type: 'both',
        template,
      }
      if (selectedCv) payload.source_cv_id = Number(selectedCv)
      console.log('[Generate] Starting generation with payload', payload)
      const { data: gen } = await api.post('/generate/', payload)
      setJobId(gen.id)
      setStatus(gen.status)
      console.log('[Generate] Generation job created id=', gen.id, 'status=', gen.status)
      try { sessionStorage.setItem('gen:last', JSON.stringify({ jobId: gen.id, status: gen.status, result: { cover_id: null, cv_id: null } })) } catch (_) {}
      toast.info('Generation started')
    } catch (err) {
      if (err?.response?.status === 401) {
        console.warn('[Generate] Unauthorized during start → redirect to /login')
        navigate('/login');
        return
      }
      const msg = err?.response?.data?.detail || err?.message || 'Failed to start generation'
      setError(msg)
      console.error('[Generate] Start error:', msg)
      toast.error(msg)
    }
  }

  const coverDownloadUrl = useMemo(() => result.cover_id ? `/documents/${result.cover_id}/download/` : '' , [result.cover_id])
  const cvDownloadUrl = useMemo(() => result.cv_id ? `/documents/${result.cv_id}/download/` : '', [result.cv_id])

  if (loading) {
    return <GenerateSkeleton />
  }

  return (
    <div style={{ margin: '24px auto', maxWidth: 1080 }}>
      <h2>Generate tailored CV & Cover Letter</h2>
      <div className="grid-2" style={{ marginTop: 12 }}>
        <div>
          <div className="card">
            <div className="card-body">
              <form onSubmit={onStart} className="stack" noValidate>
                <div>
                  <label className="label" htmlFor="jd">Job Description</label>
                  <textarea id="jd" className="textarea" value={jd} onChange={e=>setJd(e.target.value)} rows={12} placeholder="Paste the job description here" />
                </div>
                {error && (
                  <div role="alert" style={{ color: 'var(--text)', background: 'rgba(239,68,68,.15)', border: '1px solid var(--error)', padding: '10px 12px', borderRadius: 10 }}>
                    {error}
                  </div>
                )}
                <button type="submit" className="btn btn-primary" disabled={!jd.trim() || status === 'queued' || status === 'running'} aria-busy={status === 'queued' || status === 'running'}>
                  {status === 'running' ? 'Generating…' : status === 'queued' ? 'Queued…' : 'Generate'}
                </button>
              </form>
            </div>
          </div>
        </div>
        <div className="stack">
          <div className="card">
            <div className="card-body">
              <TemplateSelector 
                selectedTemplate={template} 
                onTemplateSelect={setTemplate} 
              />
              <div>
                <label className="label" htmlFor="use-cv">Use CV</label>
                <select id="use-cv" className="select" value={selectedCv} onChange={e=>setSelectedCv(e.target.value)}>
                  <option value=''>Use latest profile CV</option>
                  {cvList.map(cv => (
                    <option key={cv.id} value={cv.id}>v{cv.version} — {cv.file_name}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
          <AnimatePresence>
            {jobId && (
              <motion.div 
                className="card"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
              >
                <div className="card-body">
                  {/* Status Header */}
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: 12, 
                    marginBottom: 16,
                    paddingBottom: 16,
                    borderBottom: '1px solid var(--border)'
                  }}>
                    <div style={{
                      width: 40,
                      height: 40,
                      borderRadius: '50%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: status === 'completed' ? 'var(--success)' : 
                                 status === 'failed' ? 'var(--error)' : 
                                 'var(--info)',
                      color: 'white'
                    }}>
                      {status === 'running' && <Loader2 size={20} className="animate-spin" />}
                      {status === 'completed' && <CheckCircle size={20} />}
                      {status === 'failed' && <AlertCircle size={20} />}
                      {status === 'pending' && <Clock size={20} />}
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 'var(--text-base)' }}>
                        Generation {status === 'running' ? 'in Progress' : 
                                  status === 'completed' ? 'Complete' :
                                  status === 'failed' ? 'Failed' : 'Pending'}
                      </div>
                      <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>
                        Job ID: {jobId}
                      </div>
                    </div>
                    <div style={{ marginLeft: 'auto' }}>
                      <span className={`status-badge status-${
                        status === 'completed' ? 'completed' :
                        status === 'failed' ? 'error' :
                        status === 'running' ? 'running' : 'pending'
                      }`}>
                        {status === 'running' && <Loader2 size={12} className="animate-spin" />}
                        {status.charAt(0).toUpperCase() + status.slice(1)}
                      </span>
                    </div>
                  </div>

                  {/* Progress Indicator */}
                  {status === 'running' && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      style={{ marginBottom: 16 }}
                    >
                      <div style={{ 
                        height: 4, 
                        background: 'var(--bg-hover)', 
                        borderRadius: 2, 
                        overflow: 'hidden' 
                      }}>
                        <motion.div
                          style={{
                            height: '100%',
                            background: 'linear-gradient(90deg, var(--info), var(--primary))',
                            borderRadius: 2
                          }}
                          initial={{ width: '0%' }}
                          animate={{ width: '100%' }}
                          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                        />
                      </div>
                      <div style={{ 
                        fontSize: 'var(--text-sm)', 
                        color: 'var(--muted)', 
                        marginTop: 8,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8
                      }}>
                        <Zap size={14} />
                        AI is crafting your documents...
                      </div>
                    </motion.div>
                  )}

                  {/* Results */}
                  {(result.cover_id || result.cv_id) && (
                    <motion.div 
                      className="stack" 
                      style={{ marginTop: 8 }}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.2 }}
                    >
                      {result.cover_id && (
                        <div style={{
                          padding: 16,
                          background: 'var(--bg-elev)',
                          borderRadius: 12,
                          border: '1px solid var(--border)'
                        }}>
                          <div style={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            gap: 8, 
                            marginBottom: 12 
                          }}>
                            <Briefcase size={18} style={{ color: 'var(--success)' }} />
                            <span style={{ fontWeight: 600 }}>Cover Letter Generated</span>
                          </div>
                          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            <motion.button 
                              className="btn btn-primary"
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              onClick={() => navigate(`/documents/${result.cover_id}/edit`)}
                            >
                              <FileText size={14} />
                              Edit
                            </motion.button>
                            <motion.button 
                              className="btn"
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              onClick={async () => {
                                try {
                                  const res = await api.get(`/documents/${result.cover_id}/download/`, { responseType: 'blob' })
                                  const url = window.URL.createObjectURL(new Blob([res.data]))
                                  const link = document.createElement('a')
                                  link.href = url
                                  link.setAttribute('download', `cover_letter_${jobId}.txt`)
                                  document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                                  toast.success('TXT downloaded successfully')
                                } catch (_) { toast.error('TXT download failed') }
                              }}
                            >
                              TXT
                            </motion.button>
                            <motion.button 
                              className="btn"
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              onClick={async () => {
                                try {
                                  const res = await api.get(`/documents/${result.cover_id}/download/?fmt=docx`, { responseType: 'blob' })
                                  const url = window.URL.createObjectURL(new Blob([res.data]))
                                  const link = document.createElement('a')
                                  link.href = url
                                  link.setAttribute('download', `cover_letter_${jobId}.docx`)
                                  document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                                  toast.success('DOCX downloaded successfully')
                                } catch (_) { toast.error('DOCX download failed') }
                              }}
                            >
                              DOCX
                            </motion.button>
                            <motion.button 
                              className="btn"
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              onClick={async () => {
                                try {
                                  const res = await api.get(`/documents/${result.cover_id}/download/?fmt=pdf`, { responseType: 'blob' })
                                  const url = window.URL.createObjectURL(new Blob([res.data]))
                                  const link = document.createElement('a')
                                  link.href = url
                                  link.setAttribute('download', `cover_letter_${jobId}.pdf`)
                                  document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                                  toast.success('PDF downloaded successfully')
                                } catch (_) { toast.error('PDF download failed') }
                              }}
                            >
                              PDF
                            </motion.button>
                          </div>
                        </div>
                      )}
                      {result.cv_id && (
                        <div style={{
                          padding: 16,
                          background: 'var(--bg-elev)',
                          borderRadius: 12,
                          border: '1px solid var(--border)'
                        }}>
                          <div style={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            gap: 8, 
                            marginBottom: 12 
                          }}>
                            <FileText size={18} style={{ color: 'var(--primary)' }} />
                            <span style={{ fontWeight: 600 }}>CV Generated</span>
                          </div>
                          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            <motion.button 
                              className="btn btn-primary"
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              onClick={() => navigate(`/documents/${result.cv_id}/edit`)}
                            >
                              <FileText size={14} />
                              Edit
                            </motion.button>
                            <motion.button 
                              className="btn"
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              onClick={async () => {
                                try {
                                  const res = await api.get(`/documents/${result.cv_id}/download/`, { responseType: 'blob' })
                                  const url = window.URL.createObjectURL(new Blob([res.data]))
                                  const link = document.createElement('a')
                                  link.href = url
                                  link.setAttribute('download', `cv_${jobId}.txt`)
                                  document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                                  toast.success('TXT downloaded successfully')
                                } catch (_) { toast.error('TXT download failed') }
                              }}
                            >
                              TXT
                            </motion.button>
                            <motion.button 
                              className="btn"
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              onClick={async () => {
                                try {
                                  const res = await api.get(`/documents/${result.cv_id}/download/?fmt=docx`, { responseType: 'blob' })
                                  const url = window.URL.createObjectURL(new Blob([res.data]))
                                  const link = document.createElement('a')
                                  link.href = url
                                  link.setAttribute('download', `cv_${jobId}.docx`)
                                  document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                                  toast.success('DOCX downloaded successfully')
                                } catch (_) { toast.error('DOCX download failed') }
                              }}
                            >
                              DOCX
                            </motion.button>
                            <motion.button 
                              className="btn"
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              onClick={async () => {
                                try {
                                  const res = await api.get(`/documents/${result.cv_id}/download/?fmt=pdf`, { responseType: 'blob' })
                                  const url = window.URL.createObjectURL(new Blob([res.data]))
                                  const link = document.createElement('a')
                                  link.href = url
                                  link.setAttribute('download', `cv_${jobId}.pdf`)
                                  document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                                  toast.success('PDF downloaded successfully')
                                } catch (_) { toast.error('PDF download failed') }
                              }}
                            >
                              PDF
                            </motion.button>
                          </div>
                        </div>
                      )}
                    </motion.div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
