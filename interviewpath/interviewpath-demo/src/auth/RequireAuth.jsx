import { useTranslation } from 'react-i18next';
import { Navigate } from 'react-router-dom';
import ChangePasswordForm from '../components/ChangePasswordForm.jsx';
import { useAuth } from './AuthContext.jsx';

function CenteredPanel({ children }) {
  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-slate-100 px-4 text-slate-950">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-panel">{children}</div>
    </div>
  );
}

function RequireAuth({ children }) {
  const { token, user, loading, loadFailed, retry, logout } = useAuth();
  const { t } = useTranslation();

  if (!token) return <Navigate to="/login" replace />;
  if (loadFailed) {
    return (
      <CenteredPanel>
        <p role="alert" className="text-sm font-semibold text-red-800">
          {t('auth.loadFailed')}
        </p>
        <button
          type="button"
          onClick={retry}
          className="mt-6 w-full rounded-xl bg-blue-600 px-3 py-3 text-sm font-bold text-white shadow-card transition hover:bg-blue-700"
        >
          {t('auth.retry')}
        </button>
        <button
          type="button"
          onClick={logout}
          className="mt-3 w-full rounded-xl border border-slate-200 px-3 py-3 text-sm font-bold text-slate-700 transition hover:bg-slate-100"
        >
          {t('nav.signOut')}
        </button>
      </CenteredPanel>
    );
  }
  if (loading || !user) {
    return (
      <div role="status" className="flex min-h-[100dvh] items-center justify-center text-sm font-semibold text-slate-500">
        {t('common.loading')}
      </div>
    );
  }
  if (user.must_change_password) {
    return (
      <CenteredPanel>
        <h1 className="text-lg font-extrabold tracking-tight">{t('password.forcedTitle')}</h1>
        <p className="mt-2 text-sm text-slate-600">{t('password.forcedHint')}</p>
        <ChangePasswordForm />
        <button
          type="button"
          onClick={logout}
          className="mt-3 w-full rounded-xl border border-slate-200 px-3 py-3 text-sm font-bold text-slate-700 transition hover:bg-slate-100"
        >
          {t('nav.signOut')}
        </button>
      </CenteredPanel>
    );
  }
  return children;
}

export default RequireAuth;
