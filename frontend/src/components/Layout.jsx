import React, { useEffect, useMemo, useState } from 'react'
import { NavLink, Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Sun, Moon, Menu, X } from 'lucide-react'

export default function Layout({ authed, status, onLogout, children }) {
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem('theme')
      if (saved) return saved
      // Default to light theme by design
      return 'light'
    } catch { return 'light' }
  })

  useEffect(() => {
    try {
      if (theme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light')
      } else {
        document.documentElement.removeAttribute('data-theme')
      }
      localStorage.setItem('theme', theme)
    } catch {}
  }, [theme])

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  const links = useMemo(() => {
    const motionProps = { whileHover: { scale: 1.1 }, whileTap: { scale: 0.95 } }
    const navLink = (to, text) => (
      <motion.div {...motionProps}>
        <NavLink to={to} className={({ isActive }) => isActive ? 'active' : ''}>{text}</NavLink>
      </motion.div>
    )

    return (
      <>
        {navLink('/', 'Home')}
        {!authed && navLink('/login', 'Login')}
        {!authed && navLink('/register', 'Register')}
        {authed && navLink('/dashboard', 'Dashboard')}
        {authed && navLink('/generate', 'Generate')}
        {authed && navLink('/documents', 'My Documents')}
        {authed && navLink('/profile', 'Profile')}
      </>
    )
  }, [authed])

  return (
    <div>
      <motion.div
        className="header"
        initial={{ y: -100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
      >
        <div className="container">
          <nav className="nav" aria-label="Primary">
            <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
              <Link to="/" className="brand" aria-label="ResumeAI home">ResumeAI</Link>
            </motion.div>
            {/* Desktop links */}
            <div className="nav-links" style={{ gap: 8 }}>{links}</div>
            <div className="spacer" />
            <span aria-live="polite" style={{ fontSize: 13, color: 'var(--muted)' }}>Health: {status}</span>
            
            <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }} className="btn btn-ghost" onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')} aria-label="Toggle theme">
              {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            </motion.button>
            {authed && (
              <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }} className="btn" onClick={onLogout} aria-label="Logout">Logout</motion.button>
            )}

            {/* Mobile toggle */}
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              className="btn btn-ghost mobile-toggle"
              aria-label="Toggle navigation"
              aria-controls="mobile-menu"
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen(v => !v)}
            >
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </motion.button>
          </nav>
        </div>
      </motion.div>

      {/* Mobile menu (visible under 768px via CSS) */}
      {mobileOpen && (
        <div id="mobile-menu" className="mobile-menu" role="dialog" aria-label="Mobile navigation">
          <div className="container">
            <div className="mobile-links">
              {links}
            </div>
          </div>
        </div>
      )}
      <motion.div
        className="container page"
        style={{ paddingTop: 24, paddingBottom: 40 }}
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -15 }}
        transition={{ duration: 0.25, ease: 'easeInOut' }}
      >
        {children}
      </motion.div>
    </div>
  )
}
