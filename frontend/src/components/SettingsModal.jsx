export default function SettingsModal({ open, onClose, themes, currentTheme, onSelectTheme, onResetTheme }) {
  if (!open || !themes) return null

  const standardThemes = []
  const easyReadThemes = []

  Object.entries(themes).forEach(([key, theme]) => {
    if (theme.elderly) {
      easyReadThemes.push({ key, ...theme })
    } else {
      standardThemes.push({ key, ...theme })
    }
  })

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div className="settings-overlay open" onClick={handleOverlayClick}>
      <div className="settings-panel">
        <div className="settings-header">
          <h3>Settings</h3>
          <button className="settings-close" onClick={onClose}>&times;</button>
        </div>
        <div className="settings-section">
          <div className="settings-section-title">Color Theme</div>
          <div className="theme-grid">
            <div className="theme-section-label">Standard</div>
            {standardThemes.map(theme => (
              <div
                key={theme.key}
                className={`theme-option${theme.key === currentTheme ? ' active' : ''}`}
                onClick={() => onSelectTheme(theme.key)}
              >
                <div className="theme-swatch" style={{ background: theme.accent }} />
                <span className="theme-option-name">{theme.name}</span>
              </div>
            ))}
            {easyReadThemes.length > 0 && (
              <>
                <div className="theme-section-label">Easy Read</div>
                {easyReadThemes.map(theme => (
                  <div
                    key={theme.key}
                    className={`theme-option${theme.key === currentTheme ? ' active' : ''}`}
                    onClick={() => onSelectTheme(theme.key)}
                  >
                    <div className="theme-swatch" style={{ background: theme.accent }} />
                    <span className="theme-option-name">{theme.name}</span>
                  </div>
                ))}
              </>
            )}
          </div>
          <button className="theme-reset" onClick={onResetTheme}>Reset to Default</button>
        </div>
      </div>
    </div>
  )
}
