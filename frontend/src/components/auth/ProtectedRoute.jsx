/**
 * OSPRA INTELLIGENCE - PROTECTED ROUTE COMPONENT
 * ===============================================
 * 
 * Route wrapper that requires authentication and/or specific tier.
 * 
 * Usage:
 *   <Route path="/dashboard" element={
 *     <ProtectedRoute>
 *       <Dashboard />
 *     </ProtectedRoute>
 *   } />
 * 
 *   <Route path="/premium" element={
 *     <ProtectedRoute requiredTier="soar">
 *       <PremiumFeature />
 *     </ProtectedRoute>
 *   } />
 * 
 * @author OspraOS
 * @date December 2024
 */

import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';


/**
 * Loading spinner component
 */
function LoadingSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500/20 to-cyan-500/20 border border-white/10 mb-4">
          <svg className="animate-spin h-8 w-8 text-purple-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        </div>
        <p className="text-white/60">Loading...</p>
      </div>
    </div>
  );
}


/**
 * Upgrade required component
 */
function UpgradeRequired({ requiredTier, currentTier }) {
  const tierNames = {
    nest: 'Nest',
    flight: 'Flight',
    soar: 'Soar',
    stratosphere: 'Stratosphere',
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="backdrop-blur-xl bg-white/10 rounded-3xl shadow-2xl border border-white/20 p-8 max-w-md mx-4 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-yellow-500/20 to-orange-500/20 border border-yellow-500/30 mb-4">
          <span className="text-3xl">[LOCKED]</span>
        </div>
        
        <h1 className="text-2xl font-bold text-white mb-2">Upgrade Required</h1>
        
        <p className="text-white/60 mb-6">
          This feature requires <span className="text-purple-400 font-semibold">{tierNames[requiredTier]}</span> tier or higher.
          You're currently on <span className="text-white/80 font-semibold">{tierNames[currentTier]}</span>.
        </p>

        <a
          href="/upgrade"
          className="inline-block py-3 px-6 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white font-semibold hover:from-purple-500 hover:to-cyan-500 transition-all transform hover:scale-[1.02]"
        >
          Upgrade Now
        </a>

        <a
          href="/dashboard"
          className="block mt-4 text-white/60 hover:text-white/80 transition-colors"
        >
          ← Back to Dashboard
        </a>
      </div>
    </div>
  );
}


/**
 * Protected Route Component
 * 
 * Props:
 *   - children: React components to render if authenticated
 *   - requiredTier: Minimum tier required (optional)
 *   - redirectTo: Where to redirect if not authenticated (default: /login)
 */
export function ProtectedRoute({ 
  children, 
  requiredTier = null,
  redirectTo = '/login',
}) {
  const { isAuthenticated, user, loading, hasTier } = useAuth();
  const location = useLocation();

  // Show loading while checking auth
  if (loading) {
    return <LoadingSpinner />;
  }

  // Not authenticated - redirect to login
  if (!isAuthenticated) {
    return <Navigate to={redirectTo} state={{ from: location.pathname }} replace />;
  }

  // Check tier if required
  if (requiredTier && !hasTier(requiredTier)) {
    return <UpgradeRequired requiredTier={requiredTier} currentTier={user?.tier} />;
  }

  // Authenticated and has required tier - render children
  return children;
}


/**
 * Public Only Route Component
 * 
 * Redirects authenticated users away (e.g., from login page)
 */
export function PublicOnlyRoute({ children, redirectTo = '/dashboard' }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <LoadingSpinner />;
  }

  if (isAuthenticated) {
    return <Navigate to={redirectTo} replace />;
  }

  return children;
}


export default ProtectedRoute;
