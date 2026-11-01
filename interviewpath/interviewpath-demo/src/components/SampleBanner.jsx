import { useTranslation } from 'react-i18next';
import { useCompany } from '../company/CompanyContext.jsx';

function SampleBanner() {
  const { membership } = useCompany();
  const { t } = useTranslation();
  if (!membership?.is_sample) return null;

  return (
    <div className="border-b border-amber-200 bg-amber-50 px-8 py-2 text-xs font-bold uppercase tracking-[0.18em] text-amber-800">
      {t('banner.sample')}
    </div>
  );
}

export default SampleBanner;
