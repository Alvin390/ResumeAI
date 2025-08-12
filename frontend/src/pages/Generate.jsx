import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useToast } from '../services/toast.jsx'
import api from '../services/api'

export default function Generate() {
  const [jd, setJd] = useState('')
  const [cvList, setCvList] = useState([])
  const [selectedCv, setSelectedCv] = useState('')
  const [template, setTemplate] = useState('classic')
  const [jobId, setJobId] = useState(null)
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const [result, setResult] = useState({ cover_id: null, cv_id: null })
  const navigate = useNavigate()
  const toast = useToast()

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
      .then(r => setCvList(r.data))
      .catch((e) => {
        if (e?.response?.status === 401) {
          console.warn('[Generate] GET /cv/ unauthorized → redirect to /login')
          navigate('/login')
        } else {
          toast.error('Failed to load CV list')
        }
      })
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

  return (
    <div style={{ maxWidth: 760, margin: '32px auto' }}>
      <h2>Generate tailored CV & Cover Letter</h2>
      <form onSubmit={onStart} style={{ marginTop: 12 }}>
        <div style={{ marginBottom: 12 }}>
          <label>Job Description</label>
          <textarea value={jd} onChange={e=>setJd(e.target.value)} rows={8} style={{ width: '100%' }} placeholder="Paste the job description here" />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label>Use CV</label>
          <select value={selectedCv} onChange={e=>setSelectedCv(e.target.value)} style={{ width: '100%' }}>
            <option value=''>Use latest profile CV</option>
            {cvList.map(cv => (
              <option key={cv.id} value={cv.id}>v{cv.version} — {cv.file_name}</option>
            ))}
          </select>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label>Template</label>
          <select value={template} onChange={e=>setTemplate(e.target.value)}>
            <option value='classic'>Classic</option>
            <option value='modern'>Modern</option>
            <option value='compact'>Compact</option>
          </select>
        </div>
        {error && <div style={{ color: 'red', marginBottom: 8 }}>{error}</div>}
        <button type="submit" disabled={!jd.trim() || status === 'queued' || status === 'running'}>
          {status === 'running' ? 'Generating…' : status === 'queued' ? 'Queued…' : 'Generate'}
        </button>
      </form>

      {jobId && (
        <div style={{ marginTop: 16 }}>
          <div><b>Job ID:</b> {jobId} — <b>Status:</b> {status}</div>
          {(result.cover_id || result.cv_id) && (
            <div style={{ marginTop: 8, display: 'grid', gap: 10 }}>
              {result.cover_id && (
                <div>
                  <b>Cover Letter:</b>
                  <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                    <button onClick={() => navigate(`/documents/${result.cover_id}/edit`)}>Edit</button>
                    <button onClick={async () => {
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
                    <button onClick={async () => {
                      try {
                        const res = await api.get(`/documents/${result.cover_id}/download/?format=docx`, { responseType: 'blob' })
                        const url = window.URL.createObjectURL(new Blob([res.data]))
                        const link = document.createElement('a')
                        link.href = url
                        link.setAttribute('download', `cover_letter_${jobId}.docx`)
                        document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                        toast.success('DOCX downloaded successfully')
                      } catch (_) { toast.error('DOCX download failed') }
                    }}>DOCX</button>
                    <button onClick={async () => {
                      try {
                        const res = await api.get(`/documents/${result.cover_id}/download/?format=pdf`, { responseType: 'blob' })
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
                    <button onClick={() => navigate(`/documents/${result.cv_id}/edit`)}>Edit</button>
                    <button onClick={async () => {
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
                    <button onClick={async () => {
                      try {
                        const res = await api.get(`/documents/${result.cv_id}/download/?format=docx`, { responseType: 'blob' })
                        const url = window.URL.createObjectURL(new Blob([res.data]))
                        const link = document.createElement('a')
                        link.href = url
                        link.setAttribute('download', `generated_cv_${jobId}.docx`)
                        document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
                        toast.success('DOCX downloaded successfully')
                      } catch (_) { toast.error('DOCX download failed') }
                    }}>DOCX</button>
                    <button onClick={async () => {
                      try {
                        const res = await api.get(`/documents/${result.cv_id}/download/?format=pdf`, { responseType: 'blob' })
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
      )}
    </div>
  )
}
