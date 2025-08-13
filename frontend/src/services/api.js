import axios from 'axios'
const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
const api = axios.create({ baseURL, withCredentials: false })

// Attach auth header for each request
api.interceptors.request.use((config) => {
  const access = localStorage.getItem('access')
  const key = localStorage.getItem('token_key')
  if (access) {
    config.headers.Authorization = `Bearer ${access}`
  } else if (key) {
    config.headers.Authorization = `Token ${key}`
  } else {
    // Ensure no stale Authorization header leaks through
    if (config.headers && 'Authorization' in config.headers) {
      delete config.headers.Authorization
    }
    if (api.defaults.headers && 'Authorization' in api.defaults.headers) {
      delete api.defaults.headers.Authorization
    }
  }
  return config
})

let isRefreshing = false
let refreshPromise = null

api.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const { response, config } = error || {}
    if (!response) return Promise.reject(error) // network/timeout

    // Only attempt refresh on 401 and when using JWT (not Token key)
    if (response.status !== 401) return Promise.reject(error)

    // Prevent infinite loop
    if (config && config.__isRetry) {
      localStorage.removeItem('access')
      localStorage.removeItem('refresh')
      localStorage.removeItem('token_key')
      if (api.defaults.headers && 'Authorization' in api.defaults.headers) {
        delete api.defaults.headers.Authorization
      }
      try {
        if (typeof window !== 'undefined') window.dispatchEvent(new Event('auth-changed'))
        if (typeof window !== 'undefined' && window.location) window.location.replace('/login')
      } catch(_) {}
      return Promise.reject(error)
    }

    const refresh = localStorage.getItem('refresh')
    const hasTokenKey = !!localStorage.getItem('token_key')
    if (!refresh || hasTokenKey) {
      // Can't refresh (either no refresh token or using Token auth)
      localStorage.removeItem('access')
      localStorage.removeItem('refresh')
      if (api.defaults.headers && 'Authorization' in api.defaults.headers) {
        delete api.defaults.headers.Authorization
      }
      try {
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new Event('auth-changed'))
          window.dispatchEvent(new Event('storage'))
        }
        if (typeof window !== 'undefined' && window.location) window.location.replace('/login')
      } catch(_) {}
      return Promise.reject(error)
    }

    try {
      if (!isRefreshing) {
        isRefreshing = true
        refreshPromise = axios.post(`${baseURL}/auth/token/refresh/`, { refresh })
          .then(r => {
            const newAccess = r?.data?.access || r?.data?.access_token
            if (newAccess) {
              localStorage.setItem('access', newAccess)
              api.defaults.headers.Authorization = `Bearer ${newAccess}`
              try { if (typeof window !== 'undefined') window.dispatchEvent(new Event('auth-changed')) } catch(_) {}
            } else {
              localStorage.removeItem('access')
              localStorage.removeItem('refresh')
              if (api.defaults.headers && 'Authorization' in api.defaults.headers) {
                delete api.defaults.headers.Authorization
              }
              try { if (typeof window !== 'undefined') window.dispatchEvent(new Event('auth-changed')) } catch(_) {}
            }
            return newAccess
          })
          .catch(err => {
            localStorage.removeItem('access')
            localStorage.removeItem('refresh')
            if (api.defaults.headers && 'Authorization' in api.defaults.headers) {
              delete api.defaults.headers.Authorization
            }
            try {
              if (typeof window !== 'undefined') window.dispatchEvent(new Event('auth-changed'))
              if (typeof window !== 'undefined' && window.location) window.location.replace('/login')
            } catch(_) {}
            throw err
          })
          .finally(() => { isRefreshing = false })
      }

      const newAccess = await refreshPromise
      if (!newAccess) return Promise.reject(error)
      // retry original request once
      const retry = { ...config, __isRetry: true }
      retry.headers = { ...(retry.headers || {}), Authorization: `Bearer ${newAccess}` }
      return api.request(retry)
    } catch (e) {
      return Promise.reject(error)
    }
  }
)

// Centralized logout helper to fully clear auth and headers
api.logout = () => {
  try {
    localStorage.removeItem('access')
    localStorage.removeItem('refresh')
    localStorage.removeItem('token_key')
  } catch (_) {}
  try {
    if (api.defaults.headers && 'Authorization' in api.defaults.headers) {
      delete api.defaults.headers.Authorization
    }
  } catch (_) {}
  try {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event('auth-changed'))
      window.dispatchEvent(new Event('storage'))
    }
  } catch (_) {}
}

export default api
