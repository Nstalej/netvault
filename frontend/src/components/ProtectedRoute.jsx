import { Navigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import LoadingSpinner from './ui/LoadingSpinner';

export default function ProtectedRoute({ children }) {
  const { t } = useTranslation('common');
  const { token, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <LoadingSpinner text={t('auth.loadingSession')} />;
  }

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}
