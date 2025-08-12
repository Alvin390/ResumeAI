import React, { createContext, useCallback, useContext, useMemo, useState } from 'react'

const ToastCtx = createContext({
  show: (_msg, _type) => {},
  success: (_msg) => {},
  error: (_msg) => {},
  info: (_msg) => {},
})

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const remove = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const show = useCallback((message, type = 'info', timeoutMs = 3000) => {
    const id = Math.random().toString(36).slice(2)
    setToasts(prev => [...prev, { id, message, type }])
    if (timeoutMs > 0) {
      setTimeout(() => remove(id), timeoutMs)
    }
  }, [remove])

  const api = useMemo(() => ({
    show,
    success: (m) => show(m, 'success'),
    error: (m) => show(m, 'error', 4500),
    info: (m) => show(m, 'info'),
  }), [show])

  return (
    <ToastCtx.Provider value={api}>
      {children}
      <div style={{ position: 'fixed', top: 12, right: 12, display: 'grid', gap: 8, zIndex: 9999 }}>
        {toasts.map(t => (
          <div key={t.id} onClick={() => remove(t.id)}
               style={{
                 maxWidth: 360,
                 padding: '10px 12px',
                 borderRadius: 6,
                 color: '#111',
                 boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
                 cursor: 'pointer',
                 background: t.type === 'success' ? '#D1FAE5' : t.type === 'error' ? '#FEE2E2' : '#E5E7EB',
                 border: '1px solid ' + (t.type === 'success' ? '#10B981' : t.type === 'error' ? '#EF4444' : '#9CA3AF')
               }}>
            <b style={{ marginRight: 6, textTransform: 'capitalize' }}>{t.type}</b>
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export function useToast() {
  return useContext(ToastCtx)
}
