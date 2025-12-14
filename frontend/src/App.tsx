import { useEffect } from 'react';
import { AIChatProvider } from './contexts/AIChatContext';
import { ProductsProvider } from './contexts/ProductsContext';
import OspraChat from './components/OspraChat';
import Layout from './components/Layout';
import { WelcomeModal, SetupWizard } from './components/onboarding';
import { wsService } from './services/websocket';
import { useOspraStore } from './store/ospra.store';
import './index.css';

export default function App() {
  // WebSocket disabled - backend doesn't have /ws endpoint yet
  useEffect(() => {
    // Uncomment when backend WebSocket is implemented:
    // wsService.connect().catch(() => {});
    // return () => wsService.disconnect();
    console.log('[App] WebSocket disabled - using REST polling');
  }, []);

  return (
    <AIChatProvider>
      <ProductsProvider>
        <Layout />
        <OspraChat />
        <WelcomeModal />
        <SetupWizard />
      </ProductsProvider>
    </AIChatProvider>
  );
}
