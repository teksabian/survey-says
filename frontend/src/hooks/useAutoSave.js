import { useCallback, useRef } from 'react'

export default function useAutoSave(code, cacheBust, roundId) {
  const key = `feud_answers_${code}_${cacheBust}_round_${roundId}`
  const saveTimeoutRef = useRef(null)

  const saveAnswers = useCallback((answers) => {
    clearTimeout(saveTimeoutRef.current)
    saveTimeoutRef.current = setTimeout(() => {
      try {
        localStorage.setItem(key, JSON.stringify(answers))
      } catch (e) {
        console.warn('[AUTOSAVE] Save failed:', e)
      }
    }, 500)
  }, [key])

  const saveAnswersImmediate = useCallback((answers) => {
    try {
      localStorage.setItem(key, JSON.stringify(answers))
    } catch (e) {
      console.warn('[AUTOSAVE] Save failed:', e)
    }
  }, [key])

  const restoreAnswers = useCallback(() => {
    try {
      const saved = localStorage.getItem(key)
      if (!saved) return null
      return JSON.parse(saved)
    } catch (e) {
      console.warn('[AUTOSAVE] Restore failed:', e)
      return null
    }
  }, [key])

  const clearSaved = useCallback(() => {
    try {
      localStorage.removeItem(key)
    } catch {}
  }, [key])

  return { saveAnswers, saveAnswersImmediate, restoreAnswers, clearSaved }
}
