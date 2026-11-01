import { Copy } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CHANNEL_PATTERN, channelUrl } from '../lib/jobs.js';
import { ErrorAlert, inputClass, secondaryButton } from './KbFeedback.jsx';

// One tracked link per channel of a published job. `onAdd(channel)` creates a new channel.
function ChannelLinks({ slug, channels, onAdd }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(null);
  const [name, setName] = useState('');
  const [error, setError] = useState('');

  const copy = async (channel) => {
    setError('');
    try {
      await navigator.clipboard.writeText(channelUrl(slug, channel.token));
      setCopied(channel.id);
    } catch {
      setError(t('jobs.copyFailed'));
    }
  };

  const add = async (event) => {
    event.preventDefault();
    const channel = name.trim();
    if (!CHANNEL_PATTERN.test(channel)) {
      setError(t('jobs.channelInvalid'));
      return;
    }
    setError('');
    try {
      await onAdd(channel);
      setName('');
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <section className="space-y-3" data-testid="channel-links">
      <h2 className="text-lg font-extrabold tracking-tight">{t('jobs.channelsTitle')}</h2>
      <p className="text-xs text-slate-500">{t('jobs.channelsHint')}</p>
      <ErrorAlert message={error} />
      {channels.length === 0 ? (
        <p className="text-sm font-semibold text-slate-600">{t('jobs.noChannels')}</p>
      ) : (
        <ul className="space-y-2">
          {channels.map((channel) => (
            <li key={channel.id} data-testid={`channel-${channel.channel}`} className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <span className="w-32 text-sm font-bold text-slate-900">{channel.channel}</span>
              <code className="min-w-0 flex-1 break-all text-xs text-slate-700">{channelUrl(slug, channel.token)}</code>
              <span className="text-xs font-semibold text-slate-500">{t('jobs.clicks', { count: channel.click_count })}</span>
              <button type="button" onClick={() => copy(channel)} aria-label={`${t('jobs.copy')} ${channel.channel}`} className={`${secondaryButton} flex items-center gap-2`}>
                <Copy size={14} />
                {copied === channel.id ? t('jobs.copied') : t('jobs.copy')}
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={add} className="flex flex-wrap items-end gap-3">
        <label className="text-sm font-semibold text-slate-700">
          <span className="block">{t('jobs.newChannel')}</span>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={50} className={`${inputClass} mt-1`} />
        </label>
        <button type="submit" className={secondaryButton}>
          {t('jobs.addChannel')}
        </button>
      </form>
    </section>
  );
}

export default ChannelLinks;
