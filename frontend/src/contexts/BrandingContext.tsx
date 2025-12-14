/**
 * White-Label Branding Context - GROK RECOMMENDATION #19
 *
 * Automatically loads and applies white-label branding from the API.
 * Supports custom logos, colors, fonts, CSS, and domain-based branding.
 */

import React, { createContext, useContext, useEffect, useState } from 'react';

interface BrandingColors {
  primary: string;
  secondary: string;
  accent: string;
  background: string;
  surface: string;
  text: string;
  textMuted: string;
  success: string;
  warning: string;
  error: string;
}

interface BrandingFonts {
  family: string;
  heading: string;
}

interface BrandingConfig {
  whitelabel: boolean;
  partner_id?: number;
  partner_slug?: string;
  brand_name: string;
  tagline?: string;
  logo_url?: string;
  logo_dark_url?: string;
  favicon_url?: string;
  colors?: BrandingColors;
  fonts?: BrandingFonts;
  custom_css?: string;
  ui_config?: Record<string, any>;
  settings?: Record<string, any>;
}

interface BrandingContextType {
  branding: BrandingConfig | null;
  loading: boolean;
  error: string | null;
  refreshBranding: () => Promise<void>;
}

const defaultBranding: BrandingConfig = {
  whitelabel: false,
  brand_name: 'Ospra',
  tagline: 'E-Commerce Intelligence Platform',
};

const BrandingContext = createContext<BrandingContextType>({
  branding: defaultBranding,
  loading: false,
  error: null,
  refreshBranding: async () => {},
});

export const useBranding = () => {
  const context = useContext(BrandingContext);
  if (!context) {
    throw new Error('useBranding must be used within a BrandingProvider');
  }
  return context;
};

interface BrandingProviderProps {
  children: React.ReactNode;
  apiBaseUrl?: string;
}

export const BrandingProvider: React.FC<BrandingProviderProps> = ({
  children,
  apiBaseUrl = 'http://localhost:8001'
}) => {
  const [branding, setBranding] = useState<BrandingConfig | null>(defaultBranding);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadBranding = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${apiBaseUrl}/api/whitelabel/branding`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error(`Failed to load branding: ${response.statusText}`);
      }

      const data = await response.json();

      // If no white-label branding, use default
      if (!data.whitelabel) {
        setBranding(defaultBranding);
        applyBranding(defaultBranding);
      } else {
        setBranding(data);
        applyBranding(data);
      }
    } catch (err) {
      console.error('Branding load error:', err);
      setError(err instanceof Error ? err.message : 'Failed to load branding');
      setBranding(defaultBranding);
      applyBranding(defaultBranding);
    } finally {
      setLoading(false);
    }
  };

  const applyBranding = (config: BrandingConfig) => {
    // Update document title
    if (config.brand_name) {
      document.title = config.tagline
        ? `${config.brand_name} - ${config.tagline}`
        : config.brand_name;
    }

    // Update favicon
    if (config.favicon_url) {
      updateFavicon(config.favicon_url);
    }

    // Apply CSS variables
    if (config.colors) {
      applyCSSVariables(config.colors);
    }

    // Apply custom fonts
    if (config.fonts) {
      applyFonts(config.fonts);
    }

    // Inject custom CSS
    if (config.custom_css) {
      injectCustomCSS(config.custom_css);
    }
  };

  const updateFavicon = (faviconUrl: string) => {
    // Remove existing favicon
    const existingFavicon = document.querySelector("link[rel*='icon']");
    if (existingFavicon) {
      existingFavicon.remove();
    }

    // Add new favicon
    const link = document.createElement('link');
    link.rel = 'icon';
    link.type = 'image/png';
    link.href = faviconUrl;
    document.head.appendChild(link);
  };

  const applyCSSVariables = (colors: BrandingColors) => {
    const root = document.documentElement;

    // Apply all color variables
    root.style.setProperty('--wl-primary', colors.primary);
    root.style.setProperty('--wl-secondary', colors.secondary);
    root.style.setProperty('--wl-accent', colors.accent);
    root.style.setProperty('--wl-background', colors.background);
    root.style.setProperty('--wl-surface', colors.surface);
    root.style.setProperty('--wl-text', colors.text);
    root.style.setProperty('--wl-text-muted', colors.textMuted);
    root.style.setProperty('--wl-success', colors.success);
    root.style.setProperty('--wl-warning', colors.warning);
    root.style.setProperty('--wl-error', colors.error);

    // Also apply to Tailwind-compatible variables if needed
    root.style.setProperty('--color-primary', colors.primary);
    root.style.setProperty('--color-secondary', colors.secondary);
    root.style.setProperty('--color-accent', colors.accent);
  };

  const applyFonts = (fonts: BrandingFonts) => {
    const root = document.documentElement;

    if (fonts.family) {
      root.style.setProperty('--wl-font-family', `'${fonts.family}', system-ui, sans-serif`);
      root.style.setProperty('--font-family-base', `'${fonts.family}', system-ui, sans-serif`);
    }

    if (fonts.heading) {
      root.style.setProperty('--wl-heading-font', `'${fonts.heading}', system-ui, sans-serif`);
      root.style.setProperty('--font-family-heading', `'${fonts.heading}', system-ui, sans-serif`);
    }

    // Import Google Fonts if needed
    if (fonts.family && !document.querySelector(`link[href*="${fonts.family}"]`)) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = `https://fonts.googleapis.com/css2?family=${fonts.family.replace(/\s+/g, '+')}&display=swap`;
      document.head.appendChild(link);
    }

    if (fonts.heading && fonts.heading !== fonts.family && !document.querySelector(`link[href*="${fonts.heading}"]`)) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = `https://fonts.googleapis.com/css2?family=${fonts.heading.replace(/\s+/g, '+')}&display=swap`;
      document.head.appendChild(link);
    }
  };

  const injectCustomCSS = (css: string) => {
    // Remove existing custom CSS
    const existingStyle = document.getElementById('whitelabel-custom-css');
    if (existingStyle) {
      existingStyle.remove();
    }

    // Inject new custom CSS
    const style = document.createElement('style');
    style.id = 'whitelabel-custom-css';
    style.textContent = css;
    document.head.appendChild(style);
  };

  useEffect(() => {
    loadBranding();
  }, []);

  return (
    <BrandingContext.Provider
      value={{
        branding,
        loading,
        error,
        refreshBranding: loadBranding,
      }}
    >
      {children}
    </BrandingContext.Provider>
  );
};

/**
 * Hook to get branding-aware component props
 *
 * Usage:
 * const { brandName, logo, colors } = useBrandingProps();
 */
export const useBrandingProps = () => {
  const { branding } = useBranding();

  return {
    brandName: branding?.brand_name || 'Ospra',
    tagline: branding?.tagline,
    logo: branding?.logo_url,
    logoDark: branding?.logo_dark_url,
    favicon: branding?.favicon_url,
    colors: branding?.colors,
    fonts: branding?.fonts,
    isWhiteLabel: branding?.whitelabel || false,
    partnerSlug: branding?.partner_slug,
    uiConfig: branding?.ui_config || {},
  };
};

/**
 * Component to display partner logo with fallback
 */
export const BrandLogo: React.FC<{
  className?: string;
  darkMode?: boolean;
  fallbackText?: string;
}> = ({ className = '', darkMode = false, fallbackText }) => {
  const { brandName, logo, logoDark } = useBrandingProps();

  const logoUrl = darkMode && logoDark ? logoDark : logo;

  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt={`${brandName} logo`}
        className={className}
      />
    );
  }

  // Fallback to text
  return (
    <span className={className}>
      {fallbackText || brandName}
    </span>
  );
};

export default BrandingContext;
