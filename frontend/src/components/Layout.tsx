import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, Package, ShoppingCart, Mails, BarChart, Settings, Bot, Activity, Trophy, Target, Users, PackageCheck, Search, FlaskConical } from 'lucide-react';

const navLinks = [
  { to: '/', text: 'Portfolio', icon: LayoutDashboard },
  { to: '/products', text: 'Products', icon: Package },
  { to: '/customers', text: 'Customers', icon: Users },
  { to: '/niches', text: 'Niche Analysis', icon: Target },
  { to: '/competitors', text: 'Competitors', icon: Search },
  { to: '/emails', text: 'Emails', icon: Mails },
  { to: '/trends', text: 'Live Trends', icon: Activity },
  { to: '/rankings', text: 'Rankings', icon: Trophy },
  { to: '/abtesting', text: 'A/B Testing', icon: FlaskConical },
  { to: '/settings', text: 'Settings', icon: Settings },
];

const Sidebar = () => (
  <aside className="fixed left-0 top-0 h-screen w-56 bg-gray-900 border-r border-gray-800 flex flex-col z-10">
    <div className="flex items-center gap-3 h-20 px-6 border-b border-gray-800">
      <Bot className="w-8 h-8 text-blue-500" />
      <h1 className="text-xl font-bold text-gray-100">Ospra OS</h1>
    </div>
    <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
      {navLinks.map((item) => (
        <NavLink
          key={item.text}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            `flex items-center gap-4 px-4 py-2.5 rounded-lg font-medium transition-colors ${
              isActive
                ? 'bg-blue-600 text-white shadow-lg'
                : 'text-gray-300 hover:bg-gray-800 hover:text-white'
            }`
          }
        >
          <item.icon className="w-5 h-5" />
          <span>{item.text}</span>
        </NavLink>
      ))}
    </nav>
  </aside>
);

export default function Layout() {
  return (
    <div className="min-h-screen bg-gray-950">
      {/* Aurora Background */}
      <div className="aurora-bg">
        <div className="aurora-orb orb-1"></div>
        <div className="aurora-orb orb-2"></div>
        <div className="aurora-orb orb-3"></div>
      </div>

      <Sidebar />
      <main className="ml-56 min-h-screen relative z-10">
        <Outlet />
      </main>
    </div>
  );
}
