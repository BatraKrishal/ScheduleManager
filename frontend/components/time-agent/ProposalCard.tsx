"use client";

import React from "react";
import {
  Sparkles,
  ArrowRight,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import { TimeAgentActionCard } from "@/lib/types";

interface ProposalCardProps {
  card: TimeAgentActionCard;
  onConfirm: (proposalId: string) => void;
  onReject: (proposalId: string) => void;
  actionLoading: string | null;
}

export default function ProposalCard({
  card,
  onConfirm,
  onReject,
  actionLoading,
}: ProposalCardProps) {
  const proposalId = card.proposal_id;
  const status = card.proposal_status || "PENDING";
  const isLoading = actionLoading === proposalId;

  const isApplied = status === "APPLIED" || status === "CONSUMED";
  const isRejected = status === "REJECTED";
  const isExpired = status === "EXPIRED";
  const isPending = status === "PENDING";

  return (
    <div className="rounded-xl border border-blue-500/30 bg-slate-950/70 p-4 space-y-3 shadow-xl backdrop-blur-sm">
      {/* Header Bar */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <span className="text-xs font-bold uppercase tracking-wider text-blue-400 flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5" /> Proposed Schedule Update
        </span>
        <div className="flex items-center gap-2">
          {card.execution_date && (
            <span className="text-[11px] text-slate-400">
              Date: {card.execution_date}
            </span>
          )}

          {/* Authoritative Status Badge */}
          {isApplied && (
            <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-950 text-emerald-300 border border-emerald-700/50 flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3 text-emerald-400" />
              Applied
            </span>
          )}
          {isRejected && (
            <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-rose-950 text-rose-300 border border-rose-700/50 flex items-center gap-1">
              <XCircle className="h-3 w-3 text-rose-400" />
              Rejected
            </span>
          )}
          {isExpired && (
            <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-slate-800 text-slate-300 border border-slate-700/50 flex items-center gap-1">
              <Clock className="h-3 w-3 text-slate-400" />
              Expired (5m TTL)
            </span>
          )}
          {isPending && (
            <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-blue-950 text-blue-300 border border-blue-700/50 animate-pulse">
              Awaiting Approval
            </span>
          )}
        </div>
      </div>

      {/* Activity Details */}
      <div className="grid grid-cols-2 gap-2 text-xs bg-slate-900/80 p-3 rounded-lg border border-slate-800">
        <div>
          <span className="text-slate-400 block text-[10px]">Target Activity</span>
          <span className="font-semibold text-white">
            {card.activity_code || "Unknown"}
          </span>
          <span className="text-slate-400 block text-[11px] truncate">
            {card.activity_name || "N/A"}
          </span>
        </div>
        <div>
          <span className="text-slate-400 block text-[10px]">Progress Impact</span>
          <div className="flex items-center gap-1.5 font-bold text-sm mt-0.5">
            <span className="text-slate-400">{card.current_percent ?? 0.0}%</span>
            <ArrowRight className="h-3.5 w-3.5 text-blue-400" />
            <span className="text-emerald-400">
              {card.proposed_percent ?? 0.0}%
            </span>
          </div>
          {card.incremental_quantity !== null &&
            card.incremental_quantity !== undefined && (
              <span className="text-[11px] text-blue-300 block">
                +{card.incremental_quantity} {card.unit || ""}
              </span>
            )}
        </div>
      </div>

      {/* Interactive Actions for PENDING Proposals */}
      {isPending && proposalId && (
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={() => onConfirm(proposalId)}
            disabled={isLoading}
            className="flex-1 py-2 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition-colors flex items-center justify-center gap-1.5 shadow-md shadow-emerald-600/20 disabled:opacity-50"
          >
            {isLoading ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <CheckCircle2 className="h-3.5 w-3.5" />
            )}
            <span>Confirm & Apply Update</span>
          </button>
          <button
            onClick={() => onReject(proposalId)}
            disabled={isLoading}
            className="py-2 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs border border-slate-700 transition-colors flex items-center gap-1 disabled:opacity-50"
          >
            <XCircle className="h-3.5 w-3.5" />
            <span>Reject</span>
          </button>
        </div>
      )}

      {/* Historical Notification for Non-Pending Proposals */}
      {!isPending && (
        <div className="text-[11px] text-slate-400 italic pt-0.5 flex items-center gap-1.5">
          {isApplied && (
            <span className="text-emerald-400">
              ✓ Authoritative schedule update recorded in audit ledger.
            </span>
          )}
          {isRejected && (
            <span className="text-rose-400">
              ✗ Staged proposal was rejected by supervisor.
            </span>
          )}
          {isExpired && (
            <span className="text-slate-400">
              ⏱ Proposal expired after 5-minute safety TTL. Please re-report progress to stage a fresh proposal.
            </span>
          )}
        </div>
      )}
    </div>
  );
}
