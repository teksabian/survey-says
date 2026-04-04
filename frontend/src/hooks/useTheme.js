import { useState, useEffect, useCallback } from 'react'

const STORAGE_KEY = 'ff_player_theme'
const loadedFonts = new Set()

function loadFont(url) {
  if (!url || loadedFonts.has(url)) return
  loadedFonts.add(url)
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = url
  document.head.appendChild(link)
}

function applyThemeToDOM(theme) {
  if (!theme) return
  const root = document.documentElement.style
  root.setProperty('--font', theme.font_family)
  root.setProperty('--bg-gradient', theme.bg_gradient)
  root.setProperty('--bg-color', theme.bg_color)
  root.setProperty('--accent', theme.accent)
  root.setProperty('--card-border', theme.card_border)
  root.setProperty('--active-bg', theme.active_bg)
  root.setProperty('--active-border', theme.active_border)
  root.setProperty('--text', theme.text_primary)
  root.setProperty('--text-accent', theme.text_accent)
  root.setProperty('--text-muted', theme.text_muted)
  root.setProperty('--success', theme.success)
  root.setProperty('--success-text', theme.success_text)
  root.setProperty('--btn-bg', theme.btn_bg)
  root.setProperty('--btn-text', theme.btn_text)
  root.setProperty('--btn-blue-bg', theme.btn_blue_bg)
  root.setProperty('--btn-blue-text', theme.btn_blue_text)
  root.setProperty('--score-first-bg', theme.score_first_bg)
  root.setProperty('--score-first-text', theme.score_first_text)
  root.setProperty('--code-border', theme.code_border)
  if (theme.font_url) loadFont(theme.font_url)
  if (theme.elderly) {
    document.body.classList.add('elderly-theme')
  } else {
    document.body.classList.remove('elderly-theme')
  }
}

export default function useTheme(themes, hostThemeKey) {
  const [currentTheme, setCurrentTheme] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || hostThemeKey || 'classic'
    } catch {
      return hostThemeKey || 'classic'
    }
  })

  useEffect(() => {
    if (!themes) return
    const theme = themes[currentTheme]
    if (theme) {
      applyThemeToDOM(theme)
    }
  }, [currentTheme, themes])

  // Pre-load host font on init
  useEffect(() => {
    if (themes && hostThemeKey && themes[hostThemeKey]?.font_url) {
      loadFont(themes[hostThemeKey].font_url)
    }
  }, [themes, hostThemeKey])

  const selectTheme = useCallback((key) => {
    try {
      localStorage.setItem(STORAGE_KEY, key)
    } catch {}
    setCurrentTheme(key)
  }, [])

  const resetTheme = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {}
    setCurrentTheme(hostThemeKey || 'classic')
  }, [hostThemeKey])

  return { currentTheme, selectTheme, resetTheme }
}
