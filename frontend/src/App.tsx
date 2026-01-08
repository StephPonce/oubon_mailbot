// 
// APP - Root component with routing
// Uses Layout component for authenticated pages
// 

import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import { Layout } from './components/layout';

// Auth Pages
import Login from './pages/Login';
import Register from './pages/Register';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';

// App Pages
import Overview from './pages/Overview';
import Products from './pages/Products';
import Ads from './pages/Ads';
import Emails from './pages/Emails';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';

export default function App() {
  const { isAuthenticated, isLoading } = useAuth();

  return (
    <Routes>
      {/* 
          PUBLIC ROUTES (Auth Pages)
           */}
      
      {/* Login - Redirect to dashboard if already authenticated */}
      <Route 
        path="/login" 
        element={
          !isLoading && isAuthenticated ? (
            <Navigate to="/" replace />
          ) : (
            <Login />
          )
        } 
      />
      
      {/* Register - Redirect to dashboard if already authenticated */}
      <Route 
        path="/register" 
        element={
          !isLoading && isAuthenticated ? (
            <Navigate to="/" replace />
          ) : (
            <Register />
          )
        } 
      />
      
      {/* Forgot Password */}
      <Route 
        path="/forgot-password" 
        element={<ForgotPassword />} 
      />
      
      {/* Reset Password (with token) */}
      <Route 
        path="/reset-password" 
        element={<ResetPassword />} 
      />

      {/* 
          PROTECTED ROUTES (Require Auth)
          Wrapped in Layout component with sidebar/header
           */}
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        {/* Overview - Main dashboard / Oi's command center */}
        <Route index element={<Overview />} />
        
        {/* Products - Discovery & management */}
        <Route path="products" element={<Products />} />
        
        {/* Ads - Campaign management */}
        <Route path="ads" element={<Ads />} />
        
        {/* Emails - Automation & support */}
        <Route path="emails" element={<Emails />} />
        
        {/* Analytics - Deep metrics */}
        <Route path="analytics" element={<Analytics />} />
        
        {/* Settings - Configuration */}
        <Route path="settings" element={<Settings />} />
      </Route>

      {/* 
          CATCH ALL - Redirect to dashboard
           */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
