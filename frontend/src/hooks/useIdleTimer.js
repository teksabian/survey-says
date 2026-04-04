import { useEffect, useRef } from 'react'

const IDLE_TIMEOUT = 30 * 60 * 1000 // 30 minutes

export default function useIdleTimer() {
  const timerRef = useRef(null)

  useEffect(() => {
    function resetTimer() {
      clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => {
        if (window.confirm(
          "Are You Still There?\n\nYou've been inactive for 30 minutes.\n\nClick OK to continue playing, or Cancel to refresh the page."
        )) {
          resetTimer()
        } else {
          window.location.reload()
        }
      }, IDLE_TIMEOUT)
    }

    resetTimer()

    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click']
    events.forEach(evt => {
      document.addEventListener(evt, resetTimer, { passive: true })
    })

    return () => {
      clearTimeout(timerRef.current)
      events.forEach(evt => {
        document.removeEventListener(evt, resetTimer)
      })
    }
  }, [])
}
