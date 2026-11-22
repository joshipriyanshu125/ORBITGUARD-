import React, { useState, useEffect } from 'react';
import { Shield, Radio, Bell, Clock } from 'lucide-react';
import type { SystemHealthStatus } from '../../types';
import ShinyText from '../reactbits/ShinyText';

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

  const isOnline = health?.status === 'healthy';

  return (
    <header className="app-header h-16 border-b border-slate-800/80 bg-[#080d18]/95 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-50">
      {/* Brand & Status */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-slate-900 border border-slate-700 flex items-center justify-center shadow-md">
            <Shield className="w-5 h-5 text-sky-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <ShinyText
                text="ORBITGUARD AI"
                color="#f1f5f9"
                shineColor="#38bdf8"
                speed={4}
                shineWidth={24}
                glow={0.15}
                className="font-black text-lg tracking-wider"
              />
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 uppercase tracking-widest font-mono">
                v1.0
              </span>
            </div>
            <p className="text-[11px] text-slate-400 tracking-tight">Autonomous Orbital Collision Avoidance & Space Intelligence</p>
          </div>
        </div>

        <div className="h-6 w-px bg-slate-800 hidden sm:block" />

        {/* Live System Online Pill */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/90 border border-slate-800 shadow-inner">
          <span className="relative flex h-2 w-2">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${isOnline ? 'bg-emerald-400' : 'bg-rose-400'} opacity-75`}></span>
            <span className={`relative inline-flex rounded-full h-2 w-2 ${isOnline ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
          </span>
          <span className="text-xs font-semibold tracking-wide text-slate-200">
            {isOnline ? 'MISSION CONTROL ONLINE' : 'OFFLINE'}
          </span>
          <Radio className={`w-3.5 h-3.5 ml-1 ${isOnline ? 'text-emerald-400' : 'text-rose-400'}`} />
        </div>
      </div>

      {/* UTC Clock & Session State */}
      <div className="flex items-center gap-4">
        {/* UTC Time */}
        <div className="hidden md:flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono tracking-wider shadow-inner">
          <Clock className="w-3.5 h-3.5 text-sky-400" />
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
            <span className="absolute -top-1 -right-1 px-1.5 py-0.2 bg-rose-500 text-white text-[10px] font-bold rounded-full animate-bounce font-mono">
              {activeAlertsCount}
            </span>
          )}
        </button>

        {/* Catalog Coverage */}
        <div className="flex items-center gap-3 pl-3 border-l border-slate-800">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-200 font-bold text-xs shadow font-mono">
            {health?.catalog?.satellites ?? '—'}
          </div>
          <div className="hidden lg:block text-left">
            <div className="text-xs font-semibold text-slate-200 leading-tight">Catalog Objects</div>
            <div className="text-[10px] text-slate-400 font-mono">
              {health?.database?.engine ?? 'database unknown'}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
