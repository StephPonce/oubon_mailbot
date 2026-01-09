// 
// REGISTER PAGE
// Create new account with tier selection
// 

import { useState, FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Loader2, AlertCircle, Zap, Eye, EyeOff, CheckCircle2, Check } from 'lucide-react';
import { authApi } from '../api/auth';
import { useAuth } from '../contexts/AuthContext';

const TIERS = [
  { id: 'nest', name: 'Nest', price: 'Free', description: '10 products/week • 1 store' },
  { id: 'flight', name: 'Flight', price: '$29/mo', description: '50 products/week • 3 stores' },
  { id: 'soar', name: 'Soar', price: '$79/mo', description: '200 products/week • 10 stores' },
  { id: 'stratosphere', name: 'Stratosphere', price: '$199/mo', description: 'Unlimited • Priority support' },
];

export default function Register() {
  const navigate = useNavigate();
  const { login } = useAuth();
  
  // Form state
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [selectedTier, setSelectedTier] = useState('nest');
  const [showPassword, setShowPassword] = useState(false);
  
  // UI state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!name.trim()) {
      setError('Name is required');
      return;
    }
    
    if (!email.trim()) {
      setError('Email is required');
      return;
    }
    
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

    // Register with selected tier
    const result = await authApi.register({
      name: name.trim(),
      email: email.trim(),
      password,
      tier: selectedTier,  // Send selected tier
    });

    if (result.success) {
      // Auto-login after registration
      const loginResult = await login({
        email: email.trim(),
        password,
        remember_me: true,
      });
      
      if (loginResult.success) {
        navigate('/');
      } else {
        // Registration succeeded but login failed - redirect to login
        navigate('/login');
      }
    } else {
      setError(result.error || 'Registration failed. Please try again.');
    }
    
    setIsSubmitting(false);
  };

  // Password strength indicator
  const getPasswordStrength = () => {
    if (!password) return { strength: 0, label: '', color: '' };
    
    let strength = 0;
    if (password.length >= 8) strength++;
    if (password.length >= 12) strength++;
    if (/[A-Z]/.test(password)) strength++;
    if (/[0-9]/.test(password)) strength++;
    if (/[^A-Za-z0-9]/.test(password)) strength++;
    
    if (strength <= 2) return { strength: 1, label: 'Weak', color: 'bg-red-500' };
    if (strength <= 3) return { strength: 2, label: 'Fair', color: 'bg-yellow-500' };
    if (strength <= 4) return { strength: 3, label: 'Good', color: 'bg-blue-500' };
    return { strength: 4, label: 'Strong', color: 'bg-green-500' };
  };

  const passwordStrength = getPasswordStrength();

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
              Create Account
            </h1>
            <p className="text-secondary text-sm">
              Start your e-commerce automation journey
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
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name Field */}
            <div>
              <label htmlFor="name" className="label">
                Full Name
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="John Doe"
                className="input"
                disabled={isSubmitting}
                autoComplete="name"
                autoFocus
              />
            </div>

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
              />
            </div>

            {/* Password Field */}
            <div>
              <label htmlFor="password" className="label">
                Password
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
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-tertiary hover:text-secondary"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              
              {/* Password Strength Meter */}
              {password && (
                <div className="mt-2">
                  <div className="flex gap-1 mb-1">
                    {[1, 2, 3, 4].map((level) => (
                      <div
                        key={level}
                        className={`h-1 flex-1 rounded ${
                          level <= passwordStrength.strength 
                            ? passwordStrength.color 
                            : 'bg-white/10'
                        }`}
                      />
                    ))}
                  </div>
                  <p className="text-xs text-tertiary">
                    Password strength: <span className="text-secondary">{passwordStrength.label}</span>
                  </p>
                </div>
              )}
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
              {confirmPassword && password !== confirmPassword && (
                <p className="text-xs text-red-400 mt-1">Passwords do not match</p>
              )}
              {confirmPassword && password === confirmPassword && (
                <p className="text-xs text-green-400 mt-1 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Passwords match
                </p>
              )}
            </div>

            {/* Tier Selection */}
            <div>
              <label className="label">Select Plan</label>
              <div className="grid grid-cols-2 gap-2">
                {TIERS.map((tier) => (
                  <button
                    key={tier.id}
                    type="button"
                    onClick={() => setSelectedTier(tier.id)}
                    className={`p-3 rounded-xl border text-left transition-all ${
                      selectedTier === tier.id
                        ? 'border-purple-500 bg-purple-500/20'
                        : 'border-white/10 bg-white/5 hover:border-white/20'
                    }`}
                    disabled={isSubmitting}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-sm text-primary">{tier.name}</span>
                      <span className="text-xs text-secondary">{tier.price}</span>
                    </div>
                    <p className="text-xs text-tertiary">{tier.description}</p>
                    {selectedTier === tier.id && (
                      <div className="absolute top-2 right-2">
                        <Check className="w-4 h-4 text-purple-400" />
                      </div>
                    )}
                  </button>
                ))}
              </div>
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
                  Creating account...
                </>
              ) : (
                'Create Account'
              )}
            </button>
          </form>

          {/* Terms */}
          <p className="text-xs text-tertiary text-center mt-4">
            By creating an account, you agree to our{' '}
            <a href="#" className="link">Terms of Service</a>
            {' '}and{' '}
            <a href="#" className="link">Privacy Policy</a>
          </p>

          {/* Login Link */}
          <div className="mt-6 text-center">
            <p className="text-sm text-tertiary">
              Already have an account?{' '}
              <Link to="/login" className="link">
                Sign in
              </Link>
            </p>
          </div>
        </div>

        {/* Version Badge */}
        <div className="text-center mt-6">
          <span className="text-xs text-muted">
            Powered by Oi • Ospra Intelligence
          </span>
        </div>
      </div>
    </div>
  );
}
