import React from 'react';
import { createRoot } from 'react-dom/client';

import { AuthProvider } from './auth/AuthContext';
import './styles.css';
import App from './App';

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>,
);
