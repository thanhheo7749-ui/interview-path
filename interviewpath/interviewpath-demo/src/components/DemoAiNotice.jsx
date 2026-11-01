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
        if (!cancelled) setFake((status.fake_slots ?? []).length > 0);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!fake) return null;
  return (
    <p role="note" data-testid="demo-ai-notice" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-xs font-bold text-amber-800">
      {t('demoAi.notice')}
    </p>
  );
}

export default DemoAiNotice;
