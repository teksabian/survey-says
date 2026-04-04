import { useState, useEffect, useRef, useCallback } from 'react'
import ConnectionDot from './ConnectionDot'

const GEAR_SVG = (
  <svg className="settings-gear" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>
)

export default function FixedHeader({ roundNum, teamName, question, connected, onOpenSettings }) {
  const [compact, setCompact] = useState(false)
  const headerRef = useRef(null)

  // Compact header on mobile keyboard open
  const handleFocus = useCallback(() => {
    setCompact(true)
    document.body.classList.add('compact-mode')
  }, [])

  const handleBlur = useCallback(() => {
    setTimeout(() => {
      if (!document.activeElement || document.activeElement.tagName !== 'INPUT') {
        setCompact(false)
        document.body.classList.remove('compact-mode')
      }
    }, 100)
  }, [])

  useEffect(() => {
    const inputs = document.querySelectorAll('input[type="text"], input[type="number"]')
    inputs.forEach(input => {
      input.addEventListener('focus', handleFocus)
      input.addEventListener('blur', handleBlur)
    })
    return () => {
      inputs.forEach(input => {
        input.removeEventListener('focus', handleFocus)
        input.removeEventListener('blur', handleBlur)
      })
      document.body.classList.remove('compact-mode')
    }
  })

  // Prevent header tap from stealing focus
  const handleHeaderInteraction = useCallback((e) => {
    if (e.target.closest('.settings-gear')) return
    if (document.activeElement && document.activeElement.tagName === 'INPUT') {
      e.preventDefault()
    }
  }, [])

  return (
    <div
      ref={headerRef}
      className={`fixed-header${compact ? ' header-compact' : ''}`}
      onTouchStart={handleHeaderInteraction}
      onMouseDown={handleHeaderInteraction}
    >
      <div className="header-line1">
        <span>Round {roundNum} | {teamName}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span onClick={onOpenSettings}>{GEAR_SVG}</span>
          <ConnectionDot connected={connected} />
        </div>
      </div>
      {question && (
        <div className="header-line2">"{question}"</div>
      )}
    </div>
  )
}
