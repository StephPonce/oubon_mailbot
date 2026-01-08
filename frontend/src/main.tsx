import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './contexts/AuthContext';
import { OiProvider } from './contexts/OiContext';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <OiProvider>
          <App />
        </OiProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
