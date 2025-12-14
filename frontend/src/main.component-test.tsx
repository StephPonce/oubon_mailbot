import { StrictMode, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

// Import components one by one for testing
import Sidebar from './components/layout/Sidebar'
import Header from './components/layout/Header'
import StatsCard from './components/dashboard/StatsCard'
import { FiPackage } from 'react-icons/fi'

function ComponentTest() {
  const [testStage, setTestStage] = useState(1);

  return (
    <div className="p-8   min-h-screen">
      <h1 className="text-3xl font-bold mb-4 text-green-600">
        ✅ React + Tailwind Working!
      </h1>
      
      <div className="mb-8">
        <button 
          onClick={() => setTestStage(testStage + 1)}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Test Stage {testStage}
        </button>
      </div>

      {testStage >= 1 && (
        <div className="mb-4">
          <h2 className="text-xl font-bold mb-2">Stage 1: Icons</h2>
          <FiPackage size={32} className="text-blue-600" />
          <p className="text-green-600">✅ Icons working</p>
        </div>
      )}

      {testStage >= 2 && (
        <div className="mb-4">
          <h2 className="text-xl font-bold mb-2">Stage 2: StatsCard</h2>
          <StatsCard 
            title="Test Card" 
            value={100} 
            icon={FiPackage} 
            color="bg-blue-600" 
          />
          <p className="text-green-600">✅ StatsCard working</p>
        </div>
      )}

      {testStage >= 3 && (
        <div className="mb-4">
          <h2 className="text-xl font-bold mb-2">Stage 3: Header</h2>
          <Header />
          <p className="text-green-600">✅ Header working</p>
        </div>
      )}

      {testStage >= 4 && (
        <div className="mb-4">
          <h2 className="text-xl font-bold mb-2">Stage 4: Sidebar</h2>
          <div style={{ height: '200px', width: '300px' }}>
            <Sidebar activeView="dashboard" onViewChange={() => {}} />
          </div>
          <p className="text-green-600">✅ Sidebar working</p>
        </div>
      )}

      {testStage > 4 && (
        <div className="text-green-600 font-bold text-xl">
          🎉 ALL COMPONENTS WORKING! The issue is in App.tsx logic or data loading.
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ComponentTest />
  </StrictMode>,
)
