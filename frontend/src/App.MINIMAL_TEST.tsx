// MINIMAL TEST - If this works, React is fine
// If this fails, it's a build/config issue

export default function App() {
  return (
    <div style={{ 
      padding: '40px', 
      fontFamily: 'Arial', 
      textAlign: 'center',
      backgroundColor: '#f0f0f0',
      minHeight: '100vh'
    }}>
      <h1 style={{ color: '#2563EB', fontSize: '48px', marginBottom: '20px' }}>
        ✅ REACT IS WORKING!
      </h1>
      <p style={{ fontSize: '24px', color: '#666' }}>
        If you see this, React is rendering correctly.
      </p>
      <div style={{ 
        marginTop: '40px', 
        padding: '20px', 
        backgroundColor: 'white',
        borderRadius: '8px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
      }}>
        <p style={{ fontSize: '18px', color: '#333' }}>
          Next step: Restore full dashboard
        </p>
      </div>
    </div>
  );
}
