import React from 'react';
import {
  LayoutDashboard,
  Globe2,
  Cpu,
  AlertOctagon,
  FlaskConical,
  Wifi,
  Radio,
  FileText
} from 'lucide-react';

export type NavTab = 'dashboard' | 'orbital' | 'ai' | 'risk' | 'simulation';

interface SidebarProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  activeAlertsCount: number;
  pendingApprovalsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  activeAlertsCount,
  pendingApprovalsCount
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
      badgeColor: 'bg-purple-500',
      icon: Cpu,
      description: 'Autonomous Agents & Chat'
    },
    {
      id: 'risk' as NavTab,
      label: 'Collision Risk Center',
      badgeNum: activeAlertsCount > 0 ? activeAlertsCount : null,
      badgeColor: 'bg-rose-500',
      icon: AlertOctagon,
      description: 'CARA Risk Ranking & B-Plane'
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
    <aside className="w-64 border-r border-slate-800/80 bg-[#070b14]/95 flex flex-col justify-between p-4 shrink-0 select-none">
      <div className="space-y-6">
        {/* Navigation Category Label */}
        <div className="px-2">
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
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
                className={`w-full text-left px-3.5 py-2.5 rounded-xl transition-all duration-200 flex items-center justify-between group ${
                  isActive
                    ? 'bg-gradient-to-r from-cyan-950/80 to-blue-950/40 text-cyan-300 border border-cyan-500/40 shadow-lg shadow-cyan-950/40'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`p-2 rounded-lg transition-colors ${
                      isActive
                        ? 'bg-cyan-500/20 text-cyan-300'
                        : 'bg-slate-900 text-slate-400 group-hover:text-slate-200 group-hover:bg-slate-800'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="text-xs font-semibold block leading-tight">
                      {item.label}
                    </span>
                    <span className="text-[10px] text-slate-500 block truncate">
                      {item.description}
                    </span>
                  </div>
                </div>

                {item.badgeNum !== null && (
                  <span
                    className={`px-1.5 py-0.5 text-[10px] font-bold rounded-full text-white ${
                      item.badgeColor || 'bg-cyan-600'
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

      {/* Bottom Ground Station Network Card */}
      <div className="p-3.5 rounded-xl bg-[#0b1220]/80 border border-slate-800/80 space-y-2.5 shadow-inner">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Wifi className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-xs font-semibold text-slate-300">Ground Link</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-950/70 border border-emerald-800/60 text-emerald-400 font-mono">
            LOCKED
          </span>
        </div>

        <div className="text-[11px] text-slate-400 space-y-1 font-mono">
          <div className="flex justify-between">
            <span className="text-slate-500">Primary Station:</span>
            <span className="text-slate-300">HBK (25.88°S)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Backup Link:</span>
            <span className="text-slate-300">White Sands (WS1)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Uplink Margin:</span>
            <span className="text-cyan-400">+18.4 dB</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
