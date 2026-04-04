import React, { createContext, useContext, useState, useCallback, useRef } from 'react';

const ToastContext = createContext(null);

const ICONS = {
  success: '\u2705',
  error: '\u274C',
  warning: '\u26A0\uFE0F',
  info: '\u2139\uFE0F',
};

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);

  const addToast = useCallback((message, category = 'info', duration = 4000) => {
    const id = ++idRef.current;
    setToasts(prev => [...prev, { id, message, category }]);

    setTimeout(() => {
      setToasts(prev => prev.map(t => t.id === id ? { ...t, removing: true } : t));
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, 300);
    }, duration);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.map(t => t.id === id ? { ...t, removing: true } : t));
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 300);
  }, []);

  return (
    <ToastContext.Provider value={addToast}>
      {children}
      <div id="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.category}${t.removing ? ' removing' : ''}`}>
            <div className="toast-icon">{ICONS[t.category] || ICONS.info}</div>
            <div className="toast-content">{t.message}</div>
            <button className="toast-close" onClick={() => removeToast(t.id)}>&times;</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
