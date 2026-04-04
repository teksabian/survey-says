import { useState, useEffect, useCallback, useRef } from 'react';

const STORAGE_KEY = 'ff_player_theme';

export default function useTheme(themes, hostThemeKey) {
  const [currentTheme, setCurrentTheme] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || hostThemeKey || 'gamenight';
    } catch {
      return hostThemeKey || 'gamenight';
    }
  });

  const loadedFonts = useRef(new Set());

  useEffect(() => {
    if (!themes) return;
    const t = themes[currentTheme];
    if (!t) return;

    const root = document.documentElement.style;
    root.setProperty('--font', t.font_family);
    root.setProperty('--bg-gradient', t.bg_gradient);
    root.setProperty('--bg-color', t.bg_color);
    root.setProperty('--accent', t.accent);
    root.setProperty('--card-border', t.card_border);
    root.setProperty('--active-bg', t.active_bg);
    root.setProperty('--active-border', t.active_border);
    root.setProperty('--text', t.text_primary);
    root.setProperty('--text-accent', t.text_accent);
    root.setProperty('--text-muted', t.text_muted);
    root.setProperty('--success', t.success);
    root.setProperty('--success-text', t.success_text);
    root.setProperty('--btn-bg', t.btn_bg);
    root.setProperty('--btn-text', t.btn_text);
    root.setProperty('--btn-blue-bg', t.btn_blue_bg);
    root.setProperty('--btn-blue-text', t.btn_blue_text);
    root.setProperty('--score-first-bg', t.score_first_bg);
    root.setProperty('--score-first-text', t.score_first_text);
    root.setProperty('--code-border', t.code_border);

    // Load font if needed
    if (t.font_url && !loadedFonts.current.has(t.font_url)) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = t.font_url;
      document.head.appendChild(link);
      loadedFonts.current.add(t.font_url);
    }

    // Toggle elderly/easy-read body class
    if (t.elderly) {
      document.body.classList.add('elderly-theme');
    } else {
      document.body.classList.remove('elderly-theme');
    }
  }, [currentTheme, themes]);

  const selectTheme = useCallback((key) => {
    try { localStorage.setItem(STORAGE_KEY, key); } catch {}
    setCurrentTheme(key);
  }, []);

  const resetTheme = useCallback(() => {
    try { localStorage.removeItem(STORAGE_KEY); } catch {}
    setCurrentTheme(hostThemeKey || 'gamenight');
  }, [hostThemeKey]);

  return { currentTheme, selectTheme, resetTheme };
}
