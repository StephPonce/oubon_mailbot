// 
// RESET PASSWORD PAGE
// Set new password using reset token from email
// 

import { useState, useEffect, FormEvent } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { Loader2, AlertCircle, CheckCircle2, ArrowLeft, Zap, Eye, EyeOff } from 'lucide-react';
import { authApi } from '../api/auth';

export default function ResetPassword() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  
  // Form state
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  
  // UI state
  const [isVerifying, setIsVerifying] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [tokenValid, setTokenValid] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Verify token on mount
  useEffect(() => {
    const verifyToken = async () => {
      if (!token) {
        setTokenValid(false);
        setIsVerifying(false);
        return;
      }

      const result = await authApi.verifyResetToken(token);
      setTokenValid(result.valid);
      setIsVerifying(false);
    };

    verifyToken();
  }, [token]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!password) {
      setError('Password is required');
      return;
    }
    
    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsSubmitting(true);

    // Reset password
    const result = await authApi.resetPassword(token!, password);

    if (result.success) {
      setSuccess(true);
    } else {
      setError(result.error || 'Failed to reset password. Please try again.');
    }
    
    setIsSubmitting(false);
  };

  // Loading state
  if (isVerifying) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="app-background" />
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-accent mx-auto mb-4" />
          <p className="text-secondary text-sm">Verifying reset link...</p>
        </div>
      </div>
    );
  }

  // Invalid/expired token
  if (!tokenValid) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="app-background" />
        
        <div className="w-full max-w-md animate-fade-in">
          <div className="glass-card-static p-8">
            <div className="text-center mb-6">
              <div className="w-16 h-16 rounded-full bg-red-500/20 border border-red-500/30 flex items-center justify-center mx-auto mb-4">
                <AlertCircle className="w-8 h-8 text-red-400" />
              </div>
              <h1 className="text-2xl font-semibold text-primary mb-2">
                Link Expired
              </h1>
              <p className="text-secondary text-sm">
                This password reset link is invalid or has expired.
              </p>
            </div>

            <Link to="/forgot-password" className="btn btn-primary w-full mb-3">
              Request New Link
            </Link>
            
            <Link to="/login" className="btn btn-secondary w-full">
              <ArrowLeft className="w-4 h-4" />
              Back to Login
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Success state
  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="app-background" />
        
        <div className="w-full max-w-md animate-fade-in">
          <div className="glass-card-static p-8">
            <div className="text-center mb-6">
              <div className="w-16 h-16 rounded-full bg-green-500/20 border border-green-500/30 flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="w-8 h-8 text-green-400" />
              </div>
              <h1 className="text-2xl font-semibold text-primary mb-2">
                Password Reset!
              </h1>
              <p className="text-secondary text-sm">
                Your password has been successfully reset. You can now sign in with your new password.
              </p>
            </div>

            <Link to="/login" className="btn btn-primary w-full">
              Sign In
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      {/* Background */}
      <div className="app-background" />
      
      {/* Card */}
      <div className="w-full max-w-md animate-fade-in">
        <div className="glass-card-static p-8">
          {/* Logo & Header */}
          <div className="text-center mb-8">
            <div className="logo-icon mx-auto mb-4">
              <Zap className="w-6 h-6" />
            </div>
            <h1 className="text-2xl font-semibold text-primary mb-2">
              Create New Password
            </h1>
            <p className="text-secondary text-sm">
              Your new password must be at least 8 characters.
            </p>
          </div>

          {/* Error Alert */}
          {error && (
            <div className="alert alert-error mb-6">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* New Password Field */}
            <div>
              <label htmlFor="password" className="label">
                New Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input pr-10"
                  disabled={isSubmitting}
                  autoComplete="new-password"
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-tertiary hover:text-secondary"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Confirm Password Field */}
            <div>
              <label htmlFor="confirmPassword" className="label">
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className="input"
                disabled={isSubmitting}
                autoComplete="new-password"
              />
            </div>

            {/* Password Requirements */}
            <div className="text-xs text-tertiary">
              <p className={password.length >= 8 ? 'text-green-400' : ''}>
                {password.length >= 8 ? '[OK]' : ''} At least 8 characters
              </p>
              <p className={password && password === confirmPassword ? 'text-green-400' : ''}>
                {password && password === confirmPassword ? '[OK]' : ''} Passwords match
              </p>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Resetting...
                </>
              ) : (
                'Reset Password'
              )}
            </button>
          </form>

          {/* Back to Login */}
          <div className="mt-6 text-center">
            <Link to="/login" className="link text-sm inline-flex items-center gap-2">
              <ArrowLeft className="w-3 h-3" />
              Back to Login
            </Link>
          </div>
        </div>

        {/* Version Badge */}
        <div className="text-center mt-6">
          <span className="text-xs text-muted">
            Ospra Intelligence V5 • Product Discovery Engine
          </span>
        </div>
      </div>
    </div>
  );
}
