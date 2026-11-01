import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/AuthContext.jsx';

const MIN_LENGTH = 10;

function ChangePasswordForm() {
  const { changePassword } = useAuth();
  const { t } = useTranslation();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setDone(false);
    if (next !== repeat) {
      setError(t('password.mismatch'));
      return;
    }
    setSubmitting(true);
    try {
      await changePassword(current, next);
      setCurrent('');
      setNext('');
      setRepeat('');
      setDone(true);
    } catch (err) {
      if (err.status === 401) setError(t('password.wrongCurrent'));
      else if (err.status === 422) setError(t('password.rejected'));
      else setError(t('common.genericError'));
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass =
    'mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-950 outline-none focus:border-blue-500';
  const labelClass = 'mt-4 block text-sm font-semibold text-slate-700';

  return (
    <form onSubmit={submit}>
      <label htmlFor="password-current" className={labelClass}>
        {t('password.current')}
      </label>
      <input
        id="password-current"
        type="password"
        autoComplete="current-password"
        required
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
        className={inputClass}
      />

      <label htmlFor="password-new" className={labelClass}>
        {t('password.new')}
      </label>
      <input
        id="password-new"
        type="password"
        autoComplete="new-password"
        required
        minLength={MIN_LENGTH}
        aria-describedby="password-hint"
        value={next}
        onChange={(e) => setNext(e.target.value)}
        className={inputClass}
      />
      <p id="password-hint" className="mt-1 text-xs text-slate-500">
        {t('password.hint', { count: MIN_LENGTH })}
      </p>

      <label htmlFor="password-repeat" className={labelClass}>
        {t('password.repeat')}
      </label>
      <input
        id="password-repeat"
        type="password"
        autoComplete="new-password"
        required
        value={repeat}
        onChange={(e) => setRepeat(e.target.value)}
        className={inputClass}
      />

      {error && (
        <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold text-red-800">
          {error}
        </p>
      )}
      {done && (
        <p role="status" className="mt-4 rounded-xl border border-green-200 bg-green-50 px-3 py-2 text-sm font-semibold text-green-800">
          {t('password.changed')}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="mt-6 w-full rounded-xl bg-blue-600 px-3 py-3 text-sm font-bold text-white shadow-card transition hover:bg-blue-700 disabled:opacity-60"
      >
        {submitting ? t('password.submitting') : t('password.submit')}
      </button>
    </form>
  );
}

export default ChangePasswordForm;
