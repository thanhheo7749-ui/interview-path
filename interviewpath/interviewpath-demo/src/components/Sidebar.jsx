import { AlertTriangle, BookOpen, BrainCircuit, Briefcase, ClipboardCheck, ListChecks, ClipboardList, FileText, Users, HelpCircle, KeyRound, LogOut, MessageSquare, Network, Settings, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { useCompany } from "../company/CompanyContext.jsx";
import { useKbCounts } from "../lib/useKbCounts.js";
import LanguageSwitch from "./LanguageSwitch.jsx";

// Grouped navigation sections so daily hiring tasks, knowledge base management,
// AI assistant, and account/company configuration are clearly separated.
const navSections = [
  {
    titleKey: "nav.sections.hiring",
    items: [
      { labelKey: "nav.jobs", to: "/jobs", icon: Briefcase, hrOnly: true },
      { labelKey: "nav.candidateAccounts", to: "/candidate-accounts", icon: Users, hrOnly: true },
      { labelKey: "bridges.nav.hiringRequests", to: "/hiring-requests", icon: ClipboardList, roles: ["hr", "manager"] },
      { labelKey: "navKb.review", to: "/review", icon: ClipboardCheck, badge: "review", hrOnly: true },
      { labelKey: "bridges.nav.myInterviews", to: "/my-interviews", icon: Users, roles: ["manager"] },
      { labelKey: "onboarding.nav", to: "/my-onboarding", icon: ListChecks, roles: ["employee"] },
    ],
  },
  {
    titleKey: "nav.sections.knowledge",
    items: [
      { labelKey: "nav.graph", to: "/graph", icon: Network, hrOnly: true },
      { labelKey: "navKb.documents", to: "/documents", icon: FileText, hrOnly: true },
      { labelKey: "nav.learning", to: "/learning", icon: BookOpen, hrOnly: true },
      { labelKey: "navKb.conflicts", to: "/conflicts", icon: AlertTriangle, badge: "conflicts", hrOnly: true },
      { labelKey: "navKb.gaps", to: "/gaps", icon: HelpCircle, hrOnly: true },
      { labelKey: "trust.nav", to: "/trust", icon: ShieldCheck, hrOnly: true },
    ],
  },
  {
    titleKey: "nav.sections.assistant",
    items: [
      { labelKey: "nav.copilot", to: "/copilot", icon: MessageSquare },
    ],
  },
  {
    titleKey: "nav.sections.account",
    items: [
      { labelKey: "nav.settings", to: "/settings", icon: Settings },
      { labelKey: "nav.password", to: "/account/password", icon: KeyRound },
    ],
  },
];

function Sidebar() {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const { memberships, membership, selectCompany } = useCompany();
  const isHr = membership?.role === "hr";
  const kbCounts = useKbCounts(membership?.company_id ?? null, isHr);
  const visibleSections = navSections
    .map((section) => ({
      ...section,
      items: section.items.filter(
        (item) => (!item.hrOnly || isHr) && (!item.roles || item.roles.includes(membership?.role))
      ),
    }))
    .filter((section) => section.items.length > 0);

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-64 flex-col overflow-y-auto border-r border-slate-200 bg-white px-4 py-5 shadow-panel">
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

      <nav className="mt-6 min-h-0 flex-1 space-y-5 overflow-y-auto">
        {visibleSections.map((section) => (
          <div key={section.titleKey}>
            <p className="px-3 pb-1.5 text-[11px] font-bold uppercase tracking-[0.16em] text-slate-400">
              {t(section.titleKey)}
            </p>
            <div className="space-y-1">
              {section.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      [
                        "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold transition",
                        isActive
                          ? "bg-blue-600 text-white shadow-card"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-950",
                      ].join(" ")
                    }
                  >
                    <Icon size={18} />
                    <span className="truncate">{t(item.labelKey)}</span>
                    {item.badge && kbCounts[item.badge] > 0 && (
                      <span className="ml-auto rounded-full bg-blue-600 px-2 py-0.5 text-xs font-bold text-white">
                        {kbCounts[item.badge]}
                      </span>
                    )}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="mt-4 shrink-0 space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
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
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-3 py-3 text-sm font-bold text-white shadow-card transition hover:bg-blue-700"
        >
          <LogOut size={17} />
          {t("nav.signOut")}
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;
