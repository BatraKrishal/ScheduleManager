"use client";

import React from "react";
import { X, FileText, CheckCircle2, Database, Calendar, Tag, ShieldCheck, Hash } from "lucide-react";
import { EvidenceReference } from "@/lib/types";

interface EvidenceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  evidence: EvidenceReference[];
  formula?: string;
}

export default function EvidenceDrawer({
  isOpen,
  onClose,
  title,
  evidence,
  formula,
}: EvidenceDrawerProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/50 backdrop-blur-xs transition-opacity animate-in fade-in">
      <div
        className="w-full max-w-xl bg-white h-full shadow-2xl flex flex-col border-l border-slate-200 overflow-hidden animate-in slide-in-from-right duration-200"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-indigo-600" />
              <h2 className="text-lg font-bold text-slate-900">Historical Evidence Lineage</h2>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">{title}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-md transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Calculation basis disclosure if present */}
        {formula && (
          <div className="px-6 py-3 bg-indigo-50/70 border-b border-indigo-100 flex items-start gap-2.5">
            <Database className="h-4 w-4 text-indigo-600 mt-0.5 shrink-0" />
            <div>
              <span className="text-xs font-semibold text-indigo-900 uppercase tracking-wider block">
                Deterministic Calculation Basis
              </span>
              <span className="text-xs text-indigo-800 font-mono mt-0.5 block">
                {formula}
              </span>
            </div>
          </div>
        )}

        {/* Evidence items list */}
        <div className="flex-1 overflow-y-auto px-6 py-4 divide-y divide-slate-100 space-y-4">
          <div className="flex items-center justify-between pb-2">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              Authoritative PostgreSQL Records ({evidence.length})
            </span>
            <span className="text-xs text-slate-400">Read-Only Provenance</span>
          </div>

          {evidence.length === 0 ? (
            <div className="py-12 text-center text-slate-400 text-sm">
              No evidence records attached to this metric.
            </div>
          ) : (
            evidence.map((ev, idx) => (
              <div key={ev.execution_event_id + idx} className="pt-4 first:pt-0">
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3.5 hover:border-indigo-300 transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                        {ev.activity_code}
                      </span>
                      {ev.activity_name && (
                        <span className="text-xs font-medium text-slate-700 truncate max-w-[200px]">
                          {ev.activity_name}
                        </span>
                      )}
                    </div>
                    {ev.reporting_date && (
                      <div className="flex items-center gap-1 text-xs text-slate-500">
                        <Calendar className="h-3 w-3" />
                        <span>{ev.reporting_date.split(" ")[0]}</span>
                      </div>
                    )}
                  </div>

                  {/* Quantity & Unit */}
                  {ev.quantity !== null && ev.quantity !== undefined && (
                    <div className="mb-2 bg-emerald-50 border border-emerald-200 rounded px-2 py-1 flex items-center justify-between text-xs text-emerald-800">
                      <span className="font-medium">Installed Progress:</span>
                      <span className="font-bold">
                        {ev.quantity} {ev.unit || ""}
                      </span>
                    </div>
                  )}

                  {/* Verbatim Excerpt */}
                  {ev.verbatim_excerpt && (
                    <div className="text-xs text-slate-600 bg-white border border-slate-200 rounded p-2 italic mb-2.5">
                      &ldquo;{ev.verbatim_excerpt}&rdquo;
                    </div>
                  )}

                  {/* IDs & Provenance Metadata */}
                  <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-500 border-t border-slate-200/60 pt-2 font-mono">
                    <div>
                      <span className="text-slate-400 block">Event ID:</span>
                      <span className="truncate block" title={ev.execution_event_id}>
                        {ev.execution_event_id}
                      </span>
                    </div>
                    {ev.ledger_id && (
                      <div>
                        <span className="text-slate-400 block">Ledger ID:</span>
                        <span className="truncate block" title={ev.ledger_id}>
                          {ev.ledger_id.slice(0, 8)}...
                        </span>
                      </div>
                    )}
                    <div>
                      <span className="text-slate-400 block">Source:</span>
                      <span className="text-slate-700 font-sans font-medium">{ev.source_type || "ARTIFACT"}</span>
                    </div>
                    {ev.source_document_name && (
                      <div>
                        <span className="text-slate-400 block">Doc:</span>
                        <span className="truncate block font-sans" title={ev.source_document_name}>
                          {ev.source_document_name}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs text-emerald-700 font-medium">
            <CheckCircle2 className="h-4 w-4" />
            <span>Verified in PostgreSQL Ledger</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-800 text-xs font-medium rounded-md transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
