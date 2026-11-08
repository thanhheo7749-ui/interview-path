import { Check, Copy, ExternalLink, Eye, EyeOff, KeyRound, Mail, RefreshCw, Search, ShieldCheck, UserCheck, Users } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useCompany } from '../company/CompanyContext.jsx';
import { ErrorAlert } from '../components/KbFeedback.jsx';
import {
  CANDIDATE_PORTAL_URL,
  getCandidateAccounts,
  getCandidateAvatarUrl,
  getCandidateInitials,
  getCandidatePalette,
  resetCandidateCredentials,
} from '../lib/board.js';
import { listJobs } from '../lib/jobs.js';

const STAGE_BADGE = {
  invited: 'bg-blue-50 text-blue-700 border-blue-200',
  session_in_progress: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  ready_for_hr: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  in_manager_round: 'bg-violet-50 text-violet-700 border-violet-200',
  cv_hold: 'bg-amber-50 text-amber-800 border-amber-200',
  missing_contact: 'bg-rose-50 text-rose-700 border-rose-200',
};

function CandidateAccountRow({ item, companyId, onReload }) {
  const { t } = useTranslation();
  const [showPw, setShowPw] = useState(false);
  const [copiedKey, setCopiedKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [imgErr, setImgErr] = useState(false);
  const [customPw, setCustomPw] = useState('');
  const [editingPw, setEditingPw] = useState(false);

  const [fg, bg] = getCandidatePalette(item.application_id);
  const initials = getCandidateInitials(item.candidate_name, item.alias);
  const magicLink = item.claim_token ? `${CANDIDATE_PORTAL_URL}/claim/${item.claim_token}` : '';
  const loginUrl = `${CANDIDATE_PORTAL_URL}/login`;

  const copyText = (key, text) => {
    navigator.clipboard?.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(''), 2000);
  };

  const copyFullPackage = () => {
    const pkg = [
      `Ứng viên: ${item.candidate_name || item.alias} (${item.alias})`,
      `Vị trí: ${item.job_title}`,
      `Cổng đăng nhập vòng 1 AI: ${loginUrl}`,
      `Email tài khoản: ${item.candidate_email || 'Chưa có'}`,
      `Mật khẩu mặc định: ${item.default_password || 'N/A'}`,
      `Link vào thẳng phòng thi (1-Click Magic Link): ${magicLink}`,
    ].join('\n');
    copyText('pkg', pkg);
  };

  const handleResetAndSend = async (e) => {
    if (e) e.preventDefault();
    setBusy(true);
    try {
      await resetCandidateCredentials(companyId, item.application_id, {
        password: customPw.trim() || null,
        send_email: true,
      });
      setEditingPw(false);
      setCustomPw('');
      setCopiedKey('sent');
      setTimeout(() => setCopiedKey(''), 2500);
      await onReload();
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr className="border-t border-slate-100 hover:bg-slate-50/80">
      <td className="px-4 py-3.5">
        <div className="flex items-center gap-3">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full border border-slate-200 text-xs font-extrabold"
            style={{ backgroundColor: bg, color: fg }}
          >
            {!imgErr ? (
              <img
                src={getCandidateAvatarUrl(item.candidate_name, item.alias, item.application_id)}
                alt={item.candidate_name || item.alias}
                className="h-full w-full object-cover"
                onError={() => setImgErr(true)}
              />
            ) : (
              <span>{initials}</span>
            )}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-extrabold text-slate-900">
              {item.candidate_name || item.alias}
              <span className="ml-1.5 text-xs font-semibold text-slate-400">({item.alias})</span>
            </p>
            <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
              {item.candidate_phone && <span>{item.candidate_phone}</span>}
              {item.source_channel && (
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-slate-600">
                  {item.source_channel}
                </span>
              )}
            </div>
          </div>
        </div>
      </td>

      <td className="px-4 py-3.5">
        <p className="text-xs font-bold text-slate-900">{item.job_title}</p>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <span
            className={`inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${
              STAGE_BADGE[item.stage] || 'border-slate-200 bg-slate-100 text-slate-700'
            }`}
          >
            {t(`board.stage.${item.stage}`, { defaultValue: item.stage })}
          </span>
          {item.final_outcome && (
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold uppercase text-emerald-800">
              {item.final_outcome}
            </span>
          )}
        </div>
      </td>

      <td className="px-4 py-3.5">
        {item.account_created && item.candidate_email ? (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs">
              <span className="font-semibold text-slate-500">Email:</span>
              <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs font-bold text-slate-900">
                {item.candidate_email}
              </code>
              <button
                type="button"
                onClick={() => copyText('email', item.candidate_email)}
                className="rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-700"
                title="Copy Email"
              >
                {copiedKey === 'email' ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
              </button>
            </div>
            <div className="flex items-center gap-1.5 text-xs">
              <span className="font-semibold text-slate-500">Mật khẩu:</span>
              <code className="rounded bg-blue-50 px-1.5 py-0.5 font-mono text-xs font-bold text-blue-800">
                {showPw ? item.default_password : '••••••••••'}
              </code>
              <button
                type="button"
                onClick={() => setShowPw((v) => !v)}
                className="rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-700"
                title={showPw ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
              >
                {showPw ? <EyeOff size={13} /> : <Eye size={13} />}
              </button>
              <button
                type="button"
                onClick={() => copyText('pw', item.default_password)}
                className="rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-700"
                title="Copy mật khẩu"
              >
                {copiedKey === 'pw' ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
              </button>
            </div>
          </div>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-lg bg-rose-50 px-2.5 py-1 text-xs font-bold text-rose-700">
            Chưa có Email trong CV (Cần bổ sung trên Board)
          </span>
        )}
      </td>

      <td className="px-4 py-3.5">
        {item.account_created ? (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                onClick={() => copyText('magic', magicLink)}
                className="inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700 hover:bg-blue-100"
              >
                {copiedKey === 'magic' ? <Check size={13} /> : <Copy size={13} />}
                {copiedKey === 'magic' ? 'Đã copy Magic Link!' : 'Copy Magic Link 1-Click'}
              </button>
              <a
                href={magicLink}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-bold text-slate-700 hover:bg-slate-100"
                title="Mở thử phòng chờ phỏng vấn AI của thí sinh này"
              >
                <ExternalLink size={13} />
                Vào phòng thi
              </a>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                onClick={copyFullPackage}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-bold text-slate-700 hover:bg-slate-100"
              >
                {copiedKey === 'pkg' ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                {copiedKey === 'pkg' ? 'Đã copy trọn bộ!' : 'Copy trọn bộ TK + Link'}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setEditingPw((v) => !v)}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-bold text-slate-700 hover:bg-slate-100"
              >
                <KeyRound size={12} />
                Đặt lại MK / Gửi mail
              </button>
              <Link
                to={`/jobs/${item.job_id}/board`}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-bold text-slate-600 hover:bg-slate-100"
              >
                Xem trên Board
              </Link>
            </div>
            {copiedKey === 'sent' && (
              <p className="text-[11px] font-bold text-emerald-700">
                ✓ Đã cập nhật mật khẩu & gửi Email kèm Magic Link tới hộp thư ứng viên!
              </p>
            )}
            {editingPw && (
              <form onSubmit={handleResetAndSend} className="mt-2 flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white p-2">
                <input
                  type="text"
                  placeholder={item.default_password || 'Mật khẩu mới...'}
                  value={customPw}
                  onChange={(e) => setCustomPw(e.target.value)}
                  className="w-36 rounded-lg border border-slate-200 px-2 py-1 text-xs"
                />
                <button
                  type="submit"
                  disabled={busy}
                  className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-2.5 py-1 text-xs font-bold text-white hover:bg-blue-700"
                >
                  <Mail size={12} />
                  {busy ? 'Đang gửi...' : 'Lưu & Gửi mail'}
                </button>
              </form>
            )}
          </div>
        ) : (
          <Link
            to={`/jobs/${item.job_id}/board`}
            className="inline-flex items-center gap-1 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-amber-700"
          >
            Bổ sung Email trên Board
          </Link>
        )}
      </td>
    </tr>
  );
}

function CandidateAccountsPage() {
  const { t } = useTranslation();
  const { membership } = useCompany();
  const companyId = membership?.company_id;
  const [items, setItems] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    setError('');
    try {
      const [accRes, jobsRes] = await Promise.all([
        getCandidateAccounts(companyId, selectedJobId || null),
        listJobs(companyId),
      ]);
      setItems(accRes.items || []);
      setJobs(jobsRes || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [companyId, selectedJobId]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (item) =>
        (item.candidate_name || '').toLowerCase().includes(q) ||
        (item.candidate_email || '').toLowerCase().includes(q) ||
        (item.candidate_phone || '').toLowerCase().includes(q) ||
        (item.alias || '').toLowerCase().includes(q) ||
        (item.source_channel || '').toLowerCase().includes(q)
    );
  }, [items, search]);

  const stats = useMemo(() => {
    const total = items.length;
    const created = items.filter((i) => i.account_created).length;
    const invitedOrDone = items.filter((i) =>
      ['invited', 'session_in_progress', 'ready_for_hr', 'in_manager_round'].includes(i.stage)
    ).length;
    const missing = items.filter((i) => !i.account_created || i.stage === 'missing_contact').length;
    return { total, created, invitedOrDone, missing };
  }, [items]);

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-600">
            OMNI-CHANNEL AUTO-PROVISIONING
          </p>
          <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-950">
            {t('candidateAccounts.title', { defaultValue: 'Quản lý Tài khoản Thí sinh ( Tự động tạo từ CV )' })}
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-600">
            {t('candidateAccounts.subtitle', {
              defaultValue:
                'Khi ứng viên nộp CV hoặc HR tải lên CV đa kênh (.pdf / .docx / .zip), hệ thống tự động trích xuất Email để khởi tạo Tài khoản Thí sinh (kèm Mật khẩu mặc định & 1-Click Magic Link) phục vụ Vòng 1 Phỏng vấn với AI.',
            })}
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-700 shadow-card hover:bg-slate-50"
        >
          <RefreshCw size={15} />
          Làm mới danh sách
        </button>
      </div>

      <ErrorAlert message={error} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Tổng hồ sơ CV</span>
            <Users size={18} className="text-slate-400" />
          </div>
          <p className="mt-2 text-2xl font-extrabold text-slate-950">{stats.total}</p>
          <p className="mt-1 text-xs text-slate-500">Từ tất cả các kênh tuyển dụng</p>
        </div>

        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-5 shadow-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-700">Đã tự động tạo Tài khoản</span>
            <UserCheck size={18} className="text-emerald-600" />
          </div>
          <p className="mt-2 text-2xl font-extrabold text-emerald-900">{stats.created}</p>
          <p className="mt-1 text-xs text-emerald-700">Có sẵn Email + Mật khẩu + Magic Link</p>
        </div>

        <div className="rounded-2xl border border-blue-200 bg-blue-50/50 p-5 shadow-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-blue-700">Đủ điều kiện Vòng 1 AI</span>
            <ShieldCheck size={18} className="text-blue-600" />
          </div>
          <p className="mt-2 text-2xl font-extrabold text-blue-900">{stats.invitedOrDone}</p>
          <p className="mt-1 text-xs text-blue-700">Đã mở phòng phỏng vấn AI</p>
        </div>

        <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-5 shadow-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-amber-800">CV thiếu Email</span>
            <Mail size={18} className="text-amber-600" />
          </div>
          <p className="mt-2 text-2xl font-extrabold text-amber-900">{stats.missing}</p>
          <p className="mt-1 text-xs text-amber-800">Chờ HR nhập bổ sung Email để tạo TK</p>
        </div>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 p-4">
          <div className="relative min-w-64 flex-1 max-w-md">
            <Search size={16} className=" absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              placeholder="Tìm theo họ tên, email, SĐT, mã #A1, nguồn TopCV/ITviec..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-xs font-medium text-slate-900 outline-none focus:border-blue-500 focus:bg-white"
            />
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="job-filter" className="text-xs font-bold text-slate-600">
              Vị trí:
            </label>
            <select
              id="job-filter"
              value={selectedJobId}
              onChange={(e) => setSelectedJobId(e.target.value)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-800"
            >
              <option value="">Tất cả vị trí ({jobs.length})</option>
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title}
                </option>
              ))}
            </select>
          </div>
        </div>

        {loading ? (
          <p className="p-8 text-center text-sm text-slate-500">Đang tải danh sách tài khoản thí sinh...</p>
        ) : filtered.length === 0 ? (
          <p className="p-8 text-center text-sm text-slate-500">Không tìm thấy tài khoản thí sinh nào phù hợp.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 text-[11px] font-extrabold uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3">Thí sinh & Nguồn CV</th>
                  <th className="px-4 py-3">Vị trí & Trạng thái</th>
                  <th className="px-4 py-3">Tài khoản Tự động tạo (Cổng 3001)</th>
                  <th className="px-4 py-3">Link Vòng 1 AI & Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <CandidateAccountRow key={item.application_id} item={item} companyId={companyId} onReload={load} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default CandidateAccountsPage;
