import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, Package, ShoppingCart, Mails, BarChart, Settings, Bot, Activity, Trophy, Target, Users, PackageCheck, Search, FlaskConical, Brain } from 'lucide-react';

const navLinks = [
  { to: '/', text: 'Portfolio', icon: LayoutDashboard },
  { to: '/products', text: 'Products', icon: Package },
  { to: '/customers', text: 'Customers', icon: Users },
  { to: '/niches', text: 'Niche Analysis', icon: Target },
  { to: '/competitors', text: 'Competitors', icon: Search },
  { to: '/intelligence', text: 'Intelligence', icon: Brain },
  { to: '/emails', text: 'Emails', icon: Mails },
  { to: '/abtesting', text: 'A/B Testing', icon: FlaskConical },
  { to: '/system-health', text: 'System Health', icon: Activity },
  { to: '/settings', text: 'Settings', icon: Settings },
];

const Sidebar = () => (
  <aside className="fixed left-0 top-0 h-screen w-64 flex flex-col z-10" style={{
    background: 'rgba(255, 255, 255, 0.65)',
    backdropFilter: 'blur(24px)',
    WebkitBackdropFilter: 'blur(24px)',
    borderRight: '1px solid rgba(255, 255, 255, 0.3)',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(255, 255, 255, 0.4)'
  }}>
    <div className="flex items-center gap-3 h-20 px-6 border-b border-gray-200/50">
      <Bot className="w-8 h-8 text-gray-900" />
      <h1 className="text-xl font-light text-gray-900">Ospra OS</h1>
    </div>
    <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
      {navLinks.map((item) => (
        <NavLink
          key={item.text}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            `flex items-center gap-4 px-4 py-2.5 rounded-xl font-light transition-all ${
              isActive
                ? 'bg-gray-900 text-white shadow-lg'
                : 'text-gray-700 hover:bg-gray-200/50 hover:text-gray-900'
            }`
          }
        >
          <item.icon className="w-5 h-5" />
          <span className="text-sm">{item.text}</span>
        </NavLink>
      ))}
    </nav>
  </aside>
);

export default function Layout() {
  return (
    <div className="h-screen overflow-hidden bg-gray-50">
      <Sidebar />
      <main className="ml-64 h-screen overflow-y-auto relative z-10">
        <Outlet />
      </main>
    </div>
  );
}
