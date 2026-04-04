import React from 'react';

export default function SettingsModal({ open, onClose, themes, currentTheme, onSelectTheme, onResetTheme }) {
  if (!themes) return null;

  const standard = [];
  const easyRead = [];

  Object.entries(themes).forEach(([key, t]) => {
    if (t.elderly) {
      easyRead.push([key, t]);
    } else {
      standard.push([key, t]);
    }
  });

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div
      className={`settings-overlay${open ? ' open' : ''}`}
      onClick={handleOverlayClick}
    >
      <div className="settings-panel">
        <div className="settings-header">
          <h3>Settings</h3>
          <button className="settings-close" onClick={onClose}>&times;</button>
        </div>
        <div className="settings-section">
          <div className="settings-section-title">Color Theme</div>
          <div className="theme-grid">
            {standard.map(([key, t]) => (
              <div
                key={key}
                className={`theme-option${currentTheme === key ? ' active' : ''}`}
                onClick={() => onSelectTheme(key)}
              >
                <div
                  className="theme-swatch"
                  style={{ background: t.bg_gradient || t.bg_color }}
                />
                <span className="theme-option-name">{t.name}</span>
              </div>
            ))}

            {easyRead.length > 0 && (
              <>
                <div className="theme-section-label">Easy Read</div>
                {easyRead.map(([key, t]) => (
                  <div
                    key={key}
                    className={`theme-option${currentTheme === key ? ' active' : ''}`}
                    onClick={() => onSelectTheme(key)}
                  >
                    <div
                      className="theme-swatch"
                      style={{ background: t.bg_gradient || t.bg_color }}
                    />
                    <span className="theme-option-name">{t.name}</span>
                  </div>
                ))}
              </>
            )}
          </div>
          <button className="theme-reset" onClick={onResetTheme}>Reset to Default</button>
        </div>
      </div>
    </div>
  );
}
