import { Copy } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ErrorAlert, cardClass, primaryButton, secondaryButton } from '../KbFeedback.jsx';

// Recruiting text for each channel of a published job, with its tracked link. HR copies the text and posts it by hand:
// there is no posting button, because this system never posts to a job board.
function ChannelContent({ channels, busy, error, onGenerate }) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState(null);
  const [copied, setCopied] = useState('');
  const [copyError, setCopyError] = useState('');
  const active = channels.find((c) => c.channel === selected) ?? channels[0];

  const copy = async (what, text) => {
    setCopyError('');
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
    } catch {
      setCopyError(t('jd.channels.copyFailed'));
    }
  };

  return (
    <section data-testid="channel-content" className={`${cardClass} space-y-4`}>
      <h2 className="text-lg font-extrabold tracking-tight">{t('jd.channels.title')}</h2>
      <p data-testid="manual-post-notice" className="text-sm font-semibold text-slate-700">
        {t('jd.channels.manualNotice')}
      </p>
      <ErrorAlert message={error || copyError} />
      {channels.length === 0 && (
        <button type="button" disabled={busy} onClick={onGenerate} className={primaryButton}>
          {t('jd.channels.generate')}
        </button>
      )}
      {channels.length > 0 && (
        <>
          <button type="button" disabled={busy} onClick={onGenerate} data-testid="regenerate-channels" className={secondaryButton}>
            {t('jd.channels.regenerate')}
          </button>
          <div role="tablist" aria-label={t('jd.channels.title')} className="flex flex-wrap gap-2">
            {channels.map((item) => (
              <button
                key={item.channel}
                role="tab"
                type="button"
                aria-selected={active?.channel === item.channel}
                onClick={() => setSelected(item.channel)}
                className={`rounded-xl px-3 py-2 text-sm font-bold ${active?.channel === item.channel ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700'}`}
              >
                {t(`jd.channels.names.${item.channel}`, { defaultValue: item.channel })}
                {item.used_template && <span aria-hidden="true" title={t('jd.channels.usedTemplate')}> *</span>}
              </button>
            ))}
          </div>
          {active && (
            <div role="tabpanel" data-testid={`channel-panel-${active.channel}`} className="space-y-3">
              {active.used_template && (
                <p data-testid="template-notice" className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900">
                  {t('jd.channels.usedTemplate')}
                </p>
              )}
              <p className="text-xs font-semibold text-slate-500">
                {t('jd.channels.language', { language: t(`jd.channels.languages.${active.language}`, { defaultValue: active.language }) })}
              </p>
              <pre data-testid="channel-body" className="whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-900">
                {active.body}
              </pre>
              {active.link && (
                <div className="flex flex-wrap items-center gap-3">
                  <a data-testid="channel-link" href={active.link.url} target="_blank" rel="noreferrer" className="min-w-0 flex-1 break-all text-xs font-semibold text-blue-700 underline">
                    {active.link.url}
                  </a>
                  <button
                    type="button"
                    aria-label={t('jd.channels.copyLink', { channel: active.channel })}
                    onClick={() => copy(`link-${active.channel}`, active.link.url)}
                    className={`${secondaryButton} flex items-center gap-2`}
                  >
                    <Copy size={14} />
                    {copied === `link-${active.channel}` ? t('jd.channels.copied') : t('jd.channels.copyLinkShort')}
                  </button>
                </div>
              )}
              <button
                type="button"
                aria-label={t('jd.channels.copyText', { channel: active.channel })}
                onClick={() => copy(`text-${active.channel}`, active.body)}
                className={`${secondaryButton} flex items-center gap-2`}
              >
                <Copy size={14} />
                {copied === `text-${active.channel}` ? t('jd.channels.copied') : t('jd.channels.copyTextShort')}
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}

export default ChannelContent;
