# Mobile Experience

Survey Says is designed mobile-first for team players at the pub.

---

## Mobile Optimizations

### Layout
- Fixed header with team name and connection status
- Collapsible instructions (tap to expand/collapse)
- Full-width answer inputs with 44px touch targets
- Submit button always visible (not hidden behind keyboard)

### Real-Time Updates
- Auto-refresh polling every 5-10 seconds to detect round changes
- Connection status indicator (green dot = connected, grey = disconnected)
- "Are you still there?" idle check after 30 minutes

### Answer Handling
- Auto-save via localStorage (debounced 500ms) — survives phone sleep, app switch, page refresh
- Blank answer validation warning before submit
- Post-submit: persistent answer display so teams can see what they submitted

### Photo Scan (v2.0.5)
- Host can scan paper answer sheets from phone camera
- `/host/scan` shortcut URL for quick access
- Auto-submits scanned answers to scoring queue
- Mobile hosts auto-redirect to photo scan page

## QR Code System

- Team codes displayed as QR codes for easy joining
- QR points to join page with code pre-filled
- Codes use unambiguous characters (no O/0, I/1/l confusion)
- Fuzzy matching for manual code entry
