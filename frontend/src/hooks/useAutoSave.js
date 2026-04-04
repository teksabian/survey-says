import { useCallback, useRef } from 'react';

export default function useAutoSave(code, cacheBust, roundId) {
  const key = `feud_answers_${code}_${cacheBust}_round_${roundId}`;
  const saveTimeout = useRef(null);

  const save = useCallback((answers) => {
    try {
      localStorage.setItem(key, JSON.stringify(answers));
    } catch {}
  }, [key]);

  const debouncedSave = useCallback((answers) => {
    clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(() => save(answers), 500);
  }, [save]);

  const restore = useCallback(() => {
    try {
      const saved = localStorage.getItem(key);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  }, [key]);

  const clear = useCallback(() => {
    try { localStorage.removeItem(key); } catch {}
  }, [key]);

  return { save: debouncedSave, restore, clear };
}
