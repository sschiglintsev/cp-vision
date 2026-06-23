import { Navigate } from 'react-router-dom';

import { authStore } from '../../store/authStore';

interface PrivateRouteProps {
  children: React.ReactNode;
}

export const PrivateRoute = ({ children }: PrivateRouteProps) => {
  if (!authStore.isAuthenticated()) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
};
