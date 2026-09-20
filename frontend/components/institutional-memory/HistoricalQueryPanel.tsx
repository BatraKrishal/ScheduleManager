"use client";

import React, { useState } from "react";
import { HistoricalQueryResponse, EvidenceReference } from "@/lib/types";
import { queryInstitutionalMemory } from "@/lib/api";
import {
  Search,
  Sparkles,
  Database,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
  Send,
} from "lucide-react";

interface HistoricalQueryPanelProps {
  projectId: string;
  onViewEvidence: (title: string, evidence: EvidenceReference[], formula?: string) => void;
}

const QUICK_QUERIES = [
  { label: "Civil Concrete Production Rate", query: "What was our observed concrete pouring rate?", type: "PRODUCTIVITY" as const, disc: "Civil" },
  { label: "Electrical Cable Tray Rate", query: "What was our observed electrical installation rate?", type: "PRODUCTIVITY" as const, disc: "Electrical" },
  { label: "Completed Civil Durations", query: "How long did our completed civil activities take?", type: "DURATION" as const, disc: "Civil" },
  { label: "Planned vs Actual Variances", query: "What was our planned versus actual duration variance?", type: "VARIANCE" as const },
];

export default function HistoricalQueryPanel({
  projectId,
  onViewEvidence,
}: HistoricalQueryPanelProps) {
  const [naturalQuery, setNaturalQuery] = useState("");
  const [queryType, setQueryType] = useState<"PRODUCTIVITY" | "DURATION" | "VARIANCE" | "EXECUTION_HISTORY" | "SUMMARY">("PRODUCTIVITY");
  const [discipline, setDiscipline] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<HistoricalQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const execute = async (customQ?: string, customType?: any, customDisc?: string) => {
    const qText = customQ !== undefined ? customQ : naturalQuery;
    const qT = customType !== undefined ? customType : queryType;
    const qD = customDisc !== undefined ? customDisc : discipline;

    setLoading(true);
    setError(null);
    try {
      const res = await queryInstitutionalMemory(projectId, {
        query_type: qT,
        discipline: qD || null,
        natural_query: qText || null,
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Failed to execute historical query");
    } finally {
      setLoading(false);
    }
  };

  const handleQuickClick = (q: (typeof QUICK_QUERIES)[0]) => {
    setNaturalQuery(q.query);
    setQueryType(q.type);
    setDiscipline(q.disc || "");
    execute(q.query, q.type, q.disc);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!naturalQuery.trim()) return;
    execute();
  };

  return (
    <div className="space-y-4">
      {/* Query Bar Container */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
        <div className="flex items-center gap-2 mb-2">
          <Database className="h-5 w-5 text-indigo-600" />
          <h3 className="text-base font-bold text-slate-900">Historical Knowledge Query</h3>
        </div>
        <p className="text-xs text-slate-500 mb-4">
          Query verified historical execution actuals. Computations are strictly executed by PostgreSQL; numbers are never hallucinated.
        </p>

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="relative">
            <input
              type="text"
              placeholder="Ask a historical question (e.g. 'What was our observed concrete pouring rate?')..."
              value={naturalQuery}
              onChange={(e) => setNaturalQuery(e.target.value)}
              className="w-full text-sm pl-4 pr-24 py-2.5 border border-slate-300 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-indigo-500 shadow-2xs"
            />
            <button
              type="submit"
              disabled={loading || !naturalQuery.trim()}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-colors shadow-xs"
            >
              {loading ? (
                <span>Querying...</span>
              ) : (
                <>
                  <Send className="h-3.5 w-3.5" />
                  <span>Run Query</span>
                </>
              )}
            </button>
          </div>

          {/* Quick query chips */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-xs text-slate-400 font-medium">Quick Benchmarks:</span>
            {QUICK_QUERIES.map((q, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleQuickClick(q)}
                className="text-xs px-2.5 py-1 rounded-full bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 text-slate-700 border border-slate-200 transition-colors"
              >
                {q.label}
              </button>
            ))}
          </div>
        </form>
      </div>

      {/* Query Result View */}
      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-3 text-xs text-rose-800">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {result && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4 animate-in fade-in duration-200">
          {/* Result Header */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                {result.query_type}
              </span>
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold ${
                  result.data_status === "CONFIRMED"
                    ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                    : result.data_status === "INSUFFICIENT_DATA"
                    ? "bg-amber-50 text-amber-800 border border-amber-200"
                    : "bg-slate-100 text-slate-700"
                }`}
              >
                {result.data_status === "CONFIRMED" ? (
                  <>
                    <CheckCircle2 className="h-3 w-3" />
                    Verified Baseline
                  </>
                ) : (
                  <>
                    <HelpCircle className="h-3 w-3" />
                    Sparse Data Warning
                  </>
                )}
              </span>
            </div>

            {result.evidence.length > 0 && (
              <button
                onClick={() =>
                  onViewEvidence(
                    `Query Result Evidence (${result.evidence.length} records)`,
                    result.evidence
                  )
                }
                className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800"
              >
                <ShieldCheck className="h-4 w-4" />
                Inspect Underlying Records ({result.evidence.length})
              </button>
            )}
          </div>

          {/* Answer Statement */}
          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium text-slate-900 leading-relaxed">
            {result.summary}
          </div>

          {/* Insights Breakdown */}
          {result.insights.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
              {result.insights.map((ins, idx) => (
                <div key={idx} className="border border-slate-200 rounded-lg p-3 bg-white">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-slate-900">{ins.title}</span>
                    {ins.metric_value !== null && ins.metric_value !== undefined && (
                      <span className="font-mono text-xs font-bold text-indigo-700">
                        {ins.metric_value} {ins.unit || ""}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-600">{ins.summary}</p>
                  {ins.limitations.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-slate-100 text-[11px] text-slate-400">
                      {ins.limitations.join(" • ")}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
