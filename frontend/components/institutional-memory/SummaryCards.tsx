"use client";

import React from "react";
import { CheckCircle2, Database, Clock, BarChart2, ShieldAlert, Layers } from "lucide-react";
import { InstitutionalMemorySummary } from "@/lib/types";

interface SummaryCardsProps {
  summary: InstitutionalMemorySummary | null;
  loading: boolean;
}

export default function SummaryCards({ summary, loading }: SummaryCardsProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-28 bg-slate-100 rounded-xl border border-slate-200"></div>
        ))}
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Verified Records */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs hover:border-indigo-300 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Verified Events
            </span>
            <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <CheckCircle2 className="h-4 w-4" />
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-slate-900">
              {summary.verified_event_count}
            </span>
            <span className="text-xs text-slate-500 font-medium">approved/applied</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            {summary.ledger_entry_count} progress ledger entries
          </div>
        </div>

        {/* Card 2: Completed Activities */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs hover:border-indigo-300 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Completed Activities
            </span>
            <span className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <Database className="h-4 w-4" />
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-slate-900">
              {summary.completed_activity_count}
            </span>
            <span className="text-xs text-slate-500 font-medium">100% complete</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            {summary.data_quality.completed_activities_with_dates || 0} with start/finish dates
          </div>
        </div>

        {/* Card 3: Observed Quantities by Unit */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs hover:border-indigo-300 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Installed Quantities
            </span>
            <span className="p-2 bg-amber-50 text-amber-600 rounded-lg">
              <Layers className="h-4 w-4" />
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {Object.keys(summary.total_quantity_by_unit).length === 0 ? (
              <span className="text-xs text-slate-400">No quantities recorded</span>
            ) : (
              Object.entries(summary.total_quantity_by_unit).map(([unit, qty]) => (
                <span
                  key={unit}
                  className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-amber-50 text-amber-900 border border-amber-200"
                >
                  {qty} {unit}
                </span>
              ))
            )}
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Strictly segregated by compatible unit
          </div>
        </div>

        {/* Card 4: Average Completed Duration */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs hover:border-indigo-300 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Average Actual Duration
            </span>
            <span className="p-2 bg-blue-50 text-blue-600 rounded-lg">
              <Clock className="h-4 w-4" />
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-slate-900">
              {summary.average_actual_duration !== null && summary.average_actual_duration !== undefined
                ? `${summary.average_actual_duration} d`
                : "—"}
            </span>
            <span className="text-xs text-slate-500 font-medium">calendar days</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            {summary.average_duration_variance !== null && summary.average_duration_variance !== undefined ? (
              <span>
                Avg Variance:{" "}
                <strong className={summary.average_duration_variance > 0 ? "text-amber-600" : "text-emerald-600"}>
                  {summary.average_duration_variance > 0 ? `+${summary.average_duration_variance}` : summary.average_duration_variance} d
                </strong>
              </span>
            ) : (
              "Based on completed activities"
            )}
          </div>
        </div>
      </div>

      {/* Data Quality Transparency Banner */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2 text-slate-700">
          <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
          <span className="font-semibold text-slate-900">Institutional Coverage Audit:</span>
          <span className="text-slate-600">
            {summary.data_quality.usable_ledger_entries || 0} Ledger Rows
          </span>
          <span className="text-slate-300">•</span>
          <span className="text-slate-600">
            {summary.data_quality.records_with_quantity || 0} with Quantities
          </span>
          <span className="text-slate-300">•</span>
          <span className="text-slate-600">
            {summary.data_quality.completed_activities_with_dates || 0} Completed with Dates
          </span>
        </div>
        <div className="text-slate-400 font-mono text-[11px]">
          Latest Progress: {summary.latest_reporting_date || "N/A"}
        </div>
      </div>
    </div>
  );
}
