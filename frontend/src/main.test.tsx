import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

// MINIMAL TEST APP
function TestApp() {
  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <h1 style={{ color: 'green' }}>✅ REACT IS WORKING!</h1>
      <p>If you see this, React is rendering correctly.</p>
      <p>The issue is in one of your components.</p>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TestApp />
  </StrictMode>,
)
