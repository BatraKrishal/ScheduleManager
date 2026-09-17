"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Calendar,
  Layers,
  Table as TableIcon,
  BarChart3,
  Clock,
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
} from "lucide-react";
import { fetchProject, fetchActivities } from "@/lib/api";
import { Activity, Project } from "@/lib/types";
import ActivityTable from "@/components/ActivityTable";
import ActivityEditorModal from "@/components/ActivityEditorModal";
import WbsTree from "@/components/WbsTree";
import GanttChart from "@/components/GanttChart";

type ActiveTab = "overview" | "wbs" | "activities" | "gantt";

export default function ProjectWorkspace() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<ActiveTab>("activities");

  // Activity editor modal state
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingActivity, setEditingActivity] = useState<Activity | null>(null);
  const [refreshCounter, setRefreshCounter] = useState(0);

  // Overview status metrics
  const [statusCounts, setStatusCounts] = useState({
    notStarted: 0,
    inProgress: 0,
    completed: 0,
    avgPercent: 0,
  });

  const loadProjectData = async () => {
    try {
      const proj = await fetchProject(projectId);
      setProject(proj);

      // Load activities to compute breakdown
      const acts = await fetchActivities(projectId, { page_size: 1000 });
      let ns = 0, ip = 0, comp = 0, totalPct = 0;
      acts.items.forEach((a) => {
        if (a.status === "COMPLETED") comp++;
        else if (a.status === "IN_PROGRESS") ip++;
        else ns++;
        totalPct += a.percent_complete || 0;
      });

      const avg = acts.items.length > 0 ? Math.round(totalPct / acts.items.length) : 0;
      setStatusCounts({
        notStarted: ns,
        inProgress: ip,
        completed: comp,
        avgPercent: avg,
      });
    } catch (err) {
      console.error("Failed to load project details:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectId) {
      loadProjectData();
    }
  }, [projectId, refreshCounter]);

  const handleEditActivity = (act: Activity) => {
    setEditingActivity(act);
    setIsEditorOpen(true);
  };

  const handleAddActivity = () => {
    setEditingActivity(null);
    setIsEditorOpen(true);
  };

  const handleSaved = () => {
    setRefreshCounter((c) => c + 1);
  };

  const formatDate = (dt: string | null) => {
    if (!dt) return "Not set";
    try {
      return new Date(dt).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return dt;
    }
  };

  if (loading) {
    return (
      <div className="py-24 text-center text-sm text-slate-400">
        Loading project workspace...
      </div>
    );
  }

  if (!project) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center space-y-3">
        <AlertCircle className="mx-auto h-8 w-8 text-red-600" />
        <h3 className="text-base font-bold text-red-900">Project Not Found</h3>
        <p className="text-xs text-red-700">The requested schedule project could not be located.</p>
        <Link
          href="/"
          className="inline-block rounded-lg bg-red-600 px-4 py-2 text-xs font-semibold text-white hover:bg-red-500"
        >
          Return to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Project Header */}
      <div>
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 mb-3 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Dashboard
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-100">
                {project.project_code}
              </span>
              <span className="text-xs text-slate-400">•</span>
              <span className="text-xs text-slate-500">
                Data Date: {formatDate(project.data_date)}
              </span>
            </div>
            <h1 className="mt-1.5 text-2xl font-black text-slate-900 tracking-tight">
              {project.name}
            </h1>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <div className="text-right">
              <div className="text-slate-400">Schedule Window</div>
              <div className="font-semibold text-slate-700 mt-0.5">
                {formatDate(project.planned_start)} — {formatDate(project.planned_finish)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-8">
          <button
            onClick={() => setActiveTab("overview")}
            className={`flex items-center gap-2 pb-4 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === "overview"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <BarChart3 className="h-4 w-4" />
            Overview
          </button>

          <button
            onClick={() => setActiveTab("activities")}
            className={`flex items-center gap-2 pb-4 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === "activities"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <TableIcon className="h-4 w-4" />
            Activities ({project.activity_count})
          </button>

          <button
            onClick={() => setActiveTab("wbs")}
            className={`flex items-center gap-2 pb-4 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === "wbs"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Layers className="h-4 w-4" />
            WBS Tree ({project.wbs_count})
          </button>

          <button
            onClick={() => setActiveTab("gantt")}
            className={`flex items-center gap-2 pb-4 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === "gantt"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Calendar className="h-4 w-4" />
            Gantt Timeline
          </button>
        </nav>
      </div>

      {/* Tab 1: Overview */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Average Completion
              </div>
              <div className="mt-2 text-3xl font-black text-blue-600">
                {statusCounts.avgPercent}%
              </div>
              <div className="mt-3 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full bg-blue-600 rounded-full"
                  style={{ width: `${statusCounts.avgPercent}%` }}
                />
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Completed
              </div>
              <div className="mt-2 text-3xl font-black text-emerald-600">
                {statusCounts.completed}
              </div>
              <div className="text-xs text-slate-500 mt-1">Activities finished (100%)</div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                In Progress
              </div>
              <div className="mt-2 text-3xl font-black text-blue-600">
                {statusCounts.inProgress}
              </div>
              <div className="text-xs text-slate-500 mt-1">Active tasks underway</div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Not Started
              </div>
              <div className="mt-2 text-3xl font-black text-slate-700">
                {statusCounts.notStarted}
              </div>
              <div className="text-xs text-slate-500 mt-1">Pending future work</div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
            <h3 className="text-base font-bold text-slate-900">Project Baseline Parameters</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div className="rounded-lg bg-slate-50 p-4">
                <div className="text-slate-400 font-medium">Planned Start Date</div>
                <div className="font-bold text-slate-900 text-sm mt-1">
                  {formatDate(project.planned_start)}
                </div>
              </div>
              <div className="rounded-lg bg-slate-50 p-4">
                <div className="text-slate-400 font-medium">Planned Finish Date</div>
                <div className="font-bold text-slate-900 text-sm mt-1">
                  {formatDate(project.planned_finish)}
                </div>
              </div>
              <div className="rounded-lg bg-slate-50 p-4">
                <div className="text-slate-400 font-medium">Schedule Data Date</div>
                <div className="font-bold text-slate-900 text-sm mt-1">
                  {formatDate(project.data_date)}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Activities Spreadsheet */}
      {activeTab === "activities" && (
        <ActivityTable
          projectId={projectId}
          onEditActivity={handleEditActivity}
          onAddActivity={handleAddActivity}
          refreshTrigger={refreshCounter}
        />
      )}

      {/* Tab 3: WBS Tree */}
      {activeTab === "wbs" && (
        <WbsTree projectId={projectId} />
      )}

      {/* Tab 4: Gantt Chart */}
      {activeTab === "gantt" && (
        <GanttChart projectId={projectId} onEditActivity={handleEditActivity} />
      )}

      {/* Activity Editor Modal */}
      <ActivityEditorModal
        isOpen={isEditorOpen}
        onClose={() => setIsEditorOpen(false)}
        onSaved={handleSaved}
        activity={editingActivity}
        projectId={projectId}
      />
    </div>
  );
}
