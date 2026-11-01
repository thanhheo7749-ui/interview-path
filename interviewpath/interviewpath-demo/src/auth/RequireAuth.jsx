import { useTranslation } from 'react-i18next';
import { Navigate } from 'react-router-dom';
import { useAuth } from './AuthContext.jsx';

function RequireAuth({ children }) {
  const { token, user, loading } = useAuth();
  const { t } = useTranslation();

  if (!token) return <Navigate to="/login" replace />;
  if (loading || !user) {
    return (
      <div role="status" className="flex min-h-[100dvh] items-center justify-center text-sm font-semibold text-slate-500">
        {t('common.loading')}
      </div>
    );
  }
  return children;
}

export default RequireAuth;
