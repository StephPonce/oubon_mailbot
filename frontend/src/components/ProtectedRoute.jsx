//
// PROTECTED ROUTE & PUBLIC ONLY ROUTE
// Auth-based route guards
//
// Migrated from ProtectedRoute.tsx during Task #35 frontend cleanup —
// the rest of the app is plain JSX and this was the only .tsx file
// the JSX side still relied on (`components/auth/index.js` re-exports
// from here).

import { Navigate, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

// Protected Route - redirects to login if not authenticated
export function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  // Show loading while checking auth
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="app-background" />
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-accent mx-auto mb-4" />
          <p className="text-secondary text-sm">Loading...</p>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

// Public Only Route - redirects to dashboard if already authenticated
export function PublicOnlyRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="app-background" />
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-accent mx-auto mb-4" />
          <p className="text-secondary text-sm">Loading...</p>
        </div>
      </div>
    );
  }

  // Redirect to dashboard if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/products" replace />;
  }

  return <>{children}</>;
}

// Default export for backward compatibility
export default ProtectedRoute;
