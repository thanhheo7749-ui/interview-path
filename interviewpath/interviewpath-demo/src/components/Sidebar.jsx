import { AlertTriangle, BrainCircuit, Briefcase, ClipboardCheck, FileText, HelpCircle, KeyRound, LogOut, MessageSquare, Network, Settings, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { useCompany } from "../company/CompanyContext.jsx";
import { useKbCounts } from "../lib/useKbCounts.js";
import LanguageSwitch from "./LanguageSwitch.jsx";

// Knowledge base pages for HR; `badge` names a key of the counts from useKbCounts.
const kbNavItems = [
  { labelKey: "navKb.documents", to: "/documents", icon: FileText },
  { labelKey: "navKb.review", to: "/review", icon: ClipboardCheck, badge: "review" },
  { labelKey: "navKb.conflicts", to: "/conflicts", icon: AlertTriangle, badge: "conflicts" },
  { labelKey: "navKb.gaps", to: "/gaps", icon: HelpCircle },
  { labelKey: "trust.nav", to: "/trust", icon: ShieldCheck },
];

const navItems = [
  { labelKey: "nav.settings", to: "/settings", icon: Settings },
  { labelKey: "nav.graph", to: "/graph", icon: Network, hrOnly: true },
  { labelKey: "nav.jobs", to: "/jobs", icon: Briefcase, hrOnly: true },
  { labelKey: "nav.copilot", to: "/copilot", icon: MessageSquare },
  { labelKey: "nav.password", to: "/account/password", icon: KeyRound },
];

function Sidebar() {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const { memberships, membership, selectCompany } = useCompany();
  const isHr = membership?.role === "hr";
  const kbCounts = useKbCounts(membership?.company_id ?? null, isHr);
  const items = [...navItems.filter((item) => !item.hrOnly || isHr), ...(isHr ? kbNavItems : [])];

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-slate-200 bg-white px-4 py-5 shadow-panel">
      <div className="flex items-center gap-3 px-2">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-card">
          <BrainCircuit size={23} />
        </div>
        <div>
          <p className="text-lg font-extrabold tracking-tight text-slate-950">
            InterviewPath
          </p>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            Talent Memory
          </p>
        </div>
      </div>

      <nav className="mt-8 space-y-2">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                [
                  "flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition",
                  isActive
                    ? "bg-slate-950 text-white shadow-card"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-950",
                ].join(" ")
              }
            >
              <Icon size={18} />
              {t(item.labelKey)}
              {item.badge && kbCounts[item.badge] > 0 && (
                <span className="ml-auto rounded-full bg-blue-600 px-2 py-0.5 text-xs font-bold text-white">
                  {kbCounts[item.badge]}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      <div className="mt-auto space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
        {membership && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              {t("nav.company")}
            </p>
            {memberships.length > 1 ? (
              <select
                aria-label={t("nav.company")}
                value={membership.company_id}
                onChange={(e) => selectCompany(Number(e.target.value))}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-950"
              >
                {memberships.map((m) => (
                  <option key={m.company_id} value={m.company_id}>
                    {m.company_name}
                  </option>
                ))}
              </select>
            ) : (
              <p className="mt-1 text-sm font-bold text-slate-950">
                {membership.company_name}
              </p>
            )}
          </div>
        )}
        <LanguageSwitch />
        <button
          type="button"
          onClick={logout}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-slate-950 px-3 py-3 text-sm font-bold text-white shadow-card transition hover:bg-slate-800"
        >
          <LogOut size={17} />
          {t("nav.signOut")}
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;
