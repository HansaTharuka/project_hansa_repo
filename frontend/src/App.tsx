import { BrowserRouter } from 'react-router-dom';

import { AuthProvider } from './auth/AuthContext';
import { AppRouter } from './router';
import './styles/global.css';

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
    </AuthProvider>
  );
}
