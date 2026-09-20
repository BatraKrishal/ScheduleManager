"use client";

import React from "react";
import { HelpCircle, ChevronRight, Layers, CheckCheck, X, ArrowRight, Percent } from "lucide-react";
import { TimeAgentActionCard } from "@/lib/types";

interface ClarificationCardProps {
  card: TimeAgentActionCard;
  onSelectOption: (value: string) => void;
  onConfirmBulk?: (activityIds: string[], targetPercent: number) => void;
  disabled?: boolean;
}

export default function ClarificationCard({
  card,
  onSelectOption,
  onConfirmBulk,
  disabled = false,
}: ClarificationCardProps) {
  // 1. Bulk Scope Proposal Card
  if (card.type === "BULK_SCOPE_PROPOSAL") {
    const activities = card.bulk_activities || [];
    const count = card.bulk_count ?? activities.length;
    const targetPct = card.target_percent ?? 100.0;
    const isApplied = card.proposal_status === "APPLIED";
    const isCancelled = card.proposal_status === "CANCELLED";

    return (
      <div className="rounded-xl border border-indigo-500/40 bg-slate-950/80 p-4 space-y-3 shadow-xl backdrop-blur-md">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-semibold text-indigo-400">
            <Layers className="h-4 w-4 shrink-0" />
            <span>{card.scope_label || "Bulk Work Package Scope"}</span>
          </div>
          <div className="flex items-center gap-2">
            {isApplied && (
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold flex items-center gap-1">
                <CheckCheck className="h-3 w-3" />
                Applied
              </span>
            )}
            {isCancelled && (
              <span className="px-2 py-0.5 rounded-full bg-slate-500/20 border border-slate-500/30 text-slate-400 text-[10px] font-bold flex items-center gap-1">
                <X className="h-3 w-3" />
                Cancelled
              </span>
            )}
            <span className="px-2 py-0.5 rounded-full bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-[10px] font-bold">
              {count} {count === 1 ? "Activity" : "Activities"} Found
            </span>
          </div>
        </div>

        {card.question && (
          <p className="text-xs text-slate-300 leading-relaxed">{card.question}</p>
        )}

        {/* Activity Preview List */}
        {activities.length > 0 && (
          <div className="rounded-lg border border-slate-800 bg-slate-900/90 divide-y divide-slate-800/80 overflow-hidden text-xs">
            {activities.map((act) => (
              <div
                key={act.activity_id}
                className="flex items-center justify-between px-3 py-2 hover:bg-slate-800/50 transition-colors"
              >
                <div className="min-w-0 flex items-center gap-2">
                  <span className="font-mono font-semibold text-blue-400 shrink-0">
                    {act.activity_code}
                  </span>
                  <span className="text-slate-300 truncate max-w-[200px] sm:max-w-[280px]">
                    {act.activity_name}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0 text-[11px] font-medium">
                  <span className="text-slate-400">{act.current_percent}%</span>
                  <ArrowRight className="h-3 w-3 text-slate-500" />
                  <span className="text-emerald-400 font-semibold">{targetPct}%</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Bulk Action Buttons */}
        {!isApplied && !isCancelled && (
          <div className="flex flex-wrap items-center gap-2 pt-1">
            {activities.length > 0 && activities.length <= 6 && (
              <button
                onClick={() => {
                  if (onConfirmBulk) {
                    onConfirmBulk(
                      activities.map((a) => a.activity_id),
                      targetPct
                    );
                  } else {
                    onSelectOption("CONFIRM_ALL_BULK");
                  }
                }}
                disabled={disabled}
                className="flex-1 sm:flex-initial px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-medium text-xs flex items-center justify-center gap-1.5 shadow-md shadow-emerald-900/30 transition-all disabled:opacity-50"
              >
                <CheckCheck className="h-3.5 w-3.5" />
                <span>Update All {count} ({targetPct}%)</span>
              </button>
            )}

            <button
              onClick={() => onSelectOption("CANCEL")}
              disabled={disabled}
              className="px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-xs text-slate-300 transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              <X className="h-3.5 w-3.5 text-slate-500" />
              <span>Cancel</span>
            </button>
          </div>
        )}
      </div>
    );
  }

  // 2. Standard or Multi-Choice Clarification Choice Card
  if (!card.options || card.options.length === 0) return null;

  // Check if options have rich metadata (activity_code or score) or list has >= 3 items
  const isStructuredList =
    card.options.length >= 3 || card.options.some((o) => (o as any).activity_code || (o as any).confidence_score);

  return (
    <div className="rounded-xl border border-amber-500/30 bg-slate-950/80 p-3.5 space-y-2.5 shadow-lg backdrop-blur-md">
      <div className="flex items-center gap-2 text-xs font-semibold text-amber-400">
        <HelpCircle className="h-4 w-4 shrink-0" />
        <span>Clarification Required</span>
      </div>

      {card.question && (
        <p className="text-xs text-slate-300 leading-relaxed font-medium">{card.question}</p>
      )}

      {isStructuredList ? (
        // Structured Vertical Stacked List (ChatGPT field UI style)
        <div className="rounded-lg border border-slate-800 bg-slate-900/90 divide-y divide-slate-800/80 overflow-hidden shadow-inner">
          {card.options.map((opt, idx) => {
            const isNone = opt.value === "NONE_OF_THESE" || opt.label.toLowerCase() === "none of these";
            const score = (opt as any).confidence_score;
            const scorePct = score ? Math.round(score * 100) : null;

            return (
              <button
                key={idx}
                onClick={() => onSelectOption(opt.value || opt.label)}
                disabled={disabled}
                className={`w-full px-3.5 py-2.5 text-left text-xs transition-colors flex items-center justify-between group disabled:opacity-50 ${
                  isNone
                    ? "bg-slate-950/40 hover:bg-slate-800/60 text-slate-400 hover:text-slate-200"
                    : "hover:bg-blue-600/15 text-slate-200"
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  {(opt as any).activity_code && (
                    <span className="px-1.5 py-0.5 rounded bg-blue-500/20 border border-blue-500/30 font-mono font-bold text-[10px] text-blue-300 shrink-0">
                      {(opt as any).activity_code}
                    </span>
                  )}
                  <span className={`truncate ${isNone ? "italic text-slate-400" : "font-medium"}`}>
                    {(opt as any).activity_name || opt.label}
                  </span>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {scorePct && (
                    <span className="text-[10px] text-slate-500 font-mono group-hover:text-blue-400 transition-colors">
                      {scorePct}% match
                    </span>
                  )}
                  <ChevronRight className="h-3.5 w-3.5 text-slate-600 group-hover:text-blue-400 group-hover:translate-x-0.5 transition-all" />
                </div>
              </button>
            );
          })}
        </div>
      ) : (
        // Compact Chip Wrap for standard 2-choice options
        <div className="flex flex-wrap gap-1.5 pt-1">
          {card.options.map((opt, idx) => {
            const isNone = opt.value === "NONE_OF_THESE" || opt.label.toLowerCase() === "none of these";
            return (
              <button
                key={idx}
                onClick={() => onSelectOption(opt.value || opt.label)}
                disabled={disabled}
                className={`px-3 py-1.5 rounded-lg border text-xs transition-all flex items-center gap-1.5 shadow-sm disabled:opacity-50 group ${
                  isNone
                    ? "bg-slate-900/60 border-slate-700/60 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                    : "bg-slate-900/90 hover:bg-blue-600 hover:text-white border-slate-700/80 text-slate-200"
                }`}
              >
                <span>{opt.label}</span>
                <ChevronRight className="h-3 w-3 text-slate-500 group-hover:text-white transition-colors" />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
