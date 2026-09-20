"use client";

import React, { useState, useEffect } from "react";
import { PlanningBenchmark, EvidenceReference } from "@/lib/types";
import { fetchInstitutionalMemoryBenchmarks } from "@/lib/api";
import { ShieldAlert, Compass, CheckCircle2, AlertTriangle, ShieldCheck } from "lucide-react";

interface BenchmarkAdvisoryCardProps {
  projectId: string;
  onViewEvidence: (title: string, evidence: EvidenceReference[], formula?: string) => void;
}

const DISCIPLINES = ["Civil", "Electrical", "Piping", "Structural", "Mechanical"];

export default function BenchmarkAdvisoryCard({
  projectId,
  onViewEvidence,
}: BenchmarkAdvisoryCardProps) {
  const [selectedDisc, setSelectedDisc] = useState<string>("Civil");
  const [benchmark, setBenchmark] = useState<PlanningBenchmark | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    fetchInstitutionalMemoryBenchmarks(projectId, { discipline: selectedDisc })
      .then((res) => {
        if (isMounted) setBenchmark(res);
      })
      .catch((err) => console.error("Failed to load benchmark:", err))
      .finally(() => {
        if (isMounted) setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [projectId, selectedDisc]);

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2">
          <Compass className="h-5 w-5 text-indigo-600" />
          <h3 className="text-sm font-bold text-slate-900">Planning Benchmark Intelligence (Advisory)</h3>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-medium">Discipline:</span>
          <select
            value={selectedDisc}
            onChange={(e) => setSelectedDisc(e.target.value)}
            className="text-xs border border-slate-300 rounded-md px-2.5 py-1 bg-white text-slate-800"
          >
            {DISCIPLINES.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="py-6 text-center text-xs text-slate-400">
          Calculating benchmark distribution for {selectedDisc}...
        </div>
      ) : !benchmark ? (
        <div className="py-6 text-center text-xs text-slate-400">
          No benchmark data found.
        </div>
      ) : (
        <div className="space-y-4">
          {/* Status Alert */}
          <div
            className={`p-3.5 rounded-lg border flex items-start gap-2.5 text-xs ${
              benchmark.status === "SUFFICIENT_SAMPLE"
                ? "bg-emerald-50/70 border-emerald-200 text-emerald-900"
                : "bg-amber-50/70 border-amber-200 text-amber-900"
            }`}
          >
            {benchmark.status === "SUFFICIENT_SAMPLE" ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
            )}
            <div className="space-y-1">
              <span className="font-bold block">
                {benchmark.status === "SUFFICIENT_SAMPLE"
                  ? `Authoritative ${selectedDisc} Baseline (Sample: ${benchmark.sample_size})`
                  : `Sparse Historical Baseline (Sample: ${benchmark.sample_size})`}
              </span>
              <p className="leading-relaxed">{benchmark.advisory_message}</p>
            </div>
          </div>

          {/* Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="border border-slate-200 rounded-lg p-3 bg-slate-50/50">
              <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
                Median Duration
              </span>
              <span className="text-base font-bold text-slate-900 mt-1 block">
                {benchmark.median_actual_duration !== null && benchmark.median_actual_duration !== undefined
                  ? `${benchmark.median_actual_duration} d`
                  : "—"}
              </span>
            </div>
            <div className="border border-slate-200 rounded-lg p-3 bg-slate-50/50">
              <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
                Average Duration
              </span>
              <span className="text-base font-bold text-slate-900 mt-1 block">
                {benchmark.average_actual_duration !== null && benchmark.average_actual_duration !== undefined
                  ? `${benchmark.average_actual_duration} d`
                  : "—"}
              </span>
            </div>
            <div className="border border-slate-200 rounded-lg p-3 bg-slate-50/50">
              <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
                Observed Production
              </span>
              <span className="text-base font-bold text-slate-900 mt-1 block">
                {benchmark.observed_rate !== null && benchmark.observed_rate !== undefined
                  ? `${benchmark.observed_rate} ${benchmark.rate_unit || ""}`
                  : "—"}
              </span>
            </div>
            <div className="border border-slate-200 rounded-lg p-3 bg-slate-50/50">
              <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
                P80 Benchmark
              </span>
              <span className="text-base font-bold text-slate-900 mt-1 block">
                {benchmark.p80_duration !== null && benchmark.p80_duration !== undefined
                  ? `${benchmark.p80_duration} d`
                  : "N/A (<5)"}
              </span>
            </div>
          </div>

          {benchmark.evidence.length > 0 && (
            <div className="pt-2 flex justify-end">
              <button
                onClick={() =>
                  onViewEvidence(
                    `Historical Planning Benchmark: ${selectedDisc}`,
                    benchmark.evidence
                  )
                }
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-800"
              >
                <ShieldCheck className="h-4 w-4" />
                Inspect Benchmark Evidence Records ({benchmark.evidence.length})
              </button>
            </div>
          )}
        </div>
      )}

      {/* Safety Notice */}
      <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center gap-2 text-[11px] text-slate-500">
        <ShieldAlert className="h-4 w-4 text-slate-400 shrink-0" />
        <span>
          Governance Rule: Planning benchmarks are advisory only. ScheduleManager will never automatically mutate planned durations or CPM logic.
        </span>
      </div>
    </div>
  );
}
