import React, { useEffect } from 'react'

export default function OAuthCallback() {
  useEffect(() => {
    try {
      const hash = window.location.hash || ''
      const params = new URLSearchParams(hash.startsWith('#') ? hash.slice(1) : hash)
      const access = params.get('access')
      const refresh = params.get('refresh')

      if (access) {
        try { window.localStorage.setItem('access', access) } catch {}
      }
      if (refresh) {
        try { window.localStorage.setItem('refresh', refresh) } catch {}
      }

      // Notify opener (if popup) and current window listeners
      try {
        if (window.opener && !window.opener.closed) {
          // Post message so cross-origin openers can receive tokens safely
          try {
            window.opener.postMessage({ type: 'oauth-complete', access, refresh }, '*')
          } catch {}
          // Set tokens on opener's storage as well (same-origin)
          try {
            window.opener.localStorage.setItem('access', access || '')
            if (refresh) window.opener.localStorage.setItem('refresh', refresh)
          } catch {}
          try {
            window.opener.dispatchEvent(new Event('auth-changed'))
            window.opener.dispatchEvent(new Event('storage'))
          } catch {}
          // Close popup with multiple attempts to handle timing quirks
          const attempts = [50, 200, 600]
          attempts.forEach((ms) => {
            setTimeout(() => {
              try { window.close() } catch {}
            }, ms)
          })
          // Final fallback: navigate to blank and close
          setTimeout(() => {
            try {
              window.location.replace('about:blank')
              window.close()
            } catch {}
          }, 1000)
          return
        }
      } catch {}

      // Fallback: redirect this window to dashboard
      window.dispatchEvent(new Event('auth-changed'))
      window.dispatchEvent(new Event('storage'))
      window.location.replace('/dashboard')
    } catch (e) {
      // On any error, go to login
      try { window.location.replace('/login') } catch {}
    }
  }, [])

  return (
    <div style={{ maxWidth: 480, margin: '80px auto', textAlign: 'center' }}>
      <div className="card">
        <div className="card-body">
          <h3 style={{ marginTop: 0 }}>Completing sign-in…</h3>
          <p>Please wait while we finalize authentication.</p>
        </div>
      </div>
    </div>
  )
}
