# 🦅 Ospra Intelligence - Frontend

Liquid glass aesthetic dashboard for AI-powered e-commerce automation.

## 🚀 Quick Start

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev

# Open in browser
open http://localhost:5173
```

## 📦 Features

### Pages

| Route | Component | Description |
|-------|-----------|-------------|
| `/login` | LoginForm | Authentication |
| `/register` | RegisterForm | New account creation |
| `/dashboard` | Dashboard | Main command center |
| `/oi` | OiChat | AI chat interface |
| `/products` | ProductDiscovery | Product search & deploy |
| `/autopilot` | AutopilotControl | Automation settings |
| `/actions` | ActionQueue | AI action review |
| `/settings` | Settings | Account management |

### Authentication

- JWT-based authentication
- Automatic token refresh
- Tier-based access control
- Protected routes

### Key Components

- **AuthProvider** - Wraps app with auth state
- **ProtectedRoute** - Route protection
- **useAuth()** - Auth state hook
- **authService** - API authentication

## 🔧 Configuration

Create `.env` in frontend root:

```env
VITE_API_URL=http://localhost:8000
```

For production:

```env
VITE_API_URL=https://api.ospra.io
```

## 🎨 Design System

### Colors

| Name | Value | Usage |
|------|-------|-------|
| Purple | `#8b5cf6` | Primary accent |
| Cyan | `#06b6d4` | Secondary accent |
| Dark | `#0f172a` | Background |

### Components

All components use the liquid glass aesthetic:

```jsx
// Glass card
<div className="backdrop-blur-xl bg-white/5 rounded-2xl border border-white/10 p-6">
  {/* Content */}
</div>

// Gradient button
<button className="px-6 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white font-semibold">
  Action
</button>
```

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── auth/
│   │   │   ├── LoginForm.jsx
│   │   │   ├── RegisterForm.jsx
│   │   │   └── ProtectedRoute.jsx
│   │   ├── Dashboard.jsx
│   │   ├── OiChat.jsx
│   │   ├── ProductDiscovery.jsx
│   │   ├── AutopilotControl.jsx
│   │   ├── ActionQueue.jsx
│   │   └── Settings.jsx
│   ├── hooks/
│   │   └── useAuth.jsx
│   ├── services/
│   │   ├── auth.js
│   │   └── api.js
│   ├── App.jsx
│   ├── main.jsx
│   └── index.css
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

## 🔌 API Integration

The frontend connects to these backend endpoints:

### Authentication
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`

### OI Chat
- `POST /api/ai/chat`
- `POST /api/nl/parse`
- `GET /api/nl/examples`

### Products
- `GET /api/products/discover`
- `GET /api/products/trending`
- `POST /api/products/search`
- `POST /api/deploy/product`

### Autopilot
- `GET /api/autopilot/status`
- `GET /api/autopilot/config`
- `POST /api/autopilot/enable`
- `POST /api/autopilot/disable`
- `POST /api/autopilot/presets/{preset}`

### Actions
- `GET /api/ai/actions`
- `POST /api/ai/actions/{id}/accept`
- `POST /api/ai/actions/{id}/decline`

## 🚢 Deployment

### Build for Production

```bash
npm run build
```

Output in `dist/` folder.

### Deploy to Vercel

```bash
vercel deploy --prod
```

### Environment Variables

Set `VITE_API_URL` in Vercel dashboard.

## 🛠️ Development

### Prerequisites

- Node.js 18+
- Backend running on port 8000

### Commands

```bash
npm run dev      # Start dev server
npm run build    # Build for production
npm run preview  # Preview production build
npm run lint     # Run ESLint
```

---

Made with 🧠 by Ospra Intelligence
