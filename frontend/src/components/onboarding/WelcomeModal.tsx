/**
 * Ospra Intelligence - Welcome Modal
 * 
 * First-time user onboarding experience.
 * Uses liquid glass design system from index.css
 */

import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles,
  Zap,
  Package,
  Mail,
  Brain,
  ArrowRight,
  X,
} from 'lucide-react';
import { useOspraStore } from '../../store/ospra.store';

// ============================================
// TYPES
// ============================================

interface WelcomeModalProps {
  onComplete?: () => void;
}

// ============================================
// CAPABILITY DATA
// ============================================

const capabilities = [
  {
    icon: Brain,
    title: 'Find winning products with AI',
    description: 'Discover trending products across AliExpress, TikTok, and Amazon',
  },
  {
    icon: Package,
    title: 'Auto-deploy to Shopify',
    description: 'One-click deployment with AI-generated listings and SEO',
  },
  {
    icon: Zap,
    title: 'Real-time trend monitoring',
    description: 'Stock market-style tracking of product momentum',
  },
  {
    icon: Mail,
    title: 'Automated email responses',
    description: 'AI handles customer support within your parameters',
  },
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
  hidden: { 
    opacity: 0, 
    scale: 0.95,
    y: 20,
  },
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
  exit: { 
    opacity: 0, 
    scale: 0.95,
    y: 20,
    transition: {
      duration: 0.2,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, x: -10 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: {
      delay: 0.3 + i * 0.1,
      duration: 0.4,
    },
  }),
};

// ============================================
// COMPONENT
// ============================================

export default function WelcomeModal({ onComplete }: WelcomeModalProps) {
  const {
    showWelcomeModal,
    setShowWelcomeModal,
    setOnboardingStep,
    completeOnboardingStep,
    setUserName,
    isOnboarded,
    onboardingStep,
  } = useOspraStore();

  // Show modal on mount if user is not onboarded and at step 0
  useEffect(() => {
    if (!isOnboarded && onboardingStep === 0) {
      // Small delay for smoother initial load
      const timer = setTimeout(() => {
        setShowWelcomeModal(true);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isOnboarded, onboardingStep, setShowWelcomeModal]);

  const handleGetStarted = () => {
    completeOnboardingStep('welcome');
    setOnboardingStep(1);
    setShowWelcomeModal(false);
    
    // Set a default name for now (will be updated in setup wizard)
    setUserName('there');
    
    onComplete?.();
  };

  const handleSkip = () => {
    setShowWelcomeModal(false);
    // Don't mark as onboarded, just close the modal
    // User can restart onboarding by clearing localStorage or from settings
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      handleSkip();
    }
  };

  return (
    <AnimatePresence>
      {showWelcomeModal && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          variants={backdropVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          onClick={handleBackdropClick}
          style={{
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
          }}
        >
          <motion.div
            className="relative w-full max-w-lg"
            variants={modalVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            onClick={(e) => e.stopPropagation()}
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
                onClick={handleSkip}
                className="absolute top-4 right-4 p-2 rounded-xl hover:bg-black/5 transition-colors z-10"
                aria-label="Close"
              >
                <X className="w-5 h-5 text-[var(--text-tertiary)]" />
              </button>

              {/* Content */}
              <div className="relative z-10 p-8">
                {/* Header */}
                <div className="text-center mb-8">
                  <motion.div
                    className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
                    style={{
                      background: 'linear-gradient(135deg, #0071E3 0%, #5856D6 100%)',
                      boxShadow: '0 8px 24px rgba(0, 113, 227, 0.3)',
                    }}
                    initial={{ scale: 0, rotate: -180 }}
                    animate={{ scale: 1, rotate: 0 }}
                    transition={{ 
                      type: 'spring', 
                      damping: 15, 
                      stiffness: 200,
                      delay: 0.1,
                    }}
                  >
                    <Sparkles className="w-8 h-8 text-white" />
                  </motion.div>

                  <motion.h1
                    className="text-2xl font-semibold text-[var(--text-primary)] mb-2"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                  >
                    Hi, I'm Ospra
                  </motion.h1>

                  <motion.p
                    className="text-[var(--text-secondary)] text-base"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.25 }}
                  >
                    Your AI-powered e-commerce intelligence
                  </motion.p>
                </div>

                {/* Capabilities */}
                <div className="space-y-3 mb-8">
                  {capabilities.map((item, index) => (
                    <motion.div
                      key={item.title}
                      className="flex items-start gap-4 p-3 rounded-xl transition-colors hover:bg-black/[0.03]"
                      custom={index}
                      variants={itemVariants}
                      initial="hidden"
                      animate="visible"
                    >
                      <div
                        className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center"
                        style={{
                          background: 'rgba(0, 113, 227, 0.1)',
                        }}
                      >
                        <item.icon className="w-5 h-5 text-[var(--accent)]" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                          {item.title}
                        </h3>
                        <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                          {item.description}
                        </p>
                      </div>
                    </motion.div>
                  ))}
                </div>

                {/* Actions */}
                <div className="space-y-3">
                  <motion.button
                    className="w-full btn-primary py-3 text-base"
                    onClick={handleGetStarted}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.7 }}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <span>Let's Get Started</span>
                    <ArrowRight className="w-5 h-5" />
                  </motion.button>

                  <motion.button
                    className="w-full text-sm text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] py-2 transition-colors"
                    onClick={handleSkip}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.8 }}
                  >
                    Skip for now
                  </motion.button>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
