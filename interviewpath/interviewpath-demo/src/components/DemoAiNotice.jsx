import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getAiStatus } from '../lib/kb.js';

// Shown whenever any AI slot runs on the fake provider, so demo output is never mistaken for a real model.
function DemoAiNotice() {
  const { t } = useTranslation();
  const [fake, setFake] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getAiStatus()
      .then((status) => {
        if (!cancelled) setFake((status?.fake_slots ?? []).length > 0);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!fake) return null;
  return (
    <div role="note" data-testid="demo-ai-notice" className="border-b border-violet-200 bg-violet-50 px-8 py-2 text-xs font-bold uppercase tracking-[0.18em] text-violet-800">
      {t('demoAi.notice')}
    </div>
  );
}

export default DemoAiNotice;
