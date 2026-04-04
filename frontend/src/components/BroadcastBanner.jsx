import React, { useCallback } from 'react';

export default function BroadcastBanner({ message, onDismiss }) {
  const handleDismiss = useCallback(() => {
    if (message) {
      try {
        const dismissKey = 'broadcast_dismiss_' + btoa(message);
        localStorage.setItem(dismissKey, 'true');
      } catch {}
    }
    onDismiss();
  }, [message, onDismiss]);

  if (!message) return null;

  return (
    <div className="broadcast-banner">
      <span className="broadcast-banner-icon">{'\uD83D\uDCE2'}</span>
      <span>{message}</span>
      <div className="broadcast-close" onClick={handleDismiss}>&times;</div>
    </div>
  );
}
