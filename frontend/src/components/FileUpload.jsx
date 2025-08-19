import React, { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, File, X, CheckCircle, AlertCircle } from 'lucide-react'

export default function FileUpload({ 
  onFileSelect, 
  accept = ".pdf,.doc,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword",
  maxSize = 10 * 1024 * 1024, // 10MB
  uploading = false,
  label = "Upload File"
}) {
  const [dragActive, setDragActive] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  const validateFile = (file) => {
    if (file.size > maxSize) {
      return `File size must be less than ${Math.round(maxSize / 1024 / 1024)}MB`
    }
    
    const acceptedTypes = accept.split(',').map(type => type.trim())
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase()
    const mimeType = file.type
    
    const isValidType = acceptedTypes.some(type => 
      type === fileExtension || type === mimeType || 
      (type.startsWith('.') && fileExtension === type) ||
      (type.includes('/') && mimeType === type)
    )
    
    if (!isValidType) {
      return 'File type not supported. Please upload PDF, DOC, or DOCX files.'
    }
    
    return null
  }

  const handleFile = (file) => {
    setError('')
    const validationError = validateFile(file)
    
    if (validationError) {
      setError(validationError)
      return
    }
    
    setSelectedFile(file)
    onFileSelect(file)
  }

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0])
    }
  }

  const handleChange = (e) => {
    e.preventDefault()
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0])
    }
  }

  const handleClick = () => {
    inputRef.current?.click()
  }

  const clearFile = () => {
    setSelectedFile(null)
    setError('')
    if (inputRef.current) {
      inputRef.current.value = ''
    }
  }

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  return (
    <div>
      <label className="label" style={{ marginBottom: 8 }}>{label}</label>
      
      <motion.div
        className="card"
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={handleClick}
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        style={{
          cursor: uploading ? 'not-allowed' : 'pointer',
          borderStyle: 'dashed',
          borderWidth: 2,
          borderColor: dragActive ? 'var(--primary)' : error ? 'var(--error)' : 'var(--border)',
          background: dragActive 
            ? 'linear-gradient(180deg, rgba(110, 168, 254, 0.1), rgba(59, 130, 246, 0.05))'
            : error 
            ? 'rgba(239, 68, 68, 0.05)'
            : 'var(--card-bg)',
          transition: 'all 0.2s ease',
          opacity: uploading ? 0.6 : 1
        }}
      >
        <div className="card-body" style={{ padding: 32, textAlign: 'center' }}>
          <AnimatePresence mode="wait">
            {selectedFile ? (
              <motion.div
                key="file-selected"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                style={{ display: 'flex', alignItems: 'center', gap: 16 }}
              >
                <div style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  background: 'var(--success)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white'
                }}>
                  <File size={24} />
                </div>
                <div style={{ flex: 1, textAlign: 'left' }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>{selectedFile.name}</div>
                  <div style={{ fontSize: 14, color: 'var(--muted)' }}>
                    {formatFileSize(selectedFile.size)}
                  </div>
                </div>
                {uploading ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--primary)' }}>
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      style={{ width: 20, height: 20, border: '2px solid var(--primary)', borderTop: '2px solid transparent', borderRadius: '50%' }}
                    />
                    <span style={{ fontSize: 14 }}>Uploading...</span>
                  </div>
                ) : (
                  <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={(e) => { e.stopPropagation(); clearFile(); }}
                    style={{
                      background: 'var(--error)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '50%',
                      width: 32,
                      height: 32,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer'
                    }}
                  >
                    <X size={16} />
                  </motion.button>
                )}
              </motion.div>
            ) : (
              <motion.div
                key="upload-prompt"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
              >
                <motion.div
                  animate={dragActive ? { scale: 1.1 } : { scale: 1 }}
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: '50%',
                    background: dragActive ? 'var(--primary)' : 'var(--bg-elev)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 16px',
                    color: dragActive ? 'white' : 'var(--primary)',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <Upload size={28} />
                </motion.div>
                
                <div style={{ marginBottom: 8 }}>
                  <span style={{ fontWeight: 600, color: 'var(--text)' }}>
                    {dragActive ? 'Drop your file here' : 'Click to upload or drag and drop'}
                  </span>
                </div>
                
                <div style={{ fontSize: 14, color: 'var(--muted)' }}>
                  PDF, DOC, DOCX up to {Math.round(maxSize / 1024 / 1024)}MB
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleChange}
        style={{ display: 'none' }}
        disabled={uploading}
      />

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{
              marginTop: 12,
              padding: '12px 16px',
              background: 'var(--error-bg)',
              border: '1px solid var(--error)',
              borderRadius: 10,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              color: 'var(--error)'
            }}
          >
            <AlertCircle size={16} />
            <span style={{ fontSize: 14 }}>{error}</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
