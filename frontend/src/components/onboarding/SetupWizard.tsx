/**
 * Ospra Intelligence - Setup Wizard
 *
 * 3-step onboarding wizard for first-time users.
 * Uses liquid glass design system from index.css
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Store,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Sparkles,
  Package,
  Home,
  Smartphone,
  Dumbbell,
  Sparkle,
  PawPrint,
  UtensilsCrossed,
  Loader2,
  X,
  Zap,
  Calendar,
  ShoppingBag,
  Globe,
  Palette,
} from 'lucide-react';
import { useOspraStore } from '../../store/ospra.store';
import { shopifyAPI } from '../../services/api';

// ============================================
// TYPES
// ============================================

interface ShopifyStatusData {
  connected: boolean;
  store_name?: string;
  store_url?: string;
}

interface NicheOption {
  id: string;
  label: string;
  icon: typeof Package;
}

// ============================================
// NICHE OPTIONS
// ============================================

const NICHE_OPTIONS: NicheOption[] = [
  { id: 'smart_home', label: 'Smart Home', icon: Home },
  { id: 'tech_gadgets', label: 'Tech Gadgets', icon: Smartphone },
  { id: 'fitness', label: 'Fitness & Health', icon: Dumbbell },
  { id: 'beauty', label: 'Beauty & Skincare', icon: Sparkle },
  { id: 'pet_supplies', label: 'Pet Supplies', icon: PawPrint },
  { id: 'kitchen', label: 'Kitchen & Home', icon: UtensilsCrossed },
];

// ============================================
// PLATFORM OPTIONS
// ============================================

interface PlatformOption {
  id: 'shopify' | 'amazon' | 'woocommerce' | 'etsy';
  label: string;
  icon: typeof Package;
  badge?: string;
  disabled: boolean;
  comingSoon?: boolean;
}

const PLATFORM_OPTIONS: PlatformOption[] = [
  { id: 'shopify', label: 'Shopify', icon: ShoppingBag, badge: 'Most popular', disabled: false },
  { id: 'amazon', label: 'Amazon', icon: Package, badge: 'Coming soon', disabled: true, comingSoon: true },
  { id: 'woocommerce', label: 'WooCommerce', icon: Globe, badge: 'Coming soon', disabled: true, comingSoon: true },
  { id: 'etsy', label: 'Etsy', icon: Palette, badge: 'Coming soon', disabled: true, comingSoon: true },
];

// ============================================
// ANIMATION VARIANTS
// ============================================

const backdropVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
  exit: { opacity: 0 },
};

const modalVariants = {
  hidden: { opacity: 0, scale: 0.95, y: 20 },
  visible: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: {
      type: 'spring',
      damping: 25,
      stiffness: 300,
    },
  },
  exit: { opacity: 0, scale: 0.95, y: 20 },
};

const slideVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 300 : -300,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
    transition: {
      type: 'spring',
      damping: 25,
      stiffness: 300,
    },
  },
  exit: (direction: number) => ({
    x: direction < 0 ? 300 : -300,
    opacity: 0,
    transition: {
      duration: 0.2,
    },
  }),
};

// ============================================
// COMPONENT
// ============================================

export default function SetupWizard() {
  const {
    onboardingStep,
    preferences,
    setOnboarded,
    setOnboardingStep,
    completeOnboardingStep,
    updatePreferences,
    isOnboarded,
  } = useOspraStore();

  const [currentStep, setCurrentStep] = useState(1);
  const [direction, setDirection] = useState(0);

  // Step 1: Shopify Connection
  const [shopifyStatus, setShopifyStatus] = useState<ShopifyStatusData>({ connected: false });
  const [loadingShopify, setLoadingShopify] = useState(true);

  // Step 2: Niche Selection
  const [selectedNiches, setSelectedNiches] = useState<string[]>(
    preferences.selectedNiches || ['smart_home']
  );

  // Step 3: Feature Toggles
  const [autoDeployEnabled, setAutoDeployEnabled] = useState(preferences.autoDeployEnabled);
  const [dailyBriefingEnabled, setDailyBriefingEnabled] = useState(preferences.dailyBriefingEnabled);

  // Show wizard when onboardingStep >= 1 AND user is not yet onboarded
  // This allows wizard to stay visible through steps 1, 2, 3
  const isVisible = onboardingStep >= 1 && !isOnboarded;

  // ============================================
  // EFFECTS
  // ============================================

  useEffect(() => {
    if (isVisible && currentStep === 1) {
      checkShopifyStatus();
    }
  }, [isVisible, currentStep]);

  // ============================================
  // SHOPIFY STATUS CHECK
  // ============================================

  const checkShopifyStatus = async () => {
    setLoadingShopify(true);
    try {
      const status = await shopifyAPI.getStatus();
      setShopifyStatus({
        connected: status.connected || false,
        store_name: status.store_name,
        store_url: status.store_url,
      });
    } catch (error) {
      console.error('[SetupWizard] Failed to check Shopify status:', error);
      setShopifyStatus({ connected: false });
    } finally {
      setLoadingShopify(false);
    }
  };

  // ============================================
  // NAVIGATION
  // ============================================

  const goToNext = () => {
    if (currentStep < 3) {
      setDirection(1);
      setCurrentStep(currentStep + 1);
    }
  };

  const goToPrevious = () => {
    if (currentStep > 1) {
      setDirection(-1);
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSkip = () => {
    completeOnboardingStep('connect-shopify');
    goToNext();
  };

  const handleComplete = () => {
    // Save all preferences
    updatePreferences({
      selectedNiches,
      autoDeployEnabled,
      dailyBriefingEnabled,
    });

    // Complete all remaining onboarding steps
    completeOnboardingStep('connect-shopify');
    completeOnboardingStep('select-niches');
    completeOnboardingStep('enable-features');

    // Mark as fully onboarded
    setOnboarded(true);
    setOnboardingStep(0);

    console.log('[SetupWizard] Onboarding complete!', {
      niches: selectedNiches,
      autoDeployEnabled,
      dailyBriefingEnabled,
    });
  };

  // ============================================
  // NICHE TOGGLE
  // ============================================

  const toggleNiche = (nicheId: string) => {
    setSelectedNiches((prev) =>
      prev.includes(nicheId)
        ? prev.filter((id) => id !== nicheId)
        : [...prev, nicheId]
    );
  };

  // ============================================
  // SHOPIFY CONNECT (PLACEHOLDER)
  // ============================================

  const handleConnectShopify = () => {
    console.log('[SetupWizard] Connect Shopify clicked (placeholder)');
    // TODO: Implement Shopify OAuth flow
  };

  // ============================================
  // RENDER HELPERS
  // ============================================

  const canContinue = () => {
    if (currentStep === 2) {
      return selectedNiches.length > 0;
    }
    return true;
  };

  if (!isVisible) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-[101] flex items-center justify-center p-4"
        variants={backdropVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        style={{
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
        }}
      >
        <motion.div
          className="relative w-full max-w-xl"
          variants={modalVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
        >
          {/* Glass Card Container */}
          <div
            className="relative overflow-hidden rounded-[28px]"
            style={{
              background: 'rgba(255, 255, 255, 0.85)',
              backdropFilter: 'blur(40px) saturate(180%)',
              WebkitBackdropFilter: 'blur(40px) saturate(180%)',
              border: '1px solid rgba(255, 255, 255, 0.5)',
              boxShadow: '0 24px 80px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.8)',
            }}
          >
            {/* Rainbow Refraction Border */}
            <div
              className="absolute inset-[-1px] rounded-[28px] pointer-events-none"
              style={{
                padding: '1.5px',
                background: 'linear-gradient(135deg, rgba(255,120,120,0.4) 0%, rgba(255,200,120,0.3) 20%, rgba(120,255,200,0.35) 40%, rgba(120,200,255,0.4) 60%, rgba(200,120,255,0.35) 80%, rgba(255,120,200,0.3) 100%)',
                WebkitMask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
                mask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
                WebkitMaskComposite: 'xor',
                maskComposite: 'exclude',
                opacity: 0.7,
              }}
            />

            {/* Close Button */}
            <button
              onClick={() => setOnboardingStep(0)}
              className="absolute top-4 right-4 p-2 rounded-xl hover:bg-black/5 transition-colors z-20"
              aria-label="Close"
            >
              <X className="w-5 h-5 text-[var(--text-tertiary)]" />
            </button>

            {/* Progress Bar */}
            <div className="px-8 pt-6">
              <div className="flex gap-2">
                {[1, 2, 3].map((step) => (
                  <div
                    key={step}
                    className="flex-1 h-1.5 rounded-full overflow-hidden"
                    style={{ background: 'rgba(0, 0, 0, 0.08)' }}
                  >
                    <motion.div
                      className="h-full"
                      style={{
                        background: 'linear-gradient(135deg, #0071E3 0%, #5856D6 100%)',
                      }}
                      initial={{ width: 0 }}
                      animate={{ width: currentStep >= step ? '100%' : '0%' }}
                      transition={{ duration: 0.4, ease: 'easeOut' }}
                    />
                  </div>
                ))}
              </div>
              <div className="text-xs text-[var(--text-tertiary)] text-center mt-2">
                Step {currentStep} of 3
              </div>
            </div>

            {/* Content */}
            <div className="relative p-8 min-h-[420px]">
              <AnimatePresence mode="wait" custom={direction}>
                <motion.div
                  key={currentStep}
                  custom={direction}
                  variants={slideVariants}
                  initial="enter"
                  animate="center"
                  exit="exit"
                  className="absolute inset-8"
                >
                  {/* STEP 1: Connect Your Store */}
                  {currentStep === 1 && (
                    <div>
                      <div className="text-center mb-6">
                        <motion.div
                          className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-4"
                          style={{
                            background: 'linear-gradient(135deg, #0071E3 0%, #5856D6 100%)',
                          }}
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          transition={{ type: 'spring', damping: 15 }}
                        >
                          <Store className="w-7 h-7 text-white" />
                        </motion.div>

                        <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
                          Connect Your Store
                        </h2>
                        <p className="text-sm text-[var(--text-secondary)]">
                          Link your e-commerce platform to enable product deployment
                        </p>
                      </div>

                      {/* Platform Grid */}
                      <div className="grid grid-cols-2 gap-3 mb-4">
                        {PLATFORM_OPTIONS.map((platform) => {
                          const Icon = platform.icon;
                          const isSelected = preferences.selectedPlatform === platform.id;
                          const isShopify = platform.id === 'shopify';
                          const showConnected = isShopify && shopifyStatus.connected;

                          return (
                            <button
                              key={platform.id}
                              onClick={() => {
                                if (platform.disabled && platform.comingSoon) {
                                  // Show tooltip or message for coming soon platforms
                                  console.log(`${platform.label} coming Q1 2025`);
                                } else if (isShopify) {
                                  // For Shopify, check connection and update preference
                                  updatePreferences({ selectedPlatform: 'shopify' });
                                  if (!shopifyStatus.connected) {
                                    handleConnectShopify();
                                  }
                                }
                              }}
                              disabled={platform.disabled}
                              className="p-4 rounded-xl border transition-all text-left relative"
                              style={{
                                background: isSelected
                                  ? 'rgba(0, 113, 227, 0.1)'
                                  : platform.disabled
                                  ? 'rgba(0, 0, 0, 0.02)'
                                  : 'rgba(0, 0, 0, 0.02)',
                                borderColor: isSelected
                                  ? 'var(--accent)'
                                  : 'var(--glass-border-subtle)',
                                opacity: platform.disabled ? 0.6 : 1,
                                cursor: platform.disabled ? 'not-allowed' : 'pointer',
                              }}
                            >
                              {/* Badge */}
                              {platform.badge && (
                                <div
                                  className="absolute top-2 right-2 px-2 py-0.5 rounded-full text-[10px] font-medium"
                                  style={{
                                    background: platform.disabled
                                      ? 'rgba(142, 142, 147, 0.1)'
                                      : 'rgba(0, 113, 227, 0.1)',
                                    color: platform.disabled
                                      ? 'var(--text-tertiary)'
                                      : 'var(--accent)',
                                  }}
                                >
                                  {platform.badge}
                                </div>
                              )}

                              <div className="flex items-center gap-3">
                                <div
                                  className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                                  style={{
                                    background: isSelected
                                      ? 'var(--accent)'
                                      : 'rgba(0, 0, 0, 0.05)',
                                  }}
                                >
                                  <Icon
                                    className="w-5 h-5"
                                    style={{
                                      color: isSelected ? 'white' : 'var(--text-secondary)',
                                    }}
                                  />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div
                                    className="text-sm font-medium"
                                    style={{
                                      color: isSelected
                                        ? 'var(--accent)'
                                        : 'var(--text-primary)',
                                    }}
                                  >
                                    {platform.label}
                                  </div>
                                  {showConnected && (
                                    <div className="flex items-center gap-1 mt-1">
                                      <CheckCircle2 className="w-3 h-3 text-[var(--success)]" />
                                      <span className="text-xs text-[var(--success)]">
                                        Connected
                                      </span>
                                    </div>
                                  )}
                                  {loadingShopify && isShopify && (
                                    <div className="flex items-center gap-1 mt-1">
                                      <Loader2 className="w-3 h-3 text-[var(--accent)] animate-spin" />
                                      <span className="text-xs text-[var(--accent)]">
                                        Checking...
                                      </span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </button>
                          );
                        })}
                      </div>

                      <button
                        onClick={handleSkip}
                        className="w-full text-sm text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] py-2 transition-colors"
                      >
                        Skip for now
                      </button>
                    </div>
                  )}

                  {/* STEP 2: Choose Niches */}
                  {currentStep === 2 && (
                    <div>
                      <div className="text-center mb-6">
                        <motion.div
                          className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-4"
                          style={{
                            background: 'linear-gradient(135deg, #0071E3 0%, #5856D6 100%)',
                          }}
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          transition={{ type: 'spring', damping: 15 }}
                        >
                          <Package className="w-7 h-7 text-white" />
                        </motion.div>

                        <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
                          What do you want to sell?
                        </h2>
                        <p className="text-sm text-[var(--text-secondary)]">
                          Select niches to focus your product discovery
                        </p>
                      </div>

                      <div className="grid grid-cols-2 gap-3 mb-4">
                        {NICHE_OPTIONS.map((niche) => {
                          const isSelected = selectedNiches.includes(niche.id);
                          const Icon = niche.icon;

                          return (
                            <button
                              key={niche.id}
                              onClick={() => toggleNiche(niche.id)}
                              className="p-4 rounded-xl border transition-all text-left"
                              style={{
                                background: isSelected
                                  ? 'rgba(0, 113, 227, 0.1)'
                                  : 'rgba(0, 0, 0, 0.02)',
                                borderColor: isSelected
                                  ? 'var(--accent)'
                                  : 'var(--glass-border-subtle)',
                              }}
                            >
                              <div className="flex items-center gap-3">
                                <div
                                  className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                                  style={{
                                    background: isSelected
                                      ? 'var(--accent)'
                                      : 'rgba(0, 0, 0, 0.05)',
                                  }}
                                >
                                  <Icon
                                    className="w-5 h-5"
                                    style={{
                                      color: isSelected ? 'white' : 'var(--text-secondary)',
                                    }}
                                  />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div
                                    className="text-sm font-medium"
                                    style={{
                                      color: isSelected
                                        ? 'var(--accent)'
                                        : 'var(--text-primary)',
                                    }}
                                  >
                                    {niche.label}
                                  </div>
                                </div>
                              </div>
                            </button>
                          );
                        })}
                      </div>

                      {selectedNiches.length === 0 && (
                        <div className="text-xs text-[var(--warning)] text-center">
                          Please select at least one niche to continue
                        </div>
                      )}
                    </div>
                  )}

                  {/* STEP 3: Enable Features */}
                  {currentStep === 3 && (
                    <div>
                      <div className="text-center mb-6">
                        <motion.div
                          className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-4"
                          style={{
                            background: 'linear-gradient(135deg, #0071E3 0%, #5856D6 100%)',
                          }}
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          transition={{ type: 'spring', damping: 15 }}
                        >
                          <Sparkles className="w-7 h-7 text-white" />
                        </motion.div>

                        <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
                          Customize Your Experience
                        </h2>
                        <p className="text-sm text-[var(--text-secondary)]">
                          Choose which AI features to enable
                        </p>
                      </div>

                      <div className="space-y-4">
                        {/* Auto-Deploy Toggle */}
                        <div
                          className="p-4 rounded-xl border border-[var(--glass-border-subtle)]"
                          style={{ background: 'rgba(0, 0, 0, 0.02)' }}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-start gap-3 flex-1">
                              <div
                                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                                style={{ background: 'rgba(0, 113, 227, 0.1)' }}
                              >
                                <Zap className="w-5 h-5 text-[var(--accent)]" />
                              </div>
                              <div className="flex-1">
                                <div className="text-sm font-medium text-[var(--text-primary)]">
                                  Auto-Deploy Products
                                </div>
                                <div className="text-xs text-[var(--text-secondary)] mt-0.5">
                                  Automatically deploy high-scoring products to Shopify
                                </div>
                              </div>
                            </div>
                            <button
                              onClick={() => setAutoDeployEnabled(!autoDeployEnabled)}
                              className="flex-shrink-0 ml-4"
                            >
                              <div
                                className="relative w-11 h-6 rounded-full transition-colors"
                                style={{
                                  background: autoDeployEnabled
                                    ? 'var(--accent)'
                                    : 'rgba(0, 0, 0, 0.1)',
                                }}
                              >
                                <motion.div
                                  className="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow"
                                  animate={{ x: autoDeployEnabled ? 20 : 0 }}
                                  transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                                />
                              </div>
                            </button>
                          </div>
                        </div>

                        {/* Daily Briefing Toggle */}
                        <div
                          className="p-4 rounded-xl border border-[var(--glass-border-subtle)]"
                          style={{ background: 'rgba(0, 0, 0, 0.02)' }}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-start gap-3 flex-1">
                              <div
                                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                                style={{ background: 'rgba(0, 113, 227, 0.1)' }}
                              >
                                <Calendar className="w-5 h-5 text-[var(--accent)]" />
                              </div>
                              <div className="flex-1">
                                <div className="text-sm font-medium text-[var(--text-primary)]">
                                  Daily Briefing
                                </div>
                                <div className="text-xs text-[var(--text-secondary)] mt-0.5">
                                  Get a morning summary of trends and opportunities
                                </div>
                              </div>
                            </div>
                            <button
                              onClick={() => setDailyBriefingEnabled(!dailyBriefingEnabled)}
                              className="flex-shrink-0 ml-4"
                            >
                              <div
                                className="relative w-11 h-6 rounded-full transition-colors"
                                style={{
                                  background: dailyBriefingEnabled
                                    ? 'var(--accent)'
                                    : 'rgba(0, 0, 0, 0.1)',
                                }}
                              >
                                <motion.div
                                  className="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow"
                                  animate={{ x: dailyBriefingEnabled ? 20 : 0 }}
                                  transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                                />
                              </div>
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </motion.div>
              </AnimatePresence>
            </div>

            {/* Footer Actions */}
            <div
              className="px-8 pb-6 flex gap-3"
              style={{ paddingTop: currentStep === 2 && selectedNiches.length === 0 ? '0.5rem' : '0' }}
            >
              {currentStep > 1 && (
                <button
                  onClick={goToPrevious}
                  className="btn-secondary flex items-center gap-2 px-6 py-3"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>Back</span>
                </button>
              )}

              {currentStep < 3 ? (
                <button
                  onClick={goToNext}
                  disabled={!canContinue()}
                  className="btn-primary flex-1 flex items-center justify-center gap-2 px-6 py-3"
                  style={{
                    opacity: canContinue() ? 1 : 0.5,
                    cursor: canContinue() ? 'pointer' : 'not-allowed',
                  }}
                >
                  <span>Continue</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              ) : (
                <button
                  onClick={handleComplete}
                  className="btn-primary flex-1 flex items-center justify-center gap-2 px-6 py-3"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Complete Setup</span>
                </button>
              )}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
