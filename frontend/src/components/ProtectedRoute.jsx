import { Navigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import LoadingSpinner from './ui/LoadingSpinner';

export default function ProtectedRoute({ children, requiredRole = null }) {
  const { t } = useTranslation('auth');
  const { user, loading, isAdmin, isEditor } = useAuth();
  const location = useLocation();

  if (loading) {
    return <LoadingSpinner text={t('session.loading')} />;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (requiredRole === 'admin' && !isAdmin()) {
    return <Navigate to="/dashboard" replace state={{ denied: true }} />;
  }

  if (requiredRole === 'editor' && !isEditor()) {
    return <Navigate to="/dashboard" replace state={{ denied: true }} />;
  }

  return children;
}
