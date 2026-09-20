"use client";

import React, { useState } from "react";
import { ProductivityMetric, EvidenceReference } from "@/lib/types";
import { Info, ShieldCheck, HelpCircle } from "lucide-react";

interface ProductivityTableProps {
  metrics: ProductivityMetric[];
  loading: boolean;
  onViewEvidence: (title: string, evidence: EvidenceReference[], formula?: string) => void;
}

export default function ProductivityTable({
  metrics,
  loading,
  onViewEvidence,
}: ProductivityTableProps) {
  const [selectedDiscipline, setSelectedDiscipline] = useState<string>("ALL");

  if (loading) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-6 text-center text-slate-400">
        Loading observed production rates from PostgreSQL...
      </div>
    );
  }

  const disciplines = Array.from(new Set(metrics.map((m) => m.discipline || "General")));
  const filtered = selectedDiscipline === "ALL"
    ? metrics
    : metrics.filter((m) => (m.discipline || "General") === selectedDiscipline);

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
      {/* Header & Filters */}
      <div className="px-6 py-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-4 bg-slate-50/50">
        <div>
          <h3 className="text-sm font-bold text-slate-900">Observed Production Rates</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Strictly segregated by compatible engineering units • Observed reporting-day productivity
          </p>
        </div>

        {disciplines.length > 1 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium">Filter Discipline:</span>
            <select
              value={selectedDiscipline}
              onChange={(e) => setSelectedDiscipline(e.target.value)}
              className="text-xs border border-slate-300 rounded-md px-2.5 py-1 bg-white text-slate-800 focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
            >
              <option value="ALL">All Disciplines</option>
              {disciplines.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="py-12 text-center text-slate-400 text-sm">
          No observed production rates found for the selected filter.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider border-b border-slate-200">
              <tr>
                <th className="px-6 py-3">Discipline</th>
                <th className="px-4 py-3">Contractor</th>
                <th className="px-4 py-3">Installed Quantity</th>
                <th className="px-4 py-3">Reporting Days</th>
                <th className="px-4 py-3">Observed Rate</th>
                <th className="px-4 py-3">Sample Size</th>
                <th className="px-6 py-3 text-right">Lineage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filtered.map((metric, idx) => {
                const disc = metric.discipline || "General";
                return (
                  <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-6 py-3.5 font-bold text-slate-900">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-indigo-50 text-indigo-800 border border-indigo-200">
                        {disc}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-slate-600">
                      {metric.contractor || <span className="text-slate-400 italic">Unspecified</span>}
                    </td>
                    <td className="px-4 py-3.5 font-mono font-medium text-slate-900">
                      {metric.total_quantity} {metric.unit.split("/")[0]}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-slate-700">
                      {metric.reporting_days} day(s)
                    </td>
                    <td className="px-4 py-3.5 font-mono">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                        {metric.rate} {metric.unit}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-slate-500">
                      {metric.sample_count} event(s)
                    </td>
                    <td className="px-6 py-3.5 text-right">
                      <button
                        onClick={() =>
                          onViewEvidence(
                            `Observed ${disc} Rate: ${metric.rate} ${metric.unit}`,
                            metric.evidence,
                            metric.formula
                          )
                        }
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-medium transition-colors text-xs border border-indigo-200"
                      >
                        <ShieldCheck className="h-3.5 w-3.5" />
                        View Evidence ({metric.evidence.length})
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Footer Calculation Disclosure */}
      <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
        <div className="flex items-center gap-1.5">
          <Info className="h-3.5 w-3.5 text-indigo-500" />
          <span>Observed Rate Rule: Total installed quantity ÷ COUNT(DISTINCT reporting_date)</span>
        </div>
        <span className="text-[11px] text-slate-400 font-mono">PostgreSQL Deterministic</span>
      </div>
    </div>
  );
}
