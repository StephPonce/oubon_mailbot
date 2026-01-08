// 
// FORGOT PASSWORD PAGE
// Request password reset email
// 

import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, AlertCircle, CheckCircle2, ArrowLeft, Zap, Mail } from 'lucide-react';
import { authApi } from '../api/auth';

export default function ForgotPassword() {
  // Form state
  const [email, setEmail] = useState('');
  
  // UI state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

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

    // Request password reset
    const result = await authApi.forgotPassword(email.trim());

    if (result.success) {
      setSuccess(true);
    } else {
      setError(result.error || 'Something went wrong. Please try again.');
    }
    
    setIsSubmitting(false);
  };

  // Success state
  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="app-background" />
        
        <div className="w-full max-w-md animate-fade-in">
          <div className="glass-card-static p-8">
            {/* Success Icon */}
            <div className="text-center mb-6">
              <div className="w-16 h-16 rounded-full bg-green-500/20 border border-green-500/30 flex items-center justify-center mx-auto mb-4">
                <Mail className="w-8 h-8 text-green-400" />
              </div>
              <h1 className="text-2xl font-semibold text-primary mb-2">
                Check Your Email
              </h1>
              <p className="text-secondary text-sm">
                If an account exists for <span className="text-primary">{email}</span>, 
                we've sent a password reset link.
              </p>
            </div>

            {/* Instructions */}
            <div className="p-4 rounded-xl bg-white/5 border border-white/10 mb-6">
              <p className="text-sm text-secondary">
                <strong className="text-primary">Next steps:</strong>
              </p>
              <ol className="text-sm text-tertiary mt-2 space-y-1 list-decimal list-inside">
                <li>Check your email inbox</li>
                <li>Click the reset link (expires in 1 hour)</li>
                <li>Create a new password</li>
              </ol>
            </div>

            {/* Didn't receive email */}
            <p className="text-xs text-tertiary text-center mb-4">
              Didn't receive the email? Check your spam folder or{' '}
              <button 
                onClick={() => { setSuccess(false); setEmail(''); }}
                className="link"
              >
                try again
              </button>
            </p>

            {/* Back to Login */}
            <Link
              to="/login"
              className="btn btn-secondary w-full"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Login
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
              Forgot Password?
            </h1>
            <p className="text-secondary text-sm">
              No worries. Enter your email and we'll send you a reset link.
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
                disabled={isSubmitting}
                autoComplete="email"
                autoFocus
              />
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
                  Sending...
                </>
              ) : (
                'Send Reset Link'
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
