import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { inputClass, primaryButton, secondaryButton } from '../KbFeedback.jsx';

// Chat with the JD assistant. The assistant changes wording only: a salary, a benefit or a requirement the knowledge
// graph does not hold comes back as a proposal, which HR confirms (it is then labelled as confirmed by HR) or dismisses.
function AssistantPanel({ messages, proposals, busy, onSend, onConfirm, onDismiss }) {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  const open = proposals;

  const submit = async (event) => {
    event.preventDefault();
    const message = text.trim();
    if (!message) return;
    if (await onSend(message)) setText('');
  };

  return (
    <section aria-label={t('jd.assistant.title')} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-card">
      <h2 className="text-lg font-extrabold tracking-tight">{t('jd.assistant.title')}</h2>
      <p className="text-xs text-slate-500">{t('jd.assistant.hint')}</p>
      <ul data-testid="assistant-history" className="max-h-64 space-y-2 overflow-y-auto">
        {messages.length === 0 && <li className="text-sm text-slate-500">{t('jd.assistant.empty')}</li>}
        {messages.map((message, index) => (
          <li
            key={`${message.created_at}-${index}`}
            data-testid={`assistant-${message.role}`}
            className={`rounded-xl px-3 py-2 text-sm ${message.role === 'user' ? 'bg-slate-100 text-slate-900' : 'bg-blue-50 text-blue-950'}`}
          >
            <span className="mr-1 text-xs font-bold uppercase text-slate-500">{t(`jd.assistant.role.${message.role}`)}</span>
            {message.role === 'assistant' ? message.summary || message.content : message.content}
          </li>
        ))}
      </ul>

      {open.length > 0 && (
        <ul data-testid="proposals" className="space-y-2">
          {open.map((proposal) => (
            <li key={proposal.id} data-testid="proposal" className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="font-bold">{t('jd.assistant.proposed')}</p>
              <p>{proposal.en || proposal.vi || proposal.ko}</p>
              {proposal.reason && <p className="text-xs">{proposal.reason}</p>}
              <div className="flex gap-2">
                <button type="button" disabled={busy} onClick={() => onConfirm(proposal.id)} className={primaryButton}>
                  {t('jd.assistant.confirm')}
                </button>
                <button type="button" disabled={busy} onClick={() => onDismiss(proposal.id)} className={secondaryButton}>
                  {t('jd.assistant.dismiss')}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={submit} className="flex gap-2">
        <input
          aria-label={t('jd.assistant.input')}
          value={text}
          maxLength={2000}
          onChange={(e) => setText(e.target.value)}
          placeholder={t('jd.assistant.placeholder')}
          className={`${inputClass} min-w-0 flex-1`}
        />
        <button type="submit" disabled={busy || !text.trim()} className={primaryButton}>
          {t('jd.assistant.send')}
        </button>
      </form>
    </section>
  );
}

export default AssistantPanel;
