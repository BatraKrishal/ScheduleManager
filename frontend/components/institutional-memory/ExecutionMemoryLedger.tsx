"use client";

import React, { useState, useEffect } from "react";
import {
  HistoricalLedgerEntry,
  HistoricalLedgerPage,
  EvidenceReference,
} from "@/lib/types";
import { fetchInstitutionalMemoryLedger, exportInstitutionalMemoryLedgerUrl } from "@/lib/api";
import {
  Search,
  Filter,
  Download,
  Calendar,
  Layers,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  FileSpreadsheet,
} from "lucide-react";

interface ExecutionMemoryLedgerProps {
  projectId: string;
  onViewEvidence: (title: string, evidence: EvidenceReference[], formula?: string) => void;
}

export default function ExecutionMemoryLedger({
  projectId,
  onViewEvidence,
}: ExecutionMemoryLedgerProps) {
  const [data, setData] = useState<HistoricalLedgerPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [activityCode, setActivityCode] = useState("");
  const [discipline, setDiscipline] = useState("");
  const [unit, setUnit] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const loadLedger = async (p = page) => {
    setLoading(true);
    try {
      const res = await fetchInstitutionalMemoryLedger(projectId, {
        activity_code: activityCode || undefined,
        discipline: discipline || undefined,
        unit: unit || undefined,
        page: p,
        page_size: pageSize,
      });
      setData(res);
      setPage(p);
    } catch (err) {
      console.error("Failed to load historical ledger:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLedger(1);
  }, [projectId, discipline, unit]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadLedger(1);
  };

  const handleExport = () => {
    const url = exportInstitutionalMemoryLedgerUrl(projectId, {
      activity_code: activityCode || undefined,
      discipline: discipline || undefined,
    });
    window.open(url, "_blank");
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
      {/* Header & Controls */}
      <div className="px-6 py-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-4 bg-slate-50/50">
        <div>
          <h3 className="text-sm font-bold text-slate-900">Accumulated Execution Memory Ledger</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Append-only physical progress actuals applied from verified field reports & Time Agent confirmations
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleExport}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg shadow-2xs transition-colors"
          >
            <Download className="h-3.5 w-3.5 text-slate-500" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="p-4 border-b border-slate-200 bg-white flex flex-wrap items-center gap-3">
        <form onSubmit={handleSearchSubmit} className="relative flex-1 min-w-[200px]">
          <Search className="h-3.5 w-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search activity code (e.g. CIV-1002)..."
            value={activityCode}
            onChange={(e) => setActivityCode(e.target.value)}
            className="w-full text-xs pl-8 pr-3 py-1.5 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
          />
        </form>

        <div className="flex items-center gap-2">
          <select
            value={discipline}
            onChange={(e) => setDiscipline(e.target.value)}
            className="text-xs border border-slate-300 rounded-lg px-2.5 py-1.5 bg-white text-slate-700"
          >
            <option value="">All Disciplines</option>
            <option value="Civil">Civil</option>
            <option value="Electrical">Electrical</option>
            <option value="Piping">Piping</option>
            <option value="Structural">Structural</option>
            <option value="Mechanical">Mechanical</option>
          </select>

          <select
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
            className="text-xs border border-slate-300 rounded-lg px-2.5 py-1.5 bg-white text-slate-700"
          >
            <option value="">All Units</option>
            <option value="m">Meters (m)</option>
            <option value="m3">Cubic Meters (m3)</option>
            <option value="t">Tons (t)</option>
            <option value="ea">Each (ea)</option>
          </select>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="py-12 text-center text-slate-400 text-xs">
          Loading historical ledger rows...
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="py-12 text-center text-slate-400 text-xs">
          No historical execution ledger records found matching the filters.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider border-b border-slate-200">
              <tr>
                <th className="px-6 py-3">Reporting Date</th>
                <th className="px-4 py-3">Activity</th>
                <th className="px-4 py-3">Discipline</th>
                <th className="px-4 py-3">Incremental</th>
                <th className="px-4 py-3">Cumulative</th>
                <th className="px-4 py-3">Installed Qty</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-6 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {data.items.map((item) => (
                <tr key={item.ledger_id} className="hover:bg-slate-50/80 transition-colors">
                  <td className="px-6 py-3 font-mono text-[11px] text-slate-600">
                    {item.reporting_date ? item.reporting_date.split(" ")[0] : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono font-bold text-indigo-700">{item.activity_code}</span>
                      <span className="text-slate-500 truncate max-w-[160px]" title={item.activity_name}>
                        {item.activity_name}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {item.discipline ? (
                      <span className="inline-flex px-1.5 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700">
                        {item.discipline}
                      </span>
                    ) : (
                      <span className="text-slate-400 italic">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono font-semibold text-emerald-700">
                    {item.incremental_percent !== null ? `+${item.incremental_percent}%` : "—"}
                  </td>
                  <td className="px-4 py-3 font-mono font-bold text-slate-900">
                    {item.cumulative_percent}%
                  </td>
                  <td className="px-4 py-3 font-mono">
                    {item.installed_quantity !== null ? (
                      <span className="font-bold text-slate-900">
                        {item.installed_quantity} {item.unit_of_measure || ""}
                      </span>
                    ) : (
                      <span className="text-slate-400 italic">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-[11px] text-slate-500">
                    <span className="font-medium text-slate-700">{item.source_type}</span>
                    {item.source_document_name && (
                      <span className="block truncate max-w-[120px] text-slate-400" title={item.source_document_name}>
                        {item.source_document_name}
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-3 text-right">
                    <button
                      onClick={() =>
                        onViewEvidence(
                          `Historical Record: ${item.activity_code} on ${item.reporting_date.split(" ")[0]}`,
                          [
                            {
                              execution_event_id: item.execution_event_id,
                              ledger_id: item.ledger_id,
                              activity_code: item.activity_code,
                              activity_name: item.activity_name,
                              reporting_date: item.reporting_date,
                              quantity: item.installed_quantity,
                              unit: item.unit_of_measure,
                              source_type: item.source_type,
                              source_document_name: item.source_document_name,
                            },
                          ]
                        )
                      }
                      className="p-1 rounded hover:bg-slate-100 text-indigo-600 font-medium inline-flex items-center gap-1 text-[11px]"
                    >
                      <ShieldCheck className="h-3.5 w-3.5" />
                      Detail
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination Controls */}
      {data && data.total_pages > 1 && (
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-600">
          <div>
            Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, data.total)} of{" "}
            <strong className="text-slate-900">{data.total}</strong> records
          </div>
          <div className="flex items-center gap-1.5">
            <button
              disabled={page <= 1}
              onClick={() => loadLedger(page - 1)}
              className="p-1.5 rounded border border-slate-300 bg-white disabled:opacity-40 disabled:pointer-events-none hover:bg-slate-50"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <span className="font-mono text-xs px-2">
              Page {page} of {data.total_pages}
            </span>
            <button
              disabled={page >= data.total_pages}
              onClick={() => loadLedger(page + 1)}
              className="p-1.5 rounded border border-slate-300 bg-white disabled:opacity-40 disabled:pointer-events-none hover:bg-slate-50"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
