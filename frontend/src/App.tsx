import { AIChatProvider } from './contexts/AIChatContext';
import { ProductsProvider } from './contexts/ProductsContext';
import GlobalAIChat from './components/GlobalAIChat';
import Layout from './components/Layout';

export default function App() {
  return (
    <AIChatProvider>
      <ProductsProvider>
        <Layout />
        <GlobalAIChat />
      </ProductsProvider>
    </AIChatProvider>
  );
}
