import { StrictMode, lazy, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import './index.css';
import './aurora.css';
import App from './App.tsx';
import ErrorBoundary from './ErrorBoundary.tsx';

const PortfolioDashboard = lazy(() => import('./pages/PortfolioDashboard'));
const UnifiedProductsPage = lazy(() => import('./pages/UnifiedProductsPage').then(module => ({ default: module.UnifiedProductsPage })));
const OrdersPage = lazy(() => import('./pages/OrdersPage').then(module => ({ default: module.OrdersPage })));
const CustomerAnalyticsPage = lazy(() => import('./pages/CustomerAnalyticsPage'));
const EmailDashboard = lazy(() => import('./pages/EmailDashboard'));
const LiveTrendsPage = lazy(() => import('./pages/LiveTrendsPage'));
const RankingsPage = lazy(() => import('./pages/RankingsPage'));
const NicheAnalysisPage = lazy(() => import('./pages/NicheAnalysisPage').then(module => ({ default: module.NicheAnalysisPage })));
const CompetitiveIntelPage = lazy(() => import('./pages/CompetitiveIntelPage'));
const ABTestingPage = lazy(() => import('./pages/ABTestingPage').then(module => ({ default: module.ABTestingPage })));
const EmailSettings = lazy(() => import('./components/EmailSettings'));

const Loading = () => (
  <div className="flex justify-center items-center h-screen">
    <div className="animate-spin rounded-full h-32 w-32 border-t-2 border-b-2 border-blue-500"></div>
  </div>
);

const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { path: '/', element: <PortfolioDashboard /> },
      { path: '/products', element: <UnifiedProductsPage /> },
      { path: '/customers', element: <CustomerAnalyticsPage /> },
      { path: '/niches', element: <NicheAnalysisPage /> },
      { path: '/competitors', element: <CompetitiveIntelPage /> },
      { path: '/emails', element: <EmailDashboard /> },
      { path: '/trends', element: <LiveTrendsPage /> },
      { path: '/rankings', element: <RankingsPage /> },
      { path: '/abtesting', element: <ABTestingPage /> },
      { path: '/settings', element: <EmailSettings /> },
    ],
  },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <Suspense fallback={<Loading />}>
        <RouterProvider router={router} />
      </Suspense>
    </ErrorBoundary>
  </StrictMode>
);
