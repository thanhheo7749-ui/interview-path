import {
  BrainCircuit,
  GitBranch,
  LayoutDashboard,
  Video,
  Workflow,
} from "lucide-react";
import { NavLink } from "react-router-dom";

const speakCvUrl = (
  import.meta.env.VITE_SPEAKCV_URL || "http://localhost:3000"
).replace(/\/$/, "");

const navItems = [
  { label: "Workflow", to: "/workflow", icon: LayoutDashboard },
  { label: "n8n Workflow", to: "/n8n", icon: Workflow },
  { label: "RAG Knowledge Graph", to: "/knowledge-graph", icon: GitBranch },
];

function Sidebar() {
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
        {navItems.map((item) => {
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
              {item.label}
            </NavLink>
          );
        })}
      </nav>

      <div className="mt-auto rounded-2xl border border-blue-100 bg-blue-50 p-4">
        <p className="text-sm font-bold text-blue-950">
          Candidate practice room
        </p>
        <p className="mt-1 text-xs leading-5 text-blue-800">
          Share the demo interview link with shortlisted candidates.
        </p>
        <button
          type="button"
          onClick={() =>
            window.open(
              `${speakCvUrl}/login?email=${encodeURIComponent("admin@gmail.com")}&password=${encodeURIComponent("admin123")}&redirect=interview`,
              "_blank",
              "noopener,noreferrer"
            )
          }
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-3 py-3 text-sm font-bold text-white shadow-card transition hover:bg-blue-700"
        >
          <Video size={17} />
          Candidate Interview Link
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;
