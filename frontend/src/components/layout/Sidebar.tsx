import React from 'react';
import {
  LayoutDashboard,
  Globe2,
  Cpu,
  AlertOctagon,
  FlaskConical,
  RefreshCw
} from 'lucide-react';
import type { SystemHealthStatus } from '../../types';

export type NavTab = 'dashboard' | 'orbital' | 'ai' | 'risk' | 'simulation';

interface SidebarProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  activeAlertsCount: number;
  pendingApprovalsCount: number;
  health: SystemHealthStatus | null;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  activeAlertsCount,
  pendingApprovalsCount,
  health
}) => {
  const navItems = [
    {
      id: 'dashboard' as NavTab,
      label: 'Mission Control',
      badgeNum: null,
      icon: LayoutDashboard,
      description: 'Telemetry & Fleet Status'
    },
    {
      id: 'orbital' as NavTab,
      label: '3D Orbital Explorer',
      badgeNum: null,
      icon: Globe2,
      description: 'CesiumJS 3D Earth Globe'
    },
    {
      id: 'ai' as NavTab,
      label: 'AI Intelligence Center',
      badgeNum: pendingApprovalsCount > 0 ? pendingApprovalsCount : null,
      badgeColor: 'bg-cyan-700',
      icon: Cpu,
      description: 'Autonomous Agents & Chat'
    },
    {
      id: 'risk' as NavTab,
      label: 'Collision Risk Center',
      badgeNum: activeAlertsCount > 0 ? activeAlertsCount : null,
      badgeColor: 'bg-rose-600',
      icon: AlertOctagon,
      description: 'Close Approach Screening'
    },
    {
      id: 'simulation' as NavTab,
      label: 'Simulation Laboratory',
      badgeNum: null,
      icon: FlaskConical,
      description: 'What-If Trajectory Physics'
    }
  ];

  return (
    <aside className="app-sidebar w-64 border-r border-slate-800/80 bg-[#080d18]/95 flex flex-col justify-between p-4 shrink-0 select-none">
      <div className="space-y-6">
        {/* Navigation Category Label */}
        <div className="px-2">
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest font-mono">
            AEROSPACE MODULES
          </p>
        </div>

        {/* Navigation Items */}
        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`w-full text-left px-3.5 py-2.5 rounded-xl transition-all duration-150 flex items-center justify-between group ${
                  isActive
                    ? 'bg-slate-800/90 text-slate-100 border border-slate-700 shadow-md font-medium'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`p-2 rounded-lg transition-colors ${
                      isActive
                        ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20'
                        : 'bg-slate-900 text-slate-400 group-hover:text-slate-200 group-hover:bg-slate-800'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold leading-tight">{item.label}</div>
                    <div className="text-[10px] text-slate-500">{item.description}</div>
                  </div>
                </div>

                {item.badgeNum !== null && item.badgeNum > 0 && (
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-bold font-mono text-white ${
                      item.badgeColor || 'bg-slate-700'
                    }`}
                  >
                    {item.badgeNum}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Catalog Ingestion Status Footer */}
      <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800 text-xs font-mono space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider">Catalog Ingestion</span>
          <span className={`flex items-center gap-1 text-[10px] font-bold ${health?.ingestion_scheduler?.running ? 'text-emerald-400' : 'text-slate-500'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${health?.ingestion_scheduler?.running ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`} />
            {health?.ingestion_scheduler?.running ? 'RUNNING' : 'STOPPED'}
          </span>
        </div>
        <div className="text-[11px] text-slate-300 font-bold flex items-center gap-1">
          <RefreshCw className="w-3.5 h-3.5 text-sky-400" />
          <span>
            {health?.ingestion_scheduler
              ? `Every ${health.ingestion_scheduler.interval_hours}h`
              : 'Scheduler unknown'}
          </span>
        </div>
        <div className="text-[10px] text-slate-500 break-words">
          {health?.ingestion_scheduler?.groups?.length
            ? health.ingestion_scheduler.groups.join(', ')
            : 'No sync groups configured'}
        </div>
      </div>
    </aside>
  );
};
