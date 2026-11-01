import { BrainCircuit } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';
import LanguageSwitch from '../components/LanguageSwitch.jsx';

function LoginPage() {
  const { token, login } = useAuth();
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (token) return <Navigate to="/settings" replace />;

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(email.trim(), password);
    } catch (err) {
      setError(err.status === 401 || err.status === 400 ? t('login.failed') : t('common.genericError'));
      setSubmitting(false);
    }
  };

  const inputClass =
    'mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-950 outline-none focus:border-blue-500';

  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-slate-100 px-4 text-slate-950">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-panel">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-card">
            <BrainCircuit size={23} />
          </div>
          <div>
            <h1 className="text-lg font-extrabold tracking-tight">{t('login.title')}</h1>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{t('login.subtitle')}</p>
          </div>
        </div>

        <label htmlFor="login-email" className="mt-6 block text-sm font-semibold text-slate-700">
          {t('login.email')}
        </label>
        <input
          id="login-email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={inputClass}
        />

        <label htmlFor="login-password" className="mt-4 block text-sm font-semibold text-slate-700">
          {t('login.password')}
        </label>
        <input
          id="login-password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={inputClass}
        />

        {error && (
          <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold text-red-800">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="mt-6 w-full rounded-xl bg-blue-600 px-3 py-3 text-sm font-bold text-white shadow-card transition hover:bg-blue-700 disabled:opacity-60"
        >
          {submitting ? t('login.submitting') : t('login.submit')}
        </button>

        <div className="mt-6">
          <LanguageSwitch />
        </div>
      </form>
    </div>
  );
}

export default LoginPage;
