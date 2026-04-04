import { useCallback } from 'react'

export default function BroadcastBanner({ message, onDismiss }) {
  if (!message) return null

  const handleDismiss = useCallback(() => {
    try {
      const dismissKey = 'broadcast_dismiss_' + btoa(message)
      localStorage.setItem(dismissKey, 'true')
    } catch {}
    onDismiss()
  }, [message, onDismiss])

  return (
    <div className="broadcast-banner">
      <span className="broadcast-banner-icon">📢</span>
      <span>{message}</span>
      <div className="broadcast-close" onClick={handleDismiss}>×</div>
    </div>
  )
}
