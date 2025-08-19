import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import TextStyle from '@tiptap/extension-text-style'
import FontFamily from '@tiptap/extension-font-family'
import api from '../services/api'
import { useToast } from '../services/toast.jsx'
import { motion } from 'framer-motion'
import { 
  Bold, 
  Italic, 
  Underline as UnderlineIcon, 
  Heading1, 
  Heading2, 
  List, 
  ListOrdered, 
  Undo2, 
  Redo2,
  Save,
  Download,
  FileText,
  FileImage,
  Eye
} from 'lucide-react'

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
        {/* Enhanced Toolbar */}
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 4, 
          marginBottom: 16, 
          flexWrap: 'wrap',
          padding: '12px 16px',
          background: 'var(--bg-elev)',
          borderRadius: 12,
          border: '1px solid var(--border)'
        }}>
          {/* Text Formatting Group */}
          <div style={{ display: 'flex', gap: 2, marginRight: 12 }}>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => editor && editor.chain().focus().toggleBold().run()}
              disabled={!editor}
              aria-pressed={editor?.isActive('bold')}
              className="btn"
              style={{ 
                background: editor?.isActive('bold') ? 'var(--primary)' : 'transparent',
                color: editor?.isActive('bold') ? 'white' : 'var(--text)',
                border: '1px solid var(--border)',
                padding: '8px',
                minWidth: 36,
                height: 36
              }}
              title="Bold"
            >
              <Bold size={16} />
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => editor && editor.chain().focus().toggleItalic().run()}
              disabled={!editor}
              aria-pressed={editor?.isActive('italic')}
              className="btn"
              style={{ 
                background: editor?.isActive('italic') ? 'var(--primary)' : 'transparent',
                color: editor?.isActive('italic') ? 'white' : 'var(--text)',
                border: '1px solid var(--border)',
                padding: '8px',
                minWidth: 36,
                height: 36
              }}
              title="Italic"
            >
              <Italic size={16} />
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => editor && editor.chain().focus().toggleUnderline().run()}
              disabled={!editor}
              aria-pressed={editor?.isActive('underline')}
              className="btn"
              style={{ 
                background: editor?.isActive('underline') ? 'var(--primary)' : 'transparent',
                color: editor?.isActive('underline') ? 'white' : 'var(--text)',
                border: '1px solid var(--border)',
                padding: '8px',
                minWidth: 36,
                height: 36
              }}
              title="Underline"
            >
              <UnderlineIcon size={16} />
            </motion.button>
          </div>

          {/* Divider */}
          <div style={{ width: 1, height: 24, background: 'var(--border)', marginRight: 12 }}></div>

          {/* Headings Group */}
          <div style={{ display: 'flex', gap: 2, marginRight: 12 }}>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => editor && editor.chain().focus().toggleHeading({ level: 1 }).run()}
              disabled={!editor}
              aria-pressed={editor?.isActive('heading', { level: 1 })}
              className="btn"
              style={{ 
                background: editor?.isActive('heading', { level: 1 }) ? 'var(--primary)' : 'transparent',
                color: editor?.isActive('heading', { level: 1 }) ? 'white' : 'var(--text)',
                border: '1px solid var(--border)',
                padding: '8px',
                minWidth: 36,
                height: 36
              }}
              title="Heading 1"
            >
              <Heading1 size={16} />
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => editor && editor.chain().focus().toggleHeading({ level: 2 }).run()}
              disabled={!editor}
              aria-pressed={editor?.isActive('heading', { level: 2 })}
              className="btn"
              style={{ 
                background: editor?.isActive('heading', { level: 2 }) ? 'var(--primary)' : 'transparent',
                color: editor?.isActive('heading', { level: 2 }) ? 'white' : 'var(--text)',
                border: '1px solid var(--border)',
                padding: '8px',
                minWidth: 36,
                height: 36
              }}
              title="Heading 2"
            >
              <Heading2 size={16} />
            </motion.button>
          </div>

          {/* Divider */}
          <div style={{ width: 1, height: 24, background: 'var(--border)', marginRight: 12 }}></div>

          {/* Lists Group */}
          <div style={{ display: 'flex', gap: 2, marginRight: 12 }}>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => editor && editor.chain().focus().toggleBulletList().run()}
              disabled={!editor}
              aria-pressed={editor?.isActive('bulletList')}
              className="btn"
              style={{ 
                background: editor?.isActive('bulletList') ? 'var(--primary)' : 'transparent',
                color: editor?.isActive('bulletList') ? 'white' : 'var(--text)',
                border: '1px solid var(--border)',
                padding: '8px',
                minWidth: 36,
                height: 36
              }}
              title="Bullet List"
            >
              <List size={16} />
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => editor && editor.chain().focus().toggleOrderedList().run()}
              disabled={!editor}
              aria-pressed={editor?.isActive('orderedList')}
              className="btn"
              style={{ 
                background: editor?.isActive('orderedList') ? 'var(--primary)' : 'transparent',
                color: editor?.isActive('orderedList') ? 'white' : 'var(--text)',
                border: '1px solid var(--border)',
                padding: '8px',
                minWidth: 36,
                height: 36
              }}
              title="Numbered List"
            >
              <ListOrdered size={16} />
            </motion.button>
          </div>

          {/* Divider */}
          <div style={{ width: 1, height: 24, background: 'var(--border)', marginRight: 12 }}></div>

          {/* History Group */}
          <div style={{ display: 'flex', gap: 2, marginRight: 12 }}>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => editor && editor.chain().focus().undo().run()}
              disabled={!editor || !editor.can().undo()}
              className="btn"
              style={{ 
                background: 'transparent',
                color: 'var(--text)',
                border: '1px solid var(--border)',
                padding: '8px',
                minWidth: 36,
                height: 36,
                opacity: !editor || !editor.can().undo() ? 0.5 : 1
              }}
              title="Undo"
            >
              <Undo2 size={16} />
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => editor && editor.chain().focus().redo().run()}
              disabled={!editor || !editor.can().redo()}
              className="btn"
              style={{ 
                background: 'transparent',
                color: 'var(--text)',
                border: '1px solid var(--border)',
                padding: '8px',
                minWidth: 36,
                height: 36,
                opacity: !editor || !editor.can().redo() ? 0.5 : 1
              }}
              title="Redo"
            >
              <Redo2 size={16} />
            </motion.button>
          </div>

          {/* Font Family Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto' }}>
            <label style={{ fontSize: 13, color: 'var(--muted)', fontWeight: 500 }}>Font:</label>
            <select
              onChange={(e) => {
                if (!editor) return
                const val = e.target.value
                if (val) editor.chain().focus().setFontFamily(val).run()
                else editor.chain().focus().unsetFontFamily().run()
              }}
              defaultValue=""
              className="select"
              style={{ 
                width: 180,
                fontSize: 13,
                padding: '6px 10px',
                height: 36
              }}
            >
              <option value="">Default</option>
              <option value="Inter, system-ui, sans-serif">Inter</option>
              <option value="Georgia, serif">Georgia</option>
              <option value="Times New Roman, Times, serif">Times New Roman</option>
              <option value="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">Monospace</option>
            </select>
          </div>
        </div>
        <div style={{ border: '1px solid var(--border)', borderRadius: 12, minHeight: 400, padding: 8, background: 'var(--bg-elev)' }}>
          <EditorContent editor={editor} />
        </div>
        <div style={{ marginTop: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <label style={{ fontSize: 14, fontWeight: 500, color: 'var(--text)' }}>File name:</label>
            <input 
              value={fileName} 
              onChange={(e) => setFileName(e.target.value)} 
              className="input" 
              style={{ minWidth: 240, maxWidth: 360, fontSize: 14 }} 
            />
          </div>
          
          <div style={{ display: 'flex', gap: 8 }}>
            <motion.button 
              className="btn btn-primary" 
              onClick={() => onSave(false)} 
              disabled={saving} 
              aria-busy={saving}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              style={{ display: 'flex', alignItems: 'center', gap: 8 }}
            >
              <Save size={16} />
              {saving ? 'Saving…' : 'Save New Version'}
            </motion.button>
            
            <motion.button 
              className="btn" 
              onClick={() => onSave(true)} 
              disabled={saving} 
              aria-busy={saving}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              style={{ display: 'flex', alignItems: 'center', gap: 8 }}
            >
              <Eye size={16} />
              {saving ? 'Saving…' : 'Save & Preview'}
            </motion.button>
          </div>

          <div style={{ width: 1, height: 24, background: 'var(--border)' }}></div>
          
          <div style={{ display: 'flex', gap: 8 }}>
            <motion.button 
              className="btn" 
              onClick={() => download('')}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              style={{ display: 'flex', alignItems: 'center', gap: 8 }}
            >
              <FileText size={16} />
              TXT
            </motion.button>
            
            <motion.button 
              className="btn" 
              onClick={() => download('docx')}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              style={{ display: 'flex', alignItems: 'center', gap: 8 }}
            >
              <Download size={16} />
              DOCX
            </motion.button>
            
            <motion.button 
              className="btn" 
              onClick={() => download('pdf')}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              style={{ display: 'flex', alignItems: 'center', gap: 8 }}
            >
              <FileImage size={16} />
              PDF
            </motion.button>
          </div>
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
