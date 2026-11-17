import React, { useState, useEffect } from 'react';
import { Shield, Radio, Bell, User, Clock, AlertTriangle } from 'lucide-react';
import type { SystemHealthStatus } from '../../types';

interface HeaderProps {
  health: SystemHealthStatus | null;
  activeAlertsCount: number;
  onAlertsClick?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ health, activeAlertsCount, onAlertsClick }) => {
  const [utcTime, setUtcTime] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcTime(now.toUTCString().replace('GMT', 'UTC'));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const isOnline = health?.status === 'healthy' || health?.status === 'online' || true;

  return (
    <header className="h-16 border-b border-slate-800/80 bg-[#070b14]/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-50">
      {/* Brand & Status */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-cyan-600 to-blue-500 flex items-center justify-center shadow-lg shadow-cyan-500/20 ring-1 ring-cyan-400/40">
            <Shield className="w-5 h-5 text-white animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-black text-lg tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-100 to-cyan-300">
                ORBITGUARD AI
              </span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 uppercase tracking-widest">
                v0.1.0
              </span>
            </div>
            <p className="text-[11px] text-slate-400 tracking-tight">Autonomous Orbital Collision Avoidance & Space Intelligence</p>
          </div>
        </div>

        <div className="h-6 w-px bg-slate-800 hidden sm:block" />

        {/* Live System Online Pill */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/90 border border-slate-800/90 shadow-inner">
          <span className="relative flex h-2.5 w-2.5">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${isOnline ? 'bg-emerald-400' : 'bg-rose-400'} opacity-75`}></span>
            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${isOnline ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
          </span>
          <span className="text-xs font-semibold tracking-wide text-slate-200">
            {isOnline ? 'MISSION CONTROL ONLINE' : 'OFFLINE'}
          </span>
          <Radio className="w-3.5 h-3.5 text-cyan-400 ml-1" />
        </div>
      </div>

      {/* UTC Clock & Operator Profile */}
      <div className="flex items-center gap-5">
        {/* UTC Time */}
        <div className="hidden md:flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-[#0b1220] border border-slate-800 text-xs text-cyan-300 font-mono tracking-wider shadow-inner">
          <Clock className="w-3.5 h-3.5 text-cyan-400" />
          <span>{utcTime || 'UTC CLOCK SYNCING...'}</span>
        </div>

        {/* Alerts Button */}
        <button
          onClick={onAlertsClick}
          className="relative p-2 rounded-lg bg-slate-900/80 hover:bg-slate-800 border border-slate-800 text-slate-300 transition-colors"
          title="Active Conjunction Alerts"
        >
          <Bell className="w-4 h-4" />
          {activeAlertsCount > 0 && (
            <span className="absolute -top-1 -right-1 px-1.5 py-0.2 bg-rose-500 text-white text-[10px] font-bold rounded-full animate-bounce">
              {activeAlertsCount}
            </span>
          )}
        </button>

        {/* Operator Badge */}
        <div className="flex items-center gap-3 pl-2 border-l border-slate-800">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-slate-700 to-slate-900 border border-cyan-500/40 flex items-center justify-center text-cyan-300 font-bold text-xs shadow-md">
            AC
          </div>
          <div className="hidden lg:block text-left">
            <div className="text-xs font-semibold text-slate-200 leading-tight">Alex Carter</div>
            <div className="text-[10px] text-cyan-400 font-medium">Lead Flight Director</div>
          </div>
        </div>
      </div>
    </header>
  );
};
