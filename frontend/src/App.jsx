/**
 * OSPRA INTELLIGENCE - MAIN APP
 * ==============================
 * 
 * Root application component with routing.
 * Includes DashboardProvider for universal Oi context.
 * 
 * @author OspraOS
 * @date December 2024 (Updated January 2026 - Added forgot password)
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './hooks/useAuth';
import { SidebarProvider } from './hooks/useSidebar';
import { DashboardProvider } from './hooks/useDashboardContext';
import { LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm, ProtectedRoute, PublicOnlyRoute } from './components/auth';
import Dashboard from './components/Dashboard';
import ProductDiscovery from './components/ProductDiscovery';
import AutopilotControl from './components/AutopilotControl';
import ActionQueue from './components/ActionQueue';
import Settings from './components/Settings';

/**
 * AppRoutes - Wrapped in DashboardProvider for Oi context
 * DashboardProvider needs to be inside BrowserRouter (uses useLocation)
 */
function AppRoutes() {
  return (
    <DashboardProvider>
      <Routes>
        {/* Public routes */}
        <Route 
          path="/login" 
          element={
            <PublicOnlyRoute>
              <LoginForm />
            </PublicOnlyRoute>
          } 
        />
        <Route 
          path="/register" 
          element={
            <PublicOnlyRoute>
              <RegisterForm />
            </PublicOnlyRoute>
          } 
        />
        <Route 
          path="/forgot-password" 
          element={
            <PublicOnlyRoute>
              <ForgotPasswordForm />
            </PublicOnlyRoute>
          } 
        />
        <Route 
          path="/reset-password" 
          element={
            <PublicOnlyRoute>
              <ResetPasswordForm />
            </PublicOnlyRoute>
          } 
        />
        
        {/* Protected routes */}
        <Route 
          path="/dashboard" 
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/products" 
          element={
            <ProtectedRoute>
              <ProductDiscovery />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/autopilot" 
          element={
            <ProtectedRoute>
              <AutopilotControl />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/actions" 
          element={
            <ProtectedRoute>
              <ActionQueue />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/settings" 
          element={
            <ProtectedRoute>
              <Settings />
            </ProtectedRoute>
          } 
        />
        
        {/* Premium routes (require higher tier) */}
        <Route 
          path="/bulk-deploy" 
          element={
            <ProtectedRoute requiredTier="flight">
              <Dashboard />
            </ProtectedRoute>
          } 
        />
        
        {/* Redirect /oi to dashboard (chat is now floating) */}
        <Route path="/oi" element={<Navigate to="/dashboard" replace />} />
        
        {/* Default redirect */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </DashboardProvider>
  );
}

function App() {
  return (
    <AuthProvider>
      <SidebarProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </SidebarProvider>
    </AuthProvider>
  );
}

export default App;
