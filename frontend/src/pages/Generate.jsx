import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useToast } from '../services/toast.jsx'
import api from '../services/api'
import { GenerateSkeleton } from '../components/Skeleton.jsx'

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
              <div style={{ marginBottom: 10 }}>
                <div className="label">Choose Template</div>
                <div style={{ display: 'grid', gap: 10 }}>
                  {templates.map(t => (
                    <button type="button" key={t.id} className="card" onClick={() => setTemplate(t.id)} aria-pressed={template === t.id} style={{ borderWidth: template === t.id ? 2 : 1, borderColor: template === t.id ? 'var(--primary)' : 'var(--border)' }}>
                      <div className="card-body" style={{ padding: '12px 14px' }}>
                        <div style={{ fontWeight: 600 }}>{t.title}</div>
                        <div style={{ fontSize: 12, color: 'var(--muted)' }}>{t.desc}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
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
          {jobId && (
            <div className="card">
              <div className="card-body">
                <div><b>Job ID:</b> {jobId} — <b>Status:</b> {status}</div>
                {(result.cover_id || result.cv_id) && (
                  <div className="stack" style={{ marginTop: 8 }}>
                    {result.cover_id && (
                      <div>
                        <b>Cover Letter:</b>
                        <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                          <button className="btn" onClick={() => navigate(`/documents/${result.cover_id}/edit`)}>Edit</button>
                          <button className="btn" onClick={async () => {
                            try {
                              const res = await api.get(`/documents/${result.cover_id}/download/`, { responseType: 'blob' })
                              const url = window.URL.createObjectURL(new Blob([res.data]))
                              const link = document.createElement('a')
                              link.href = url
                              link.setAttribute('download', `cover_letter_${jobId}.txt`)
                              document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                              toast.success('TXT downloaded successfully')
                            } catch (_) { toast.error('TXT download failed') }
                          }}>TXT</button>
                          <button className="btn" onClick={async () => {
                            try {
                              const res = await api.get(`/documents/${result.cover_id}/download/?fmt=docx`, { responseType: 'blob' })
                              const url = window.URL.createObjectURL(new Blob([res.data]))
                              const link = document.createElement('a')
                              link.href = url
                              link.setAttribute('download', `cover_letter_${jobId}.docx`)
                              document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                              toast.success('DOCX downloaded successfully')
                            } catch (_) { toast.error('DOCX download failed') }
                          }}>DOCX</button>
                          <button className="btn" onClick={async () => {
                            try {
                              const res = await api.get(`/documents/${result.cover_id}/download/?fmt=pdf`, { responseType: 'blob' })
                              const url = window.URL.createObjectURL(new Blob([res.data]))
                              const link = document.createElement('a')
                              link.href = url
                              link.setAttribute('download', `cover_letter_${jobId}.pdf`)
                              document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                              toast.success('PDF downloaded successfully')
                            } catch (_) { toast.error('PDF download failed') }
                          }}>PDF</button>
                        </div>
                      </div>
                    )}
                    {result.cv_id && (
                      <div>
                        <b>Generated CV:</b>
                        <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                          <button className="btn" onClick={() => navigate(`/documents/${result.cv_id}/edit`)}>Edit</button>
                          <button className="btn" onClick={async () => {
                            try {
                              const res = await api.get(`/documents/${result.cv_id}/download/`, { responseType: 'blob' })
                              const url = window.URL.createObjectURL(new Blob([res.data]))
                              const link = document.createElement('a')
                              link.href = url
                              link.setAttribute('download', `generated_cv_${jobId}.txt`)
                              document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                              toast.success('TXT downloaded successfully')
                            } catch (_) { toast.error('TXT download failed') }
                          }}>TXT</button>
                          <button className="btn" onClick={async () => {
                            try {
                              const res = await api.get(`/documents/${result.cv_id}/download/?fmt=docx`, { responseType: 'blob' })
                              const url = window.URL.createObjectURL(new Blob([res.data]))
                              const link = document.createElement('a')
                              link.href = url
                              link.setAttribute('download', `generated_cv_${jobId}.docx`)
                              document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                              toast.success('DOCX downloaded successfully')
                            } catch (_) { toast.error('DOCX download failed') }
                          }}>DOCX</button>
                          <button className="btn" onClick={async () => {
                            try {
                              const res = await api.get(`/documents/${result.cv_id}/download/?fmt=pdf`, { responseType: 'blob' })
                              const url = window.URL.createObjectURL(new Blob([res.data]))
                              const link = document.createElement('a')
                              link.href = url
                              link.setAttribute('download', `generated_cv_${jobId}.pdf`)
                              document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                              toast.success('PDF downloaded successfully')
                            } catch (_) { toast.error('PDF download failed') }
                          }}>PDF</button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
