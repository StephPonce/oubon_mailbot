import { motion } from 'framer-motion';
import { AIChatProvider } from './contexts/AIChatContext';
import { ProductsProvider } from './contexts/ProductsContext';
import GlobalAIChat from './components/GlobalAIChat';
import Layout from './components/Layout';
import './index.css';

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50" style={{ perspective: '1500px' }}>
      <AIChatProvider>
        <ProductsProvider>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8 }}
            className="relative z-10"
          >
            <Layout />
          </motion.div>
          <GlobalAIChat />
        </ProductsProvider>
      </AIChatProvider>
    </div>
  );
}
