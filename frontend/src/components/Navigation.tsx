import { Link, useLocation } from 'react-router-dom';
import { NotificationBell } from './NotificationBell';

export const Navigation = () => {
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path
      ? 'bg-blue-700'
      : 'hover:bg-blue-700';
  };

  return (
    <nav className="bg-blue-600 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-8">
            <h1 className="text-2xl font-bold">Ospra Intelligence</h1>
            <div className="flex gap-2">
              <Link
                to="/"
                className={`px-4 py-2 rounded font-semibold transition ${isActive('/')}`}
              >
                📦 Products
              </Link>
              <Link
                to="/orders"
                className={`px-4 py-2 rounded font-semibold transition ${isActive('/orders')}`}
              >
                🛒 Orders
              </Link>
            </div>
          </div>
          <NotificationBell />
        </div>
      </div>
    </nav>
  );
};
