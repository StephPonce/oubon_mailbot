// 
// LAYOUT - Main application shell
// Wraps all authenticated pages with sidebar and header
// Includes Oi AI Assistant - The Brain of Ospra Intelligence
// NOW WITH: Context-aware Oi integration
// 

import { useState, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import { OiChatPanel, OiFloatingButton } from '../oi';
import { useOi, useDashboardContext } from '../../contexts/OiContext';

export default function Layout() {
  const location = useLocation();
  
  // Use Oi context for chat state
  const { isOiOpen, setIsOiOpen } = useOi();
  
  // Use dashboard context to register current page
  const { registerPage } = useDashboardContext();
  
  // Persist sidebar state in localStorage
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const saved = localStorage.getItem('sidebar-collapsed');
    return saved === 'true';
  });

  // Mobile sidebar state
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Save sidebar state
  useEffect(() => {
    localStorage.setItem('sidebar-collapsed', String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  // Register current page with Oi context
  useEffect(() => {
    // Extract page name from path
    const path = location.pathname;
    let pageName = 'overview';
    
    if (path === '/' || path === '') {
      pageName = 'overview';
    } else {
      // Remove leading slash and get first segment
      pageName = path.slice(1).split('/')[0] || 'overview';
    }
    
    // Register with Oi so it knows what page user is on
    registerPage(pageName);
    
  }, [location.pathname, registerPage]);

  // Keyboard shortcut is now handled in OiContext
  // But we can add Escape to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOiOpen) {
        setIsOiOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOiOpen, setIsOiOpen]);

  return (
    <div className="min-h-screen">
      {/* Background */}
      <div className="app-background" />
      
      {/* Sidebar */}
      <Sidebar 
        isCollapsed={sidebarCollapsed} 
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} 
      />
      
      {/* Header */}
      <Header sidebarCollapsed={sidebarCollapsed} />
      
      {/* Main content area */}
      <main 
        className={`
          min-h-screen pt-16
          transition-all duration-300 ease-in-out
          ${sidebarCollapsed ? 'pl-[72px]' : 'pl-[260px]'}
        `}
      >
        <div className="p-6">
          <Outlet />
        </div>
      </main>
      
      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black/60 z-30 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* 
          OI AI ASSISTANT - The Brain of Ospra Intelligence
          Now context-aware - knows what page you're on!
           */}
      
      {/* Floating Oi Button */}
      <OiFloatingButton 
        onClick={() => setIsOiOpen(true)} 
      />

      {/* Oi Chat Panel - Now uses OiContext for state */}
      <OiChatPanel 
        isOpen={isOiOpen} 
        onClose={() => setIsOiOpen(false)} 
      />
    </div>
  );
}
