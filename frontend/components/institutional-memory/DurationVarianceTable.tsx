"use client";

import React, { useState } from "react";
import { DurationSummary } from "@/lib/types";
import { CheckCircle2, AlertTriangle, Clock, TrendingUp } from "lucide-react";

interface DurationVarianceTableProps {
  durations: DurationSummary | null;
  loading: boolean;
}

export default function DurationVarianceTable({
  durations,
  loading,
}: DurationVarianceTableProps) {
  const [filterStatus, setFilterStatus] = useState<"ALL" | "ON_TIME" | "DELAYED">("ALL");

  if (loading) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-6 text-center text-slate-400">
        Loading planned vs actual durations from PostgreSQL...
      </div>
    );
  }

  if (!durations || durations.activities_completed === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-12 text-center text-slate-400">
        No completed activities with verified start and finish dates found in project history.
      </div>
    );
  }

  const filteredItems = durations.items.filter((item) => {
    if (filterStatus === "ON_TIME") return item.is_on_time;
    if (filterStatus === "DELAYED") return !item.is_on_time;
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Top Distribution Metric Pills */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white border border-slate-200 rounded-lg p-3">
          <span className="text-xs text-slate-500 font-medium block">Avg Planned Duration</span>
          <span className="text-lg font-bold text-slate-900 mt-1 block">
            {durations.average_planned_duration} d
          </span>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-3">
          <span className="text-xs text-slate-500 font-medium block">Avg Actual Duration</span>
          <span className="text-lg font-bold text-slate-900 mt-1 block">
            {durations.average_actual_duration} d
          </span>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-3">
          <span className="text-xs text-slate-500 font-medium block">Average Variance</span>
          <span
            className={`text-lg font-bold mt-1 block ${
              durations.average_variance_days > 0 ? "text-amber-600" : "text-emerald-600"
            }`}
          >
            {durations.average_variance_days > 0
              ? `+${durations.average_variance_days}`
              : durations.average_variance_days}{" "}
            d
          </span>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-3">
          <span className="text-xs text-slate-500 font-medium block">Pacing Distribution</span>
          <div className="text-xs font-mono text-slate-700 mt-1.5 space-y-0.5">
            <div>
              P50: <strong>{durations.p50_duration !== null && durations.p50_duration !== undefined ? `${durations.p50_duration}d` : "N/A (<5)"}</strong>
            </div>
            <div>
              P80: <strong>{durations.p80_duration !== null && durations.p80_duration !== undefined ? `${durations.p80_duration}d` : "N/A (<5)"}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Table Card */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-4 bg-slate-50/50">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Planned vs Actual Duration Variance</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Strictly calculated from recorded actual start and finish dates of completed activities
            </p>
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-lg border border-slate-200 text-xs">
            <button
              onClick={() => setFilterStatus("ALL")}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                filterStatus === "ALL"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              All ({durations.items.length})
            </button>
            <button
              onClick={() => setFilterStatus("ON_TIME")}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                filterStatus === "ON_TIME"
                  ? "bg-white text-emerald-800 shadow-xs"
                  : "text-slate-600 hover:text-emerald-800"
              }`}
            >
              On Time ({durations.on_time_count})
            </button>
            <button
              onClick={() => setFilterStatus("DELAYED")}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                filterStatus === "DELAYED"
                  ? "bg-white text-amber-800 shadow-xs"
                  : "text-slate-600 hover:text-amber-800"
              }`}
            >
              Delayed ({durations.delayed_count})
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider border-b border-slate-200">
              <tr>
                <th className="px-6 py-3">Activity Code</th>
                <th className="px-4 py-3">Activity Name</th>
                <th className="px-4 py-3">Discipline</th>
                <th className="px-4 py-3">Planned Duration</th>
                <th className="px-4 py-3">Actual Duration</th>
                <th className="px-4 py-3">Variance</th>
                <th className="px-4 py-3">Execution Dates</th>
                <th className="px-6 py-3 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filteredItems.map((item) => (
                <tr key={item.activity_id} className="hover:bg-slate-50/80 transition-colors">
                  <td className="px-6 py-3.5 font-mono font-bold text-indigo-700">
                    {item.activity_code}
                  </td>
                  <td className="px-4 py-3.5 font-medium text-slate-900 max-w-[220px] truncate" title={item.activity_name}>
                    {item.activity_name}
                  </td>
                  <td className="px-4 py-3.5 text-slate-600">
                    {item.discipline || <span className="text-slate-400 italic">—</span>}
                  </td>
                  <td className="px-4 py-3.5 font-mono text-slate-800">
                    {item.planned_duration_days} d
                  </td>
                  <td className="px-4 py-3.5 font-mono font-bold text-slate-900">
                    {item.actual_duration_days} d
                  </td>
                  <td className="px-4 py-3.5 font-mono">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                        item.variance_days > 0
                          ? "bg-amber-50 text-amber-800 border border-amber-200"
                          : item.variance_days < 0
                          ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                          : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {item.variance_days > 0 ? `+${item.variance_days}` : item.variance_days} d
                      {" "}({item.variance_percent > 0 ? `+${item.variance_percent}` : item.variance_percent}%)
                    </span>
                  </td>
                  <td className="px-4 py-3.5 text-[11px] font-mono text-slate-500">
                    {item.actual_start} → {item.actual_finish}
                  </td>
                  <td className="px-6 py-3.5 text-right">
                    {item.is_on_time ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <CheckCircle2 className="h-3 w-3" />
                        On Time
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                        <AlertTriangle className="h-3 w-3" />
                        Delayed
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
