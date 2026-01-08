// 
// LOGIN PAGE
// Dark liquid glass aesthetic
// 

import { useState, FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Loader2, AlertCircle, Zap } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const navigate = useNavigate();
  const { login, isLoading: authLoading } = useAuth();
  
  // Form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  
  // UI state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    // Validation
    if (!email.trim()) {
      setError('Email is required');
      setIsSubmitting(false);
      return;
    }
    
    if (!password) {
      setError('Password is required');
      setIsSubmitting(false);
      return;
    }

    // Attempt login
    const result = await login({
      email: email.trim(),
      password,
      remember_me: rememberMe,
    });

    if (result.success) {
      navigate('/');
    } else {
      setError(result.error || 'Login failed. Please try again.');
    }
    
    setIsSubmitting(false);
  };

  const isLoading = isSubmitting || authLoading;

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      {/* Background */}
      <div className="app-background" />
      
      {/* Login Card */}
      <div className="w-full max-w-md animate-fade-in">
        <div className="glass-card-static p-8">
          {/* Logo & Header */}
          <div className="text-center mb-8">
            <div className="logo-icon mx-auto mb-4">
              <Zap className="w-6 h-6" />
            </div>
            <h1 className="text-2xl font-semibold text-primary mb-2">
              Welcome Back
            </h1>
            <p className="text-secondary text-sm">
              Sign in to Ospra Intelligence
            </p>
          </div>

          {/* Error Alert */}
          {error && (
            <div className="alert alert-error mb-6">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Email Field */}
            <div>
              <label htmlFor="email" className="label">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="input"
                disabled={isLoading}
                autoComplete="email"
                autoFocus
              />
            </div>

            {/* Password Field */}
            <div>
              <label htmlFor="password" className="label">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="input"
                disabled={isLoading}
                autoComplete="current-password"
              />
            </div>

            {/* Remember Me & Forgot Password */}
            <div className="flex items-center justify-between">
              <label className="checkbox-wrapper">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="checkbox"
                  disabled={isLoading}
                />
                <span className="text-sm text-secondary">Remember me</span>
              </label>
              
              <Link to="/forgot-password" className="link text-sm">
                Forgot password?
              </Link>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          {/* Register Link */}
          <div className="mt-6 text-center">
            <p className="text-sm text-tertiary">
              Don't have an account?{' '}
              <Link to="/register" className="link">
                Create one
              </Link>
            </p>
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
