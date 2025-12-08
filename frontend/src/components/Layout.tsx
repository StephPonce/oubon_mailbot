import { useState } from 'react';
import { useNavigate, useLocation, Routes, Route, Navigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Package,
  Mail,
  Settings,
  Brain,
  Activity,
  Target,
  Users,
  Search,
  FlaskConical,
  TrendingUp,
  CreditCard,
  ChevronRight,
  Zap,
  Menu,
  X,
  Bell,
  LogOut,
  Eye,
  Bot,
  ShoppingBag
} from 'lucide-react';

// Import all pages
import PortfolioDashboard from '../pages/PortfolioDashboard';
import UnifiedProductsPage from '../pages/UnifiedProductsPage';
import LiveTrendsPage from '../pages/LiveTrendsPage';
import IntelligencePage from '../pages/IntelligencePage';
import NicheAnalysisPage from '../pages/NicheAnalysisPage';
import CompetitiveIntelPage from '../pages/CompetitiveIntelPage';
import CustomerAnalyticsPage from '../pages/CustomerAnalyticsPage';
import EmailDashboard from '../pages/EmailDashboard';
import ABTestingPage from '../pages/ABTestingPage';
import SystemHealthPage from '../pages/SystemHealthPage';
import AutoDeploymentPage from '../pages/AutoDeploymentPage';
import ShopifyPage from '../pages/ShopifyPage';
import { ErrorBoundary } from './ErrorBoundary';

// Navigation items with routes
const mainNavItems = [
  { id: 'dashboard', path: '/', icon: LayoutDashboard, label: 'Command Center' },
  { id: 'products', path: '/products', icon: Package, label: 'Product Discovery' },
  { id: 'trends', path: '/trends', icon: TrendingUp, label: 'Live Trends', badge: 'Live' },
  { id: 'intelligence', path: '/intelligence', icon: Brain, label: 'Ospra Intelligence' },
  { id: 'niches', path: '/niches', icon: Target, label: 'Niche Analysis' },
  { id: 'competitors', path: '/competitors', icon: Eye, label: 'Competitors' },
];

const operationsNavItems = [
  { id: 'shopify', path: '/shopify', icon: ShoppingBag, label: 'Shopify Store' },
  { id: 'auto-deploy', path: '/auto-deploy', icon: Bot, label: 'Auto-Deployment', badge: 'New' },
  { id: 'customers', path: '/customers', icon: Users, label: 'Customer Analytics' },
  { id: 'email', path: '/email', icon: Mail, label: 'Email Automation' },
  { id: 'testing', path: '/testing', icon: FlaskConical, label: 'A/B Testing' },
  { id: 'health', path: '/health', icon: Activity, label: 'System Health' },
];

const bottomNavItems = [
  { id: 'subscription', path: '/subscription', icon: CreditCard, label: 'Subscription' },
  { id: 'settings', path: '/settings', icon: Settings, label: 'Settings' },
];

// Nav Section Component
function NavSection({ title, items, activePath, onSelect }: {
  title: string;
  items: typeof mainNavItems;
  activePath: string;
  onSelect: (path: string) => void;
}) {
  return (
    <div className="mb-6">
      <div className="px-4 mb-2">
        <span className="text-[11px] font-medium text-secondary uppercase tracking-wider">
          {title}
        </span>
      </div>
      <nav className="space-y-1 px-2">
        {items.map((item) => {
          const isActive = activePath === item.path || (item.path === '/' && activePath === '/');
          return (
            <button
              key={item.id}
              onClick={() => onSelect(item.path)}
              className={`nav-item w-full ${isActive ? 'active' : ''}`}
            >
              <item.icon className="w-[18px] h-[18px]" />
              <span className="flex-1 text-left">{item.label}</span>
              {'badge' in item && item.badge && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-500/20 text-green-600 border border-green-500/30">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>
    </div>
  );
}

// Sidebar Component
function Sidebar({
  isOpen,
  onClose,
  activePath,
  onSelect
}: {
  isOpen: boolean;
  onClose: () => void;
  activePath: string;
  onSelect: (path: string) => void;
}) {
  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 h-full w-[260px] z-50
        flex flex-col
        transition-transform duration-300 ease-out
        lg:translate-x-0
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `}
      style={{
        background: 'rgba(255, 255, 255, 0.5)',
        backdropFilter: 'blur(40px) saturate(180%)',
        WebkitBackdropFilter: 'blur(40px) saturate(180%)',
        borderRight: '1px solid rgba(255, 255, 255, 0.5)',
      }}
      >
        {/* Logo */}
        <div className="h-16 flex items-center gap-3 px-4 border-b border-black/5">
          <div className="stat-card-icon blue">
            <Zap className="w-5 h-5" />
          </div>
          <span className="text-base font-semibold text-primary">Ospra Intelligence</span>
          
          {/* Mobile close button */}
          <button
            onClick={onClose}
            className="ml-auto p-2 rounded-lg hover:bg-black/5 text-secondary lg:hidden"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation */}
        <div className="flex-1 overflow-y-auto py-2">
          <NavSection
            title="Overview"
            items={mainNavItems}
            activePath={activePath}
            onSelect={onSelect}
          />
          <NavSection
            title="Operations"
            items={operationsNavItems}
            activePath={activePath}
            onSelect={onSelect}
          />
        </div>

        {/* Bottom Section */}
        <div className="p-4 border-t border-black/5">
          {/* Tier Badge */}
          <div className="mb-4 p-3 rounded-xl bg-white/50 border border-black/10">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-blue" />
              <span className="text-sm font-medium badge-blue">Stratosphere</span>
            </div>
          </div>

          {/* Bottom Nav */}
          <nav className="space-y-1">
            {bottomNavItems.map((item) => {
              const isActive = activePath === item.path;
              return (
                <button
                  key={item.id}
                  onClick={() => onSelect(item.path)}
                  className={`nav-item w-full ${isActive ? 'active' : ''}`}
                >
                  <item.icon className="w-[18px] h-[18px]" />
                  <span className="flex-1 text-left">{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* User */}
          <div className="mt-4 pt-4 border-t border-black/5">
            <div className="flex items-center gap-3">
              <div className="stat-card-icon blue">
                <span className="text-sm font-medium">S</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-primary truncate">Steph</div>
                <div className="text-xs text-secondary truncate">steph@ospra.io</div>
              </div>
              <button className="p-2 rounded-lg hover:bg-black/5 text-secondary hover:text-primary">
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}

// Top Bar Component
function TopBar({ onMenuClick }: { onMenuClick: () => void }) {
  return (
    <header
      className="h-16 sticky top-0 z-30 flex items-center justify-between px-4 lg:px-6"
      style={{
        background: 'rgba(255, 255, 255, 0.5)',
        backdropFilter: 'blur(40px) saturate(180%)',
        WebkitBackdropFilter: 'blur(40px) saturate(180%)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.5)',
      }}
    >
      <div className="flex items-center gap-4">
        {/* Mobile menu button */}
        <button
          onClick={onMenuClick}
          className="p-2 rounded-lg hover:bg-black/5 text-secondary lg:hidden"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Search */}
        <div className="relative hidden sm:block">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-secondary" />
          <input
            type="text"
            placeholder="Search products, niches, analytics..."
            className="w-64 lg:w-80 pl-10 pr-4 py-2 rounded-xl bg-white/50 border border-black/10 text-sm text-primary placeholder-text-tertiary outline-none focus:border-apple-blue transition-colors"
          />
          <div className="absolute right-3 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded bg-black/5 text-[10px] text-tertiary">
            /
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Notifications */}
        <button className="relative p-2 rounded-xl hover:bg-black/5 text-secondary">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-status-blue" />
        </button>
      </div>
    </header>
  );
}

// Routes Component
function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<PortfolioDashboard />} />
      <Route path="/products" element={<UnifiedProductsPage />} />
      <Route path="/trends" element={<LiveTrendsPage />} />
      <Route path="/intelligence" element={<IntelligencePage />} />
      <Route path="/niches" element={<NicheAnalysisPage />} />
      <Route path="/competitors" element={<CompetitiveIntelPage />} />
      <Route path="/shopify" element={<ShopifyPage />} />
      <Route path="/auto-deploy" element={<AutoDeploymentPage />} />
      <Route path="/customers" element={<CustomerAnalyticsPage />} />
      <Route path="/email" element={<EmailDashboard />} />
      <Route path="/testing" element={<ABTestingPage />} />
      <Route path="/health" element={<SystemHealthPage />} />
      <Route path="/subscription" element={<SubscriptionPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      {/* Redirect any unknown routes to dashboard */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

// Placeholder pages
function SubscriptionPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold text-primary mb-2">Subscription</h1>
      <p className="text-sm text-secondary mb-6">Manage your plan and billing</p>

      <div className="glass-card p-6">
        <div className="flex items-center gap-4 mb-4">
          <div className="stat-card-icon blue" style={{ width: '48px', height: '48px' }}>
            <Zap className="w-6 h-6" />
          </div>
          <div>
            <div className="text-lg font-semibold text-primary">Stratosphere Plan</div>
            <div className="text-sm text-secondary">$199/month - Unlimited everything</div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-white/30 border border-black/5">
            <div className="text-xs text-secondary mb-1">AI Searches</div>
            <div className="text-lg font-semibold text-primary">Unlimited</div>
          </div>
          <div className="p-4 rounded-xl bg-white/30 border border-black/5">
            <div className="text-xs text-secondary mb-1">Product Deploys</div>
            <div className="text-lg font-semibold text-primary">Unlimited</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SettingsPage() {
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [pushNotifications, setPushNotifications] = useState(false);
  const [autoSync, setAutoSync] = useState(true);
  const [darkMode, setDarkMode] = useState(false);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold text-primary mb-2">Settings</h1>
      <p className="text-sm text-secondary mb-6">Configure your Ospra Intelligence dashboard</p>

      <div className="space-y-6">
        {/* Notifications */}
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-primary mb-4">Notifications</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-primary">Email Notifications</div>
                <div className="text-xs text-secondary">Receive email alerts for important events</div>
              </div>
              <button
                onClick={() => setEmailNotifications(!emailNotifications)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  emailNotifications ? 'bg-accent' : 'bg-black/20'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    emailNotifications ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-primary">Push Notifications</div>
                <div className="text-xs text-secondary">Browser notifications for real-time updates</div>
              </div>
              <button
                onClick={() => setPushNotifications(!pushNotifications)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  pushNotifications ? 'bg-accent' : 'bg-black/20'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    pushNotifications ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>
        </div>

        {/* Automation */}
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-primary mb-4">Automation</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-primary">Auto-Sync Emails</div>
                <div className="text-xs text-secondary">Automatically sync emails every 5 minutes</div>
              </div>
              <button
                onClick={() => setAutoSync(!autoSync)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  autoSync ? 'bg-accent' : 'bg-black/20'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    autoSync ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>
        </div>

        {/* Appearance */}
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-primary mb-4">Appearance</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-primary">Dark Mode</div>
                <div className="text-xs text-secondary">Switch to dark theme (Coming soon)</div>
              </div>
              <button
                onClick={() => setDarkMode(!darkMode)}
                disabled
                className="relative inline-flex h-6 w-11 items-center rounded-full bg-black/10 opacity-50 cursor-not-allowed"
              >
                <span className="inline-block h-4 w-4 transform rounded-full bg-white translate-x-1" />
              </button>
            </div>
          </div>
        </div>

        {/* Integrations */}
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-primary mb-4">Integrations</h2>
          <div className="space-y-3">
            {[
              { name: 'Shopify', status: 'Connected', color: 'green' },
              { name: 'Google Analytics', status: 'Not Connected', color: 'gray' },
              { name: 'Slack', status: 'Not Connected', color: 'gray' },
            ].map((integration) => (
              <div key={integration.name} className="flex items-center justify-between p-3 rounded-lg bg-white/30 border border-black/5">
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full bg-${integration.color}-500`} />
                  <span className="text-sm text-primary">{integration.name}</span>
                </div>
                <span className="text-xs text-secondary">{integration.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// Main Layout Component
export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const handleSelect = (path: string) => {
    navigate(path);
    setSidebarOpen(false);
  };

  return (
    <div className="min-h-screen">
      {/* Liquid Glass Background - Colorful gradient that bleeds through */}
      <div className="app-background" />

      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        activePath={location.pathname}
        onSelect={handleSelect}
      />

      {/* Main Content */}
      <div className="lg:ml-[260px]">
        <TopBar onMenuClick={() => setSidebarOpen(true)} />
        <main className="min-h-[calc(100vh-64px)] relative">
          <ErrorBoundary>
            <AppRoutes />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
