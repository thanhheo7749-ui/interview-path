import {
  Bot,
  CalendarCheck,
  Database,
  FileText,
  Gauge,
  IdCard,
  LayoutDashboard,
  ScanText,
  Send,
  Target,
} from 'lucide-react';
import { Handle, Position } from 'reactflow';

const iconMap = {
  bot: Bot,
  calendar: CalendarCheck,
  dashboard: LayoutDashboard,
  database: Database,
  file: FileText,
  gauge: Gauge,
  'id-card': IdCard,
  scan: ScanText,
  send: Send,
  target: Target,
};

const statusStyles = {
  Waiting: 'bg-slate-100 text-slate-600 ring-slate-200',
  Running: 'bg-blue-50 text-blue-700 ring-blue-200',
  Success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  Failed: 'bg-red-50 text-red-700 ring-red-200',
};

const typeStyles = {
  Trigger: 'bg-slate-950 text-white',
  'AI Processing': 'bg-blue-600 text-white',
  'AI Scoring': 'bg-violet-600 text-white',
  'Talent Memory': 'bg-emerald-600 text-white',
  Automation: 'bg-indigo-600 text-white',
  'AI Interview': 'bg-purple-600 text-white',
  Scheduling: 'bg-cyan-600 text-white',
  'HR Workspace': 'bg-slate-700 text-white',
  'Memory Storage': 'bg-green-700 text-white',
};

function N8nNode({ data, selected }) {
  const Icon = iconMap[data.icon] || FileText;
  const statusClass = statusStyles[data.status] || statusStyles.Waiting;
  const typeClass = typeStyles[data.workflowType] || 'bg-slate-700 text-white';

  return (
    <div
      className={[
        'w-[230px] rounded-2xl border bg-white p-3 shadow-card transition',
        selected ? 'border-blue-400 ring-4 ring-blue-100' : 'border-slate-200',
        data.status === 'Running' ? 'scale-[1.02]' : '',
      ].join(' ')}
    >
      <Handle type="target" position={Position.Left} className="!h-3 !w-3 !border-2 !border-white !bg-slate-400" />
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-950 text-white">
          <Icon size={19} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-extrabold text-slate-950">{data.label}</p>
          <p className="mt-1 line-clamp-2 text-[11px] font-medium leading-4 text-slate-500">{data.description}</p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2">
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-extrabold ${typeClass}`}>{data.workflowType}</span>
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-extrabold ring-1 ${statusClass}`}>{data.status}</span>
      </div>
      <Handle type="source" position={Position.Right} className="!h-3 !w-3 !border-2 !border-white !bg-blue-500" />
    </div>
  );
}

export default N8nNode;
