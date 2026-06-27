# Parkinox Operator — Beta (Electron)

A standalone **Electron** rebuild of the Parkinox parking **operator** dashboard
(`parkinox_op`, Flutter). It is a faithful **1:1** reproduction of the original
screens with a refined, more polished UI — same dark "Stockholm" palette, same
RTL Persian layout, same Iranian-plate rendering, same flows.

> This app lives **alongside** the original project and does not modify any
> existing code. It only **inspected** the Flutter app and Django/parking models
> for reference. It runs fully standalone on **mock data** (no backend required).

## What's included

| Screen | Parity with Flutter app |
| --- | --- |
| **Login** | Operator profile cards + 6-digit superuser PIN (demo PIN: `123456`) |
| **Dashboard** | Top toolbar (clock + Shamsi date, service-health pills, operator chip), 4-card stats bar, parked-vehicles panel (with همه/ثبت‌شده/مهمان filters), dual camera panels (entry/exit, on/off), live plate-detection approval panel with countdown ring, unpaid-sessions panel (نقدی / بخشش) |
| **Settings** | Server, cameras, rate-config and auto-detection sections |
| **Archive** | Gate-event log with entry/exit filtering |

### Beta UI refinements over the original
- Layered gradient background + glassmorphism on cards/dialogs
- Smooth motion (rise/fade transitions, pulsing detection glow, animated countdown ring)
- SVG corner brackets + animated LIVE badge on camera feeds
- On-screen keypad for PIN entry (plus physical keyboard support)

## Run

```bash
cd Parkinox_Beta_electron
npm install
npm start
```

`npm run dev` opens DevTools.

## Architecture

```
src/
├── main.js            # Electron main process (BrowserWindow)
├── preload.js         # contextIsolated bridge (seam for real backend wiring)
└── renderer/
    ├── index.html
    ├── styles/        # theme.css (tokens from app_colors/text_styles) + app.css
    └── js/
        ├── app.js     # tiny view router
        ├── store.js   # mock state mirroring backend models
        ├── util.js    # Persian numerals, Jalali date, plate renderer, toasts
        ├── icons.js   # inline SVG icon set
        └── views/     # login · dashboard · settings · archive
```

Vanilla JS + a small `h()` DOM helper — no build step. Vazirmatn font is loaded
from a CDN; the design tokens are mapped directly from the Flutter theme so visual
changes stay in sync conceptually.

### Wiring a real backend later
`store.js` is the single source of truth and `preload.js` is the privileged seam.
Replace the mock arrays in `store.js` with calls to the Django REST API
(`/api/parking/…`) and a WebSocket for live detections via `window.parkinox`.
