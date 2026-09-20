"use client";

import React from "react";
import { HelpCircle, ChevronRight } from "lucide-react";
import { TimeAgentActionCard } from "@/lib/types";

interface ClarificationCardProps {
  card: TimeAgentActionCard;
  onSelectOption: (value: string) => void;
  disabled?: boolean;
}

export default function ClarificationCard({
  card,
  onSelectOption,
  disabled = false,
}: ClarificationCardProps) {
  if (!card.options || card.options.length === 0) return null;

  return (
    <div className="rounded-xl border border-amber-500/30 bg-slate-950/70 p-3.5 space-y-2.5 shadow-lg backdrop-blur-sm">
      <div className="flex items-center gap-2 text-xs font-semibold text-amber-400">
        <HelpCircle className="h-4 w-4 shrink-0" />
        <span>Clarification Required</span>
      </div>

      {card.question && (
        <p className="text-xs text-slate-300 leading-relaxed">
          {card.question}
        </p>
      )}

      <div className="flex flex-wrap gap-1.5 pt-1">
        {card.options.map((opt, idx) => (
          <button
            key={idx}
            onClick={() => onSelectOption(opt.value || opt.label)}
            disabled={disabled}
            className="px-3 py-1.5 rounded-lg bg-slate-900/90 hover:bg-blue-600 hover:text-white border border-slate-700/80 text-xs text-slate-200 transition-all flex items-center gap-1.5 shadow-sm disabled:opacity-50 group"
          >
            <span>{opt.label}</span>
            <ChevronRight className="h-3 w-3 text-slate-500 group-hover:text-white transition-colors" />
          </button>
        ))}
      </div>
    </div>
  );
}
