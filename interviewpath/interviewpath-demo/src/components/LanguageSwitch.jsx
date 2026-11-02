import { useTranslation } from 'react-i18next';

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'vi', label: 'Tiếng Việt' },
  { code: 'ko', label: '한국어' },
];

function LanguageSwitch() {
  const { i18n } = useTranslation();

  const choose = (code) => {
    localStorage.setItem('portal_lang', code);
    i18n.changeLanguage(code);
  };

  return (
    <div className="flex gap-2">
      {LANGUAGES.map(({ code, label }) => (
        <button
          key={code}
          type="button"
          onClick={() => choose(code)}
          aria-pressed={i18n.language === code}
          className={[
            'flex-1 rounded-xl px-3 py-2 text-xs font-bold transition',
            i18n.language === code
              ? 'bg-slate-950 text-white'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
          ].join(' ')}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export default LanguageSwitch;
