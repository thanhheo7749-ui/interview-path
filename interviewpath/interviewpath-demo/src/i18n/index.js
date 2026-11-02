import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './en.json';
import ko from './ko.json';
import vi from './vi.json';

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, vi: { translation: vi }, ko: { translation: ko } },
  lng: localStorage.getItem('portal_lang') || 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

export default i18n;
