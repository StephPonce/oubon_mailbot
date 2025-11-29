# GEMINI.md

**Instructions for Gemini CLI - Frontend Development Only**

## 🚨 CRITICAL RULES - READ FIRST

**YOU ARE RESTRICTED TO FRONTEND DEVELOPMENT ONLY**

- **DO NOT** modify, read, or suggest changes to any backend Python files
- **DO NOT** modify any backend configuration files
- **DO NOT** touch database files or database-related code
- **DO NOT** modify API endpoints or routes
- **DO NOT** change environment variables or .env files
- **DO NOT** modify pyproject.toml, uv.lock, or Python dependencies

**ONLY work with frontend code in the `/frontend` directory.**

---

## ✅ ALLOWED: What You CAN Work On

### Frontend Directory Structure
```
frontend/
├── src/
│   ├── components/     ✅ React components
│   ├── pages/          ✅ Page components
│   ├── lib/            ✅ Utilities and helpers
│   ├── contexts/       ✅ React contexts
│   ├── types/          ✅ TypeScript types
│   ├── App.tsx         ✅ Main app component
│   ├── main.tsx        ✅ Entry point
│   └── index.css       ✅ Global styles
├── public/             ✅ Static assets
├── package.json        ✅ Frontend dependencies only
├── vite.config.ts      ✅ Vite configuration
├── tailwind.config.js  ✅ Tailwind styling
└── tsconfig.json       ✅ TypeScript config
```

### Your Responsibilities
1. **UI/UX Design**: Improve visual design, layouts, animations
2. **React Components**: Create, modify, refactor React components
3. **Styling**: Work with Tailwind CSS, custom CSS
4. **TypeScript**: Type definitions, interfaces for frontend
5. **State Management**: React hooks, context, client-side state
6. **Routing**: React Router configuration and navigation
7. **Client-side Logic**: Form validation, UI interactions
8. **Performance**: Code splitting, lazy loading, optimization
9. **Accessibility**: ARIA labels, keyboard navigation

---

## ❌ FORBIDDEN: What You MUST NOT Touch

### Backend Files (Absolutely Off-Limits)
```
❌ main.py                    (Legacy backend)
❌ ospra_os/                  (Backend application)
❌ app/                       (Backend modules)
❌ data/                      (Database and data files)
❌ .secrets/                  (Credentials)
❌ *.db                       (SQLite databases)
❌ pyproject.toml             (Python dependencies)
❌ uv.lock                    (Python lock file)
❌ .env                       (Environment variables)
❌ .env.example               (Environment template)
```

### Backend File Patterns to Avoid
- Any `.py` files outside `/frontend`
- Any files in `ospra_os/`, `app/`, `scripts/`
- Database files: `*.db`, `*.sqlite`
- Configuration: `.env`, `pyproject.toml`
- Credentials: `.secrets/`, `*token*`, `*credentials*`

---

## 🔌 Backend API Integration

### How to Work with Backend APIs

The backend is already running on `http://127.0.0.1:8001`. You can:

✅ **Use existing API endpoints** by making requests from frontend
✅ **Read** `/frontend/src/lib/api.ts` to understand available endpoints
✅ **Check** the backend API documentation at http://127.0.0.1:8001/docs (when server is running)

❌ **DO NOT** create or modify backend endpoints
❌ **DO NOT** change API response formats or data structures

### Example: Correct API Usage
```typescript
// ✅ GOOD: Using existing API from frontend
import axios from 'axios';

const response = await axios.get('http://127.0.0.1:8001/api/emails/list');
```

```python
# ❌ BAD: Modifying backend routes (DO NOT DO THIS)
@router.get("/api/emails/list")
def get_emails():
    # Don't touch this!
```

---

## 🎯 Your Focus Areas

### 1. Email Dashboard UI
- **File**: `/frontend/src/pages/EmailDashboard.tsx`
- Improve email list presentation
- Enhance email viewer interface
- Add filters, search, sorting
- Improve mobile responsiveness

### 2. Portfolio Dashboard
- **File**: `/frontend/src/pages/PortfolioDashboard.tsx`
- Enhance charts and visualizations
- Improve metrics display
- Add interactive elements

### 3. Products Page
- **File**: `/frontend/src/pages/ProductsPage.tsx`
- Improve product card design
- Add filtering and sorting UI
- Enhance product modal

### 4. Component Library
- **Directory**: `/frontend/src/components/`
- Create reusable UI components
- Improve existing components
- Ensure consistent styling

### 5. Design System
- Tailwind configuration
- Color schemes and themes
- Typography and spacing
- Component patterns

---

## 🛠️ Development Commands (Frontend Only)

### Running Frontend Dev Server
```bash
cd frontend
npm run dev          # Start development server
npm run build        # Build for production
npm run lint         # Lint code
npm run preview      # Preview production build
```

### Installing Frontend Dependencies
```bash
cd frontend
npm install <package-name>     # Add new frontend package
```

---

## 📋 Project Context

### Tech Stack (Frontend)
- **Framework**: React 18.3.1
- **Build Tool**: Vite 7.1.12
- **Language**: TypeScript 5.9.3
- **Styling**: Tailwind CSS 3.4.18
- **Routing**: React Router DOM 7.9.5
- **Charts**: Recharts 3.4.1
- **HTTP Client**: Axios 1.13.1
- **Icons**: Lucide React, React Icons

### Tech Stack (Backend - DO NOT MODIFY)
- Python 3.12
- FastAPI
- SQLite/PostgreSQL
- SQLAlchemy
- Google OAuth
- OpenAI Integration

### Application Architecture
```
┌─────────────────────────────────────┐
│  Frontend (React + Vite)           │ ← YOU WORK HERE
│  Port: 5173                         │
└──────────────┬──────────────────────┘
               │ HTTP Requests
               ↓
┌─────────────────────────────────────┐
│  Backend (FastAPI)                  │ ← DO NOT TOUCH
│  Port: 8001                         │
│  - OspraOS (ospra_os/main.py)      │
└─────────────────────────────────────┘
```

---

## 🚦 When to Ask for Help

### Ask User If:
1. You need a **new API endpoint** that doesn't exist
2. The **backend response format** needs to change
3. You encounter **CORS or connection issues**
4. **Environment variables** need to be added
5. **Backend behavior** needs modification

### Don't Ask, Just Do:
1. Frontend styling changes
2. Component refactoring
3. UI/UX improvements
4. TypeScript type definitions
5. Client-side logic and validation
6. React hooks and state management

---

## ✅ Checklist Before Making Changes

Before modifying any file, verify:

- [ ] File is inside `/frontend` directory
- [ ] File is NOT a `.py` file
- [ ] File is NOT in `ospra_os/`, `app/`, or `data/`
- [ ] Change is UI/UX related only
- [ ] No backend logic is being modified
- [ ] No API endpoints are being changed
- [ ] No database queries are being added

---

## 🎨 Design Guidelines

### Styling Approach
- Use **Tailwind CSS** utility classes first
- Follow existing color scheme:
  - Primary: `brand-blue` (#3B82F6)
  - Background: Dark theme (gray-900, gray-950)
  - Text: Light grays (gray-200, gray-300)
- Maintain glassmorphism effects for cards
- Keep consistent spacing and typography

### Component Patterns
- Use functional components with hooks
- Implement proper TypeScript types
- Follow existing component structure
- Keep components small and focused
- Use React.memo for performance when needed

---

## 📞 Communication Protocol

### When Referencing Files
Always use full paths from project root:
- ✅ `/frontend/src/components/EmailSettings.tsx`
- ❌ `EmailSettings.tsx`

### When Suggesting Changes
Focus on frontend improvements:
- ✅ "Let's improve the email list UI by adding filters"
- ❌ "Let's modify the API to return filtered emails"

### When Encountering Backend Issues
Report to user, don't fix:
- ✅ "The API is returning an error. User should check backend logs."
- ❌ "Let me fix the backend endpoint for you."

---

## 🔐 Security Notes

- **Never** expose or modify credentials
- **Never** hardcode API tokens in frontend
- **Never** commit sensitive data
- Use environment variables for configuration (user will set these)

---

## 📚 Additional Resources

- **Frontend Dev Server**: http://localhost:5173
- **Backend API Docs**: http://127.0.0.1:8001/docs (when running)
- **Vite Docs**: https://vitejs.dev
- **React Docs**: https://react.dev
- **Tailwind Docs**: https://tailwindcss.com

---

## ⚡ Quick Start

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies (if needed)
npm install

# 3. Start development server
npm run dev

# 4. Open browser to http://localhost:5173

# 5. Make your changes to files in /frontend/src/

# 6. Changes will hot-reload automatically
```

---

## 🤖 Gemini CLI Optimization Guide

### Efficient File Reading Strategy

**Always read these files first to understand context:**
1. `/frontend/src/lib/api.ts` - Available API endpoints
2. `/frontend/src/types/index.ts` - Type definitions
3. The specific component you're working on
4. Related components in the same directory

**Don't waste time reading:**
- Backend `.py` files (you can't modify them anyway)
- `node_modules/` (dependencies)
- Build artifacts (`dist/`, `.vite/`)
- Large data files

**Example Efficient Workflow:**
```bash
# Read API types first
Read /frontend/src/lib/api.ts

# Read component you're modifying
Read /frontend/src/pages/EmailDashboard.tsx

# Read related components if needed
Read /frontend/src/components/EmailSettingsModal.tsx

# Make changes
Edit /frontend/src/pages/EmailDashboard.tsx
```

---

## 📝 Prompt Templates for Common Tasks

### Creating a New Component
```
Create a new React component at /frontend/src/components/[ComponentName].tsx
Requirements:
- TypeScript with proper types
- Tailwind CSS styling matching existing dark theme
- Lucide React icons if needed
- Props interface defined
- Export as default
```

### Improving Existing UI
```
Improve the UI of /frontend/src/pages/[PageName].tsx:
- Better spacing and alignment
- Responsive design for mobile
- Smoother animations/transitions
- Accessibility improvements (ARIA labels)
- Keep existing functionality intact
```

### Adding a New Feature
```
Add [feature description] to /frontend/src/pages/[PageName].tsx:
- Use existing API endpoint: [endpoint]
- Add loading states
- Handle errors gracefully
- Update TypeScript types if needed
- Match existing design patterns
```

### Fixing Bugs
```
Fix the issue in /frontend/src/components/[ComponentName].tsx where [description]:
- Debug the problem
- Implement the fix
- Ensure no breaking changes
- Test edge cases
```

---

## 🎯 Task-Specific Workflows

### Workflow 1: Adding a Filter to a List
```bash
# 1. Read the page component
Read /frontend/src/pages/[PageName].tsx

# 2. Add filter state
- Add useState for filter value
- Create filter UI (dropdown/input)
- Apply filter to data array

# 3. Style with Tailwind
- Use existing design patterns
- Maintain dark theme

# 4. Verify it works
- Check browser console for errors
- Test different filter values
```

### Workflow 2: Creating a Modal
```bash
# 1. Check existing modal patterns
Read /frontend/src/components/EmailSettingsModal.tsx

# 2. Create new modal component
- Copy structure from existing modal
- Customize content
- Add open/close state management

# 3. Integrate into parent component
- Import modal
- Add state for isOpen
- Add trigger button

# 4. Test
- Verify open/close works
- Check backdrop click closes modal
- Test keyboard navigation (ESC key)
```

### Workflow 3: Improving Chart Visualization
```bash
# 1. Read chart component
Read /frontend/src/components/portfolio/RevenueChart.tsx

# 2. Review Recharts docs for enhancement ideas

# 3. Implement improvements:
- Better colors matching theme
- Tooltips with more info
- Animations
- Responsive sizing

# 4. Test with different data scenarios
```

---

## 🔍 Context Management for AI Efficiency

### What to Include in Your Context

**Always maintain awareness of:**
1. **Current file structure** - Know where you are
2. **Component dependencies** - What imports what
3. **Existing patterns** - Follow established conventions
4. **Type definitions** - Ensure type safety
5. **API contracts** - Don't assume endpoint responses

### How to Stay Focused

**For each task:**
1. ✅ Read only relevant files (2-5 max)
2. ✅ Focus on one component at a time
3. ✅ Complete one feature before starting another
4. ✅ Use existing patterns instead of inventing new ones
5. ✅ Test changes immediately

**Avoid:**
1. ❌ Reading entire codebase before starting
2. ❌ Making changes to multiple unrelated files
3. ❌ Reinventing existing components
4. ❌ Over-engineering simple tasks

---

## ✅ Verification Checklist

After making changes, verify:

### Visual Check
- [ ] Component renders without errors
- [ ] Styling matches design system
- [ ] Responsive on different screen sizes
- [ ] Dark theme colors are correct
- [ ] Icons and images load properly

### Functional Check
- [ ] All interactions work (clicks, hovers, inputs)
- [ ] Forms validate correctly
- [ ] API calls succeed
- [ ] Loading states display
- [ ] Error handling works

### Code Quality Check
- [ ] No TypeScript errors
- [ ] No console errors in browser
- [ ] No unused imports
- [ ] Proper prop types defined
- [ ] Code follows existing patterns

### Testing Commands
```bash
# Check for TypeScript errors
cd frontend && npx tsc --noEmit

# Check for lint errors
cd frontend && npm run lint

# Build to catch any issues
cd frontend && npm run build
```

---

## 🚀 Performance Best Practices

### Component Optimization
```typescript
// Use React.memo for expensive renders
import { memo } from 'react';

const ExpensiveComponent = memo(({ data }) => {
  return <div>{/* ... */}</div>;
});

// Use useMemo for expensive calculations
const filteredData = useMemo(() => {
  return data.filter(item => item.active);
}, [data]);

// Use useCallback for stable function references
const handleClick = useCallback(() => {
  // handler logic
}, [dependency]);
```

### Lazy Loading
```typescript
// Already implemented in main.tsx, use same pattern
const NewPage = lazy(() => import('./pages/NewPage'));
```

### Image Optimization
- Use appropriate image sizes
- Consider lazy loading images
- Use modern formats (WebP) when possible

---

## 🐛 Common Issues & Solutions

### Issue: TypeScript Errors
```typescript
// ❌ BAD: Using 'any'
const data: any = fetchData();

// ✅ GOOD: Proper typing
interface DataType {
  id: number;
  name: string;
}
const data: DataType[] = await fetchData();
```

### Issue: API Call Failing
```typescript
// Always handle errors
try {
  const response = await axios.get('http://127.0.0.1:8001/api/endpoint');
  setData(response.data);
} catch (error) {
  console.error('Failed to fetch:', error);
  setError('Failed to load data');
}
```

### Issue: Component Not Re-rendering
```typescript
// Make sure dependencies are correct
useEffect(() => {
  fetchData();
}, [dependency]); // ← Add all dependencies

// Use functional setState for state based on previous state
setCount(prev => prev + 1);
```

### Issue: Styling Not Applied
```typescript
// Ensure Tailwind classes are not dynamic strings
// ❌ BAD:
className={`text-${color}-500`} // Won't work with Tailwind

// ✅ GOOD:
className={color === 'blue' ? 'text-blue-500' : 'text-red-500'}
```

---

## 🗺️ Component Architecture Reference

### Page Components (High Level)
```
/frontend/src/pages/
├── PortfolioDashboard.tsx    (Dashboard with charts)
├── ProductsPage.tsx           (Product listings)
├── OrdersPage.tsx             (Order management)
├── EmailDashboard.tsx         (Email interface)
├── AnalyticsPage.tsx          (Analytics views)
└── LiveTrendsPage.tsx         (Trend monitoring)
```

### Reusable Components
```
/frontend/src/components/
├── Layout.tsx                 (Main app layout)
├── EmailSettings.tsx          (Email config)
├── ProductCard.tsx            (Product display)
├── ProductModal.tsx           (Product details)
├── AIChat.tsx                 (Chat interface)
├── GlobalAIChat.tsx           (Global chat overlay)
└── NotificationBell.tsx       (Notification icon)
```

### Utilities
```
/frontend/src/lib/
├── api.ts                     (API client & endpoints)
└── mockData.ts                (Sample data)
```

### State Management
```
/frontend/src/contexts/
└── AIChatContext.tsx          (AI chat state)
```

---

## 🔄 Working with Existing Components

### Before Modifying a Component

1. **Read the component file completely**
2. **Understand its props and state**
3. **Note what API endpoints it uses**
4. **Check where it's imported/used**
5. **Review related TypeScript types**

### Example Analysis
```typescript
// Reading EmailDashboard.tsx, note:
// 1. State management pattern (useState, useEffect)
// 2. API endpoints used (emails/stats, emails/list)
// 3. Props passed to child components
// 4. Styling patterns (Tailwind classes)
// 5. Event handlers and their logic
```

### Safe Modification Pattern
```typescript
// 1. Keep existing functionality
// 2. Add new features incrementally
// 3. Test after each change
// 4. Don't remove code you don't understand

// Example: Adding a filter
// ✅ Add new state without removing old code
const [filter, setFilter] = useState('all');
const [existingState, setExistingState] = useState(/* ... */);

// ✅ Filter data without changing original array
const filteredEmails = useMemo(() => {
  return allEmails.filter(/* filter logic */);
}, [allEmails, filter]);
```

---

## 📊 API Endpoint Reference

### Available Endpoints (Read-Only Knowledge)

**Portfolio API:**
- `GET /api/portfolio/overview` - Portfolio stats
- `GET /api/portfolio/rankings` - Store rankings

**Email API:**
- `GET /api/emails/stats/summary?user_id=1` - Email statistics
- `GET /api/emails/list?user_id=1&limit=200&label=INBOX` - Email list
- `POST /api/emails/sync?user_id=1&account_id=1` - Sync emails
- `GET /api/emails/{id}?user_id=1` - Email details
- `POST /api/emails/{id}/mark-read` - Mark as read
- `POST /api/emails/{id}/star` - Star email
- `POST /api/emails/send` - Send email

**Products API:**
- `GET /api/dashboard/v2/niches` - Available niches
- `GET /api/dashboard/v2/products?niche=X&page=1` - Product list
- `GET /api/dashboard/v2/overview?niche=X` - Overview stats

**Note:** All endpoints return JSON. Check `/frontend/src/lib/api.ts` for implementation.

---

## 💡 Pro Tips for Gemini CLI

### Tip 1: Use Incremental Changes
Make small changes and verify they work before moving to the next feature.

### Tip 2: Follow Existing Patterns
Don't reinvent. Copy patterns from existing components:
```bash
# Find similar component
Read /frontend/src/components/EmailSettingsModal.tsx

# Copy structure, modify content
# This is faster and more consistent
```

### Tip 3: Test in Browser Immediately
After each change, check http://localhost:5173 to verify it works.

### Tip 4: Use TypeScript to Your Advantage
Let TypeScript guide you - if types don't match, there's likely an issue.

### Tip 5: Read Error Messages Carefully
Browser console and terminal errors tell you exactly what's wrong.

### Tip 6: Maintain Consistency
Match existing code style, naming conventions, and file organization.

### Tip 7: Document Complex Logic
Add comments for non-obvious code:
```typescript
// Calculate weighted average for portfolio performance
// Weight = store revenue / total revenue
const weightedAvg = stores.reduce((acc, store) => {
  const weight = store.revenue / totalRevenue;
  return acc + (store.performance * weight);
}, 0);
```

---

## 🎓 Learning Resources

### Understanding the Codebase
1. Start with `/frontend/src/main.tsx` - Entry point
2. Read `/frontend/src/App.tsx` - App wrapper
3. Review `/frontend/src/components/Layout.tsx` - Main layout
4. Explore individual page components

### TypeScript Patterns in Use
```typescript
// Interface for props
interface ComponentProps {
  title: string;
  count?: number; // Optional
  onUpdate: (id: number) => void; // Function type
}

// Type for state
type LoadingState = 'idle' | 'loading' | 'success' | 'error';

// Generic type usage
interface ApiResponse<T> {
  data: T;
  status: number;
}
```

### Tailwind Patterns in Use
```typescript
// Dark theme utilities
bg-gray-900/50         // Semi-transparent background
backdrop-blur-lg       // Glassmorphism effect
border-gray-800        // Subtle borders
text-gray-200          // Light text on dark bg

// Interactive states
hover:bg-glass-white   // Hover effect
transition            // Smooth transitions
focus:outline-none    // Clean focus
focus:ring-2          // Accessible focus ring
focus:ring-brand-blue // Branded focus color
```

---

## 🔧 Debugging Workflow

### When Something Doesn't Work

**Step 1: Check Browser Console**
```bash
# Open DevTools: F12 or Cmd+Option+I
# Look for:
# - Red error messages
# - Yellow warnings
# - Network failures (Network tab)
```

**Step 2: Check Terminal**
```bash
# Look for:
# - TypeScript errors
# - Build errors
# - Vite warnings
```

**Step 3: Isolate the Issue**
```typescript
// Add console.logs to debug
console.log('Data received:', data);
console.log('State value:', stateVariable);

// Check if component renders
console.log('Component mounted');
```

**Step 4: Verify API Response**
```bash
# Test endpoint directly
curl http://127.0.0.1:8001/api/endpoint

# Check Network tab in DevTools
# - Status code (should be 200)
# - Response data format
# - Request headers
```

**Step 5: Fix and Test**
- Make targeted fix
- Verify in browser
- Remove debug logs
- Test related functionality

---

## 📦 Managing Dependencies

### Adding New npm Packages

**Before adding a package, check if you can:**
1. Use existing dependencies
2. Implement with vanilla JS/React
3. Use Tailwind CSS instead of UI library

**If you must add a package:**
```bash
cd frontend

# Check if it's already installed
npm list <package-name>

# Install
npm install <package-name>

# For TypeScript types
npm install --save-dev @types/<package-name>
```

**Prefer lightweight packages:**
- ✅ Use lucide-react (already installed) for icons
- ✅ Use Tailwind for styling
- ✅ Use Recharts (already installed) for charts
- ❌ Avoid heavy UI libraries (Material-UI, Ant Design)
- ❌ Avoid duplicate icon libraries

---

## 🎯 Quick Reference: File Paths

### Common Files You'll Edit
```
Frontend Components:
/frontend/src/pages/EmailDashboard.tsx
/frontend/src/pages/PortfolioDashboard.tsx
/frontend/src/pages/ProductsPage.tsx
/frontend/src/pages/OrdersPage.tsx
/frontend/src/pages/AnalyticsPage.tsx
/frontend/src/components/Layout.tsx
/frontend/src/components/[AnyComponent].tsx

Frontend Utilities:
/frontend/src/lib/api.ts
/frontend/src/types/index.ts
/frontend/src/contexts/AIChatContext.tsx

Frontend Config:
/frontend/package.json
/frontend/vite.config.ts
/frontend/tailwind.config.js
/frontend/tsconfig.json
/frontend/src/index.css
```

### Files You'll Read (But Not Modify)
```
Backend Reference Only:
CLAUDE.md (backend context - read for API understanding)
/frontend/src/lib/api.ts (API endpoints reference)
```

### Files to Never Touch
```
Backend Code:
main.py
ospra_os/**/*.py
app/**/*.py

Backend Config:
.env
pyproject.toml
uv.lock

Data:
*.db
data/**/*
.secrets/**/*
```

---

**Remember: You are the frontend specialist. Backend is not your concern. Focus on making the UI beautiful, responsive, and delightful to use!**

---

## 🎬 Final Checklist for Every Task

Before saying you're done:

- [ ] ✅ Changes are in `/frontend` directory only
- [ ] ✅ No backend files were modified
- [ ] ✅ Component renders without errors
- [ ] ✅ TypeScript types are correct
- [ ] ✅ Styling matches dark theme
- [ ] ✅ Tested in browser at http://localhost:5173
- [ ] ✅ No console errors
- [ ] ✅ Responsive design works
- [ ] ✅ Follows existing code patterns
- [ ] ✅ Code is clean and commented if needed

**When in doubt, ask the user before proceeding!**
