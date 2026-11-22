import React from 'react';
import { Info } from 'lucide-react';

interface RiskInterpretationNoticeProps {
  compact?: boolean;
}

export const RiskInterpretationNotice: React.FC<RiskInterpretationNoticeProps> = ({ compact = false }) => (
  <aside className={`flex items-start gap-3 rounded-xl border border-cyan-900/70 bg-cyan-950/20 text-cyan-50 ${compact ? 'px-3 py-2.5' : 'px-4 py-3.5'}`} role="note">
    <Info className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" aria-hidden="true" />
    <div className="space-y-1">
      <p className="text-xs font-semibold text-cyan-100">
        Proximity risk is not probability of collision (Pc).
      </p>
      <p className="text-[11px] leading-relaxed text-slate-300">
        GP/TLE screening tiers prioritize predicted close approaches using propagated geometry. Any Pc shown is an
        illustrative estimate based on modeled uncertainty, not a validated operational probability. Operational Pc
        assessment requires suitable encounter covariance, typically from a quality CDM.
      </p>
    </div>
  </aside>
);
