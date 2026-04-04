import { useState, useCallback, useRef } from 'react'

const ICONS = {
  success: '✅',
  error: '❌',
  warning: '⚠️',
  info: 'ℹ️',
}

let nextId = 0

export function useToasts() {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, category = 'info', duration = 4000) => {
    const id = nextId++
    setToasts(prev => [...prev, { id, message, category }])
    setTimeout(() => {
      setToasts(prev => prev.map(t => t.id === id ? { ...t, removing: true } : t))
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id))
      }, 300)
    }, duration)
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.map(t => t.id === id ? { ...t, removing: true } : t))
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 300)
  }, [])

  return { toasts, addToast, removeToast }
}

export default function ToastContainer({ toasts, onRemove }) {
  return (
    <div id="toast-container">
      {toasts.map(toast => (
        <div key={toast.id} className={`toast ${toast.category}${toast.removing ? ' removing' : ''}`}>
          <span className="toast-icon">{ICONS[toast.category] || ICONS.info}</span>
          <span className="toast-content">{toast.message}</span>
          <button className="toast-close" onClick={() => onRemove(toast.id)}>&times;</button>
        </div>
      ))}
    </div>
  )
}
