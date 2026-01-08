// 
// DASHBOARD - Minimal Placeholder
// Just proves authentication works - will be expanded later
// 

import { LogOut, Zap, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function Dashboard() {
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      {/* Background */}
      <div className="app-background" />
      
      {/* Dashboard Card */}
      <div className="w-full max-w-lg animate-fade-in">
        <div className="glass-card-static p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="logo-icon mx-auto mb-4">
              <Zap className="w-6 h-6" />
            </div>
            <h1 className="text-2xl font-semibold text-primary mb-2">
              Ospra Intelligence V5
            </h1>
            <p className="text-secondary text-sm">
              Product Discovery Engine
            </p>
          </div>

          {/* Auth Success Message */}
          <div className="alert alert-success mb-6">
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            <span>Authentication working! You're signed in.</span>
          </div>

          {/* User Info */}
          <div className="p-4 rounded-xl bg-white/5 border border-white/10 mb-6">
            <div className="text-xs text-tertiary uppercase tracking-wider mb-2">
              Signed in as
            </div>
            <div className="text-lg font-medium text-primary">
              {user?.email || 'User'}
            </div>
            {user?.tier && (
              <div className="text-sm text-secondary mt-1">
                Tier: {user.tier}
              </div>
            )}
          </div>

          {/* Status */}
          <div className="space-y-3 mb-6">
            <div className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10">
              <span className="text-sm text-secondary">Feature #1</span>
              <span className="text-xs text-success font-medium">[SUCCESS] Authentication</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10">
              <span className="text-sm text-secondary">Feature #2</span>
              <span className="text-xs text-tertiary font-medium">⏳ Coming next...</span>
            </div>
          </div>

          {/* Logout Button */}
          <button
            onClick={handleLogout}
            className="btn btn-secondary w-full"
          >
            <LogOut className="w-4 h-4" />
            Sign Out
          </button>

          {/* Instructions */}
          <div className="mt-6 p-4 rounded-xl bg-blue-500/10 border border-blue-500/20">
            <p className="text-sm text-blue-300">
              <strong>Next step:</strong> Tell me what feature to build next. 
              The login, remember me, and logout are now fully functional.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
