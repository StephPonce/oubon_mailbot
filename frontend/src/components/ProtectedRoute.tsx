/**
 * Protected Route Component
 * =========================
 * 
 * Wraps routes that require authentication.
 * Redirects to login if not authenticated.
 */

import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Loader2 } from 'lucide-react';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireTier?: 'nest' | 'flight' | 'soar' | 'stratosphere';
}

export function ProtectedRoute({ children, requireTier }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  // Show loading spinner while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500 mx-auto mb-4" />
          <p className="text-slate-400">Loading...</p>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }

  // Check tier requirement
  if (requireTier && user) {
    const tierOrder = ['nest', 'flight', 'soar', 'stratosphere'];
    const userTier = user.subscription_tier?.toLowerCase() || 'nest';
    const userTierIndex = tierOrder.indexOf(userTier);
    const requiredTierIndex = tierOrder.indexOf(requireTier.toLowerCase());

    if (userTierIndex < requiredTierIndex) {
      return <Navigate to="/subscription" state={{
        requiredTier: requireTier,
        message: `This feature requires ${requireTier.charAt(0).toUpperCase() + requireTier.slice(1)} tier or higher`
      }} replace />;
    }
  }

  return <>{children}</>;
}

export default ProtectedRoute;
