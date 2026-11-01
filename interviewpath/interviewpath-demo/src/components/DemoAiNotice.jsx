import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getAiStatus } from '../lib/kb.js';

// Read once after login. Reasoning or bulk running on the fake provider means answers and extraction are simulated.
function DemoAiNotice() {
  const { t } = useTranslation();
  const [demo, setDemo] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getAiStatus()
      .then((status) => {
        const fake = status?.fake_slots ?? [];
        if (!cancelled) setDemo(fake.includes('reasoning') || fake.includes('bulk'));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!demo) return null;
  return (
    <div className="border-b border-violet-200 bg-violet-50 px-8 py-2 text-xs font-bold uppercase tracking-[0.18em] text-violet-800">
      {t('demoAi.notice')}
    </div>
  );
}

export default DemoAiNotice;
