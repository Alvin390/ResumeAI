import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import TextStyle from '@tiptap/extension-text-style'
import FontFamily from '@tiptap/extension-font-family'
import api from '../services/api'
import { useToast } from '../services/toast.jsx'

function textToHtml(text) {
  if (!text) return '<p></p>'
  const esc = (s) => s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))
  return text.split(/\r?\n/).map(line => `<p>${esc(line)}</p>`).join('\n')
}

function htmlToText(html) {
  // Very basic strip to text by replacing block tags with newlines
  if (!html) return ''
  const tmp = document.createElement('div')
  tmp.innerHTML = html
  return (tmp.textContent || tmp.innerText || '').replace(/\u00A0/g, ' ').trimEnd()
}

export default function EditorPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [doc, setDoc] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')
  const [fileName, setFileName] = useState('')
  const toast = useToast()

  const editor = useEditor({
    extensions: [StarterKit, Underline, TextStyle, FontFamily],
    content: '<p>Loading…</p>',
  })

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const { data } = await api.get(`/documents/${id}/`)
      setDoc(data)
      const html = textToHtml(data.text || '')
      if (editor) editor.commands.setContent(html)
      // initialize editable file name (default to .txt for text saves)
      const def = (data.file_name?.replace(/\.[^.]+$/, '') || 'document') + '.txt'
      setFileName(def)
      // Load preview for current version
      try {
        const res = await api.get(`/documents/${id}/download/?fmt=pdf`, { responseType: 'blob' })
        const url = URL.createObjectURL(res.data)
        setPreviewUrl((prev) => { try { if (prev) URL.revokeObjectURL(prev) } catch(_){}; return url })
        toast.info('Preview loaded')
      } catch (_) { /* ignore preview error */ }
      // Restore any draft from sessionStorage
      try {
        const raw = sessionStorage.getItem(`draft:doc:${id}`)
        if (raw) {
          const draft = JSON.parse(raw)
          if (draft?.text) {
            if (editor) editor.commands.setContent(textToHtml(draft.text))
          }
          if (draft?.fileName) setFileName(draft.fileName)
        }
      } catch (_) {}
    } catch (e) {
      if (e?.response?.status === 401) { navigate('/login'); return }
      setError(e?.response?.data?.detail || 'Failed to load document')
      toast.error('Failed to load document')
    } finally { setLoading(false) }
  }, [id, editor, navigate])

  useEffect(() => { load() }, [load])
  useEffect(() => () => { try { if (previewUrl) URL.revokeObjectURL(previewUrl) } catch(_){} }, [previewUrl])

  const onSave = async (doPreview=false) => {
    if (!editor || !doc) return
    setSaving(true); setError('')
    try {
      const html = editor.getHTML()
      const text = htmlToText(html)
      const payload = {
        doc_type: doc.doc_type,
        content: text,
        content_type: 'text/plain',
        file_name: (fileName || ((doc.file_name?.replace(/\.[^.]+$/, '') || 'document') + '.txt')),
      }
      const { data: saved } = await api.post('/documents/save/', payload)
      // Navigate to the new document version
      if (doPreview) {
        try {
          const res = await api.get(`/documents/${saved.id}/download/?fmt=pdf`, { responseType: 'blob' })
          const url = URL.createObjectURL(res.data)
          setPreviewUrl((prev) => { try { if (prev) URL.revokeObjectURL(prev) } catch(_){}; return url })
        } catch (_) {}
      }
      navigate(`/documents/${saved.id}/edit`)
      toast.success('Saved new version')
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to save document')
      toast.error('Failed to save document')
    } finally { setSaving(false) }
  }

  const download = async (format) => {
    if (!doc) return
    try {
      const res = await api.get(`/documents/${doc.id}/download/${format ? `?fmt=${format}` : ''}`, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      const base = (doc.file_name?.replace(/\.[^.]+$/, '') || 'document')
      link.setAttribute('download', `${base}${format ? '.'+format : ''}`)
      document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url)
      toast.success(`${format ? format.toUpperCase() : 'TXT'} downloaded`)
    } catch (_) { toast.error('Download failed') }
  }

  // Auto-save draft to sessionStorage whenever content or fileName changes
  useEffect(() => {
    if (!editor) return
    const key = `draft:doc:${id}`
    const handler = () => {
      try {
        const text = htmlToText(editor.getHTML())
        sessionStorage.setItem(key, JSON.stringify({ text, fileName }))
      } catch (_) {}
    }
    editor.on('update', handler)
    return () => {
      try {
        handler()
        editor.off('update', handler)
      } catch (_) {}
    }
  }, [editor, id, fileName])

  return (
    <div style={{ maxWidth: 1100, margin: '24px auto', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <div>
        <h2>Edit Document</h2>
        {loading ? <div>Loading…</div> : null}
        {error ? <div style={{ color: 'red' }}>{error}</div> : null}
        {doc ? (
          <div style={{ marginBottom: 8, color: '#444' }}>
            <div><b>Type:</b> {doc.doc_type} — <b>v</b>{doc.version} — <b>File:</b> {doc.file_name}</div>
          </div>
        ) : null}
        {/* Toolbar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
          <button
            onClick={() => editor && editor.chain().focus().toggleBold().run()}
            disabled={!editor}
            aria-pressed={editor?.isActive('bold')}
            className="btn"
            style={{ background: editor?.isActive('bold') ? 'rgba(255,255,255,0.12)' : undefined }}
          >
            B
          </button>
          <button
            onClick={() => editor && editor.chain().focus().toggleItalic().run()}
            disabled={!editor}
            aria-pressed={editor?.isActive('italic')}
            className="btn"
            style={{ background: editor?.isActive('italic') ? 'rgba(255,255,255,0.12)' : undefined }}
          >
            I
          </button>
          <button
            onClick={() => editor && editor.chain().focus().toggleUnderline().run()}
            disabled={!editor}
            aria-pressed={editor?.isActive('underline')}
            className="btn"
            style={{ background: editor?.isActive('underline') ? 'rgba(255,255,255,0.12)' : undefined }}
          >
            U
          </button>
          <button onClick={() => editor && editor.chain().focus().toggleHeading({ level: 1 }).run()} disabled={!editor} className="btn">H1</button>
          <button onClick={() => editor && editor.chain().focus().toggleHeading({ level: 2 }).run()} disabled={!editor} className="btn">H2</button>
          <button onClick={() => editor && editor.chain().focus().toggleBulletList().run()} disabled={!editor} className="btn">• List</button>
          <button onClick={() => editor && editor.chain().focus().toggleOrderedList().run()} disabled={!editor} className="btn">1. List</button>
          <button onClick={() => editor && editor.chain().focus().undo().run()} disabled={!editor} className="btn">Undo</button>
          <button onClick={() => editor && editor.chain().focus().redo().run()} disabled={!editor} className="btn">Redo</button>
          <label style={{ marginLeft: 8, color: 'var(--muted)' }}>Font:</label>
          <select
            onChange={(e) => {
              if (!editor) return
              const val = e.target.value
              if (val) editor.chain().focus().setFontFamily(val).run()
              else editor.chain().focus().unsetFontFamily().run()
            }}
            defaultValue=""
            className="input"
            style={{ width: 200 }}
          >
            <option value="">Default</option>
            <option value="Inter, system-ui, sans-serif">Inter</option>
            <option value="Georgia, serif">Georgia</option>
            <option value="Times New Roman, Times, serif">Times New Roman</option>
            <option value="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">Monospace</option>
          </select>
        </div>
        <div style={{ border: '1px solid var(--border)', borderRadius: 12, minHeight: 400, padding: 8, background: 'var(--bg-elev)' }}>
          <EditorContent editor={editor} />
        </div>
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <label>File name:</label>
          <input value={fileName} onChange={(e) => setFileName(e.target.value)} className="input" style={{ minWidth: 240, maxWidth: 360 }} />
          <button className="btn btn-primary" onClick={() => onSave(false)} disabled={saving} aria-busy={saving}>{saving ? 'Saving…' : 'Save New Version'}</button>
          <button className="btn" onClick={() => onSave(true)} disabled={saving} aria-busy={saving}>{saving ? 'Saving…' : 'Save & Refresh Preview'}</button>
          <span style={{ marginLeft: 16 }}></span>
          <button className="btn" onClick={() => download('')}>Download .txt</button>
          <button className="btn" onClick={() => download('docx')}>Download .docx</button>
          <button className="btn" onClick={() => download('pdf')}>Download .pdf</button>
        </div>
      </div>
      <div>
        <h3>PDF Preview</h3>
        {previewUrl ? (
          <iframe title="preview" src={previewUrl} style={{ width: '100%', height: 600, border: '1px solid var(--border)', borderRadius: 12, background: 'var(--bg-elev)' }} />
        ) : (
          <div style={{ height: 600, display:'flex', alignItems:'center', justifyContent:'center', border:'1px solid var(--border)', borderRadius:12, background: 'var(--bg-elev)' }}>
            <span>No preview</span>
          </div>
        )}
      </div>
    </div>
  )
}
