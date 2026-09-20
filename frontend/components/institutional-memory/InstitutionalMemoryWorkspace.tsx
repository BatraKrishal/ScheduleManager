"use client";

import React, { useState, useEffect } from "react";
import {
  Project,
  InstitutionalMemorySummary,
  ProductivityMetric,
  DurationSummary,
  EvidenceReference,
} from "@/lib/types";
import {
  fetchInstitutionalMemorySummary,
  fetchInstitutionalMemoryProductivity,
  fetchInstitutionalMemoryDurations,
  exportInstitutionalMemoryLedgerUrl,
} from "@/lib/api";
import SummaryCards from "./SummaryCards";
import ProductivityTable from "./ProductivityTable";
import DurationVarianceTable from "./DurationVarianceTable";
import ExecutionMemoryLedger from "./ExecutionMemoryLedger";
import HistoricalQueryPanel from "./HistoricalQueryPanel";
import BenchmarkAdvisoryCard from "./BenchmarkAdvisoryCard";
import EvidenceDrawer from "./EvidenceDrawer";
import {
  Database,
  BarChart3,
  Clock,
  FileSpreadsheet,
  Search,
  RefreshCw,
  Download,
  ShieldCheck,
  Compass,
} from "lucide-react";

interface InstitutionalMemoryWorkspaceProps {
  projectId: string;
  project: Project | null;
}

type SubTab = "overview" | "productivity" | "durations" | "ledger" | "query";

export default function InstitutionalMemoryWorkspace({
  projectId,
  project,
}: InstitutionalMemoryWorkspaceProps) {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>("overview");
  const [summary, setSummary] = useState<InstitutionalMemorySummary | null>(null);
  const [productivities, setProductivities] = useState<ProductivityMetric[]>([]);
  const [durations, setDurations] = useState<DurationSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshIndex, setRefreshIndex] = useState(0);

  // Evidence Drawer State
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTitle, setDrawerTitle] = useState("");
  const [drawerEvidence, setDrawerEvidence] = useState<EvidenceReference[]>([]);
  const [drawerFormula, setDrawerFormula] = useState<string | undefined>(undefined);

  const loadData = async () => {
    setLoading(true);
    try {
      const [sumRes, prodRes, durRes] = await Promise.all([
        fetchInstitutionalMemorySummary(projectId),
        fetchInstitutionalMemoryProductivity(projectId),
        fetchInstitutionalMemoryDurations(projectId),
      ]);
      setSummary(sumRes);
      setProductivities(prodRes);
      setDurations(durRes);
    } catch (err) {
      console.error("Failed to load institutional memory analytics:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectId) {
      loadData();
    }
  }, [projectId, refreshIndex]);

  const handleOpenEvidence = (title: string, evidence: EvidenceReference[], formula?: string) => {
    setDrawerTitle(title);
    setDrawerEvidence(evidence);
    setDrawerFormula(formula);
    setDrawerOpen(true);
  };

  const handleExportCSV = () => {
    const url = exportInstitutionalMemoryLedgerUrl(projectId);
    window.open(url, "_blank");
  };

  return (
    <div className="space-y-6">
      {/* Workspace Header */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-2 bg-indigo-50 text-indigo-700 rounded-lg">
                <Database className="h-5 w-5" />
              </span>
              <div>
                <h1 className="text-xl font-black text-slate-900">Institutional Memory Engine</h1>
                <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-500">
                  <span>Project Scope: <strong className="text-slate-800 font-mono">{project?.project_code || "CURRENT_PROJECT"}</strong></span>
                  <span>•</span>
                  <span>PostgreSQL Authoritative Execution Ledger</span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setRefreshIndex((c) => c + 1)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg shadow-2xs transition-colors"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-indigo-600" : "text-slate-500"}`} />
              Refresh
            </button>
            <button
              onClick={handleExportCSV}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors"
            >
              <Download className="h-3.5 w-3.5" />
              Export Full Ledger (CSV)
            </button>
          </div>
        </div>

        {/* Sub-tab Navigation */}
        <div className="flex items-center gap-1 mt-6 border-b border-slate-200 -mb-2 text-xs">
          <button
            onClick={() => setActiveSubTab("overview")}
            className={`pb-2.5 px-3 font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
              activeSubTab === "overview"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Compass className="h-3.5 w-3.5" />
            Executive Overview & Insights
          </button>
          <button
            onClick={() => setActiveSubTab("productivity")}
            className={`pb-2.5 px-3 font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
              activeSubTab === "productivity"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <BarChart3 className="h-3.5 w-3.5" />
            Observed Productivity
          </button>
          <button
            onClick={() => setActiveSubTab("durations")}
            className={`pb-2.5 px-3 font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
              activeSubTab === "durations"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Clock className="h-3.5 w-3.5" />
            Planned vs Actual Durations
          </button>
          <button
            onClick={() => setActiveSubTab("ledger")}
            className={`pb-2.5 px-3 font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
              activeSubTab === "ledger"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <FileSpreadsheet className="h-3.5 w-3.5" />
            Execution Memory Ledger
          </button>
          <button
            onClick={() => setActiveSubTab("query")}
            className={`pb-2.5 px-3 font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
              activeSubTab === "query"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Search className="h-3.5 w-3.5" />
            Historical Query & Lineage
          </button>
        </div>
      </div>

      {/* Sub-tab Contents */}
      {activeSubTab === "overview" && (
        <div className="space-y-6">
          <SummaryCards summary={summary} loading={loading} />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <BenchmarkAdvisoryCard projectId={projectId} onViewEvidence={handleOpenEvidence} />
            <ProductivityTable
              metrics={productivities}
              loading={loading}
              onViewEvidence={handleOpenEvidence}
            />
          </div>

          <DurationVarianceTable durations={durations} loading={loading} />
        </div>
      )}

      {activeSubTab === "productivity" && (
        <ProductivityTable
          metrics={productivities}
          loading={loading}
          onViewEvidence={handleOpenEvidence}
        />
      )}

      {activeSubTab === "durations" && (
        <DurationVarianceTable durations={durations} loading={loading} />
      )}

      {activeSubTab === "ledger" && (
        <ExecutionMemoryLedger projectId={projectId} onViewEvidence={handleOpenEvidence} />
      )}

      {activeSubTab === "query" && (
        <HistoricalQueryPanel projectId={projectId} onViewEvidence={handleOpenEvidence} />
      )}

      {/* Slide-over Evidence Drawer */}
      <EvidenceDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerTitle}
        evidence={drawerEvidence}
        formula={drawerFormula}
      />
    </div>
  );
}
