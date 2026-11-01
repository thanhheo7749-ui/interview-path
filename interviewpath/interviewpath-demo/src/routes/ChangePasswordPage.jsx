import { useTranslation } from 'react-i18next';
import ChangePasswordForm from '../components/ChangePasswordForm.jsx';

function ChangePasswordPage() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6 p-8">
      <h1 className="text-2xl font-extrabold tracking-tight">{t('password.title')}</h1>
      <section className="max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
        <ChangePasswordForm />
      </section>
    </div>
  );
}

export default ChangePasswordPage;
