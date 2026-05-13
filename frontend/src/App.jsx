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

import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { AuthProvider } from './hooks/useAuth';
import { SidebarProvider } from './hooks/useSidebar';
import { DashboardProvider } from './hooks/useDashboardContext';
import { LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm, ProtectedRoute, PublicOnlyRoute } from './components/auth';
import Dashboard from './components/Dashboard';
// Task #35 — lazy-load the heavy route components. ProductDiscovery alone is
// ~3.2k lines (Score Breakdown, image gallery, ai chat panel, etc) and was
// dragging the main bundle every user paid for, whether they ever clicked
// Products or not. Lazy-loading defers its parse cost to the first visit to
// that route. Suspense fallback below paints a centered spinner so the
// hand-off is invisible to the user on a warm cache.
const ProductDiscovery = lazy(() => import('./components/ProductDiscovery'));
const AutopilotControl = lazy(() => import('./components/AutopilotControl'));
const ActionQueue = lazy(() => import('./components/ActionQueue'));
const Settings = lazy(() => import('./components/Settings'));
const Stores = lazy(() => import('./components/Stores'));

// Suspense fallback used by every lazy route. Centered spinner with the
// glassmorphism look the rest of the app uses, so the lazy hand-off
// doesn't visually flash. Defined once so it's not re-created per render.
const RouteFallback = () => (
  <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-950 via-purple-950 to-slate-950">
    <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
  </div>
);

/**
 * AppRoutes - Wrapped in DashboardProvider for Oi context
 * DashboardProvider needs to be inside BrowserRouter (uses useLocation)
 */
function AppRoutes() {
  return (
    <DashboardProvider>
      {/* Suspense boundary covers every lazy route below (Products,
          Autopilot, Actions, Settings, Stores). Eager routes (login,
          register, dashboard) render synchronously and never hit the
          fallback. */}
      <Suspense fallback={<RouteFallback />}>
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
        <Route
          path="/settings/stores"
          element={
            <ProtectedRoute>
              <Stores />
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
      </Suspense>
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
