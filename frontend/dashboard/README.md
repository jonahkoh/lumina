# Carekiki MET Dashboard

WhatsApp-native MET (Medical Escort Transport) coordination tool, built for the Open Government Product hackathon.

## Quickstart

```bash
npm install
npm run dev
```

Open http://localhost:5173 — Vite will probably open it for you.

## What's inside

- **Admin Dashboard** — read-only operational view for MET providers. Gantt-style schedule timeline with drivers and escorts, area filter, status legend.
- **Driver / Escort view** — identity-scoped view with Pending Requests + Current Booking tabs. Accept/Reject actions with reason capture, "I am 10 mins away" caregiver notification.

Switch between views using the top-of-page tabs.

## API integration

The dashboard hits these endpoints (configurable in `src/Dashboard.jsx` near the top):

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/transport/dashboard` | Provider's full operational view (admin) |
| POST | `/transport/my-bookings` | Driver/escort's pending + current bookings |
| POST | `/engine/accept` | Accept a pending booking |
| POST | `/engine/reject` | Decline + procure next-best match |
| POST | `/engine/notify-arrival` | "10 mins away" caregiver ping |

Set `API_BASE` to point at your backend (e.g. `http://localhost:8000`). Mock fallback runs when endpoints are unreachable, so the UI is fully demo-able without a backend.

Reads go through MET Transport, writes go through MET Engine — matches the architecture (Engine ↔ Kafka ↔ Transport).

## Stack

- React 18
- Vite (dev server + bundler)
- Tailwind CSS (utility classes)
- lucide-react (icons)
- Custom CSS-in-JSX for typography, colors, animations (warm operational aesthetic, Fraunces serif + Manrope sans + JetBrains Mono)

## Build for production

```bash
npm run build      # outputs to dist/
npm run preview    # serves the production build locally
```

## File structure

```
carekiki-dashboard/
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── index.html
└── src/
    ├── main.jsx       # entry point
    ├── index.css      # Tailwind directives
    └── Dashboard.jsx  # the entire dashboard (admin + driver/escort views)
```

The dashboard is a single self-contained file. Future refactor: split into separate components per view, lift state to context or a simple store, extract the API layer.
