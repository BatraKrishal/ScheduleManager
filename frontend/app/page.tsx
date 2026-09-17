"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Plus,
  Calendar,
  Layers,
  Activity as ActivityIcon,
  GitFork,
  Trash2,
  FolderGit2,
  ArrowUpRight,
  Clock,
  CheckCircle,
} from "lucide-react";
import { fetchProjects, deleteProject } from "@/lib/api";
import { Project } from "@/lib/types";
import ImportModal from "@/components/ImportModal";

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [isImportOpen, setIsImportOpen] = useState(false);

  const loadProjects = async () => {
    setLoading(true);
    try {
      const data = await fetchProjects();
      setProjects(data);
    } catch (err) {
      console.error("Failed to load projects:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const handleDelete = async (e: React.MouseEvent, project: Project) => {
    e.preventDefault();
    e.stopPropagation();

    if (
      confirm(
        `Are you sure you want to delete project '${project.project_code} - ${project.name}'?\nThis will permanently delete all associated WBS, activities, and relationships from PostgreSQL.`
      )
    ) {
      try {
        await deleteProject(project.id);
        loadProjects();
      } catch (err: any) {
        alert(err.message || "Failed to delete project.");
      }
    }
  };

  const formatDate = (val: string | null) => {
    if (!val) return "Not specified";
    try {
      return new Date(val).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return val;
    }
  };

  const totalActivities = projects.reduce((acc, p) => acc + (p.activity_count || 0), 0);
  const totalWBS = projects.reduce((acc, p) => acc + (p.wbs_count || 0), 0);
  const totalRels = projects.reduce((acc, p) => acc + (p.relationship_count || 0), 0);

  return (
    <div className="space-y-8">
      {/* Top Banner & Action */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Schedule Management
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Import, view, validate, and edit Primavera P6 schedules across XER, XML, CSV, and XLSX formats.
          </p>
        </div>

        <button
          onClick={() => setIsImportOpen(true)}
          className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-md hover:bg-blue-500 transition-all hover:shadow-lg self-start sm:self-auto"
        >
          <Plus className="h-5 w-5" />
          Import Schedule File
        </button>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Projects</span>
            <FolderGit2 className="h-5 w-5 text-blue-500" />
          </div>
          <div className="mt-3 text-2xl font-black text-slate-900">{projects.length}</div>
          <div className="mt-1 text-xs text-slate-500">Stored in PostgreSQL</div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Activities</span>
            <ActivityIcon className="h-5 w-5 text-emerald-500" />
          </div>
          <div className="mt-3 text-2xl font-black text-slate-900">{totalActivities}</div>
          <div className="mt-1 text-xs text-slate-500">Across all projects</div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">WBS Elements</span>
            <Layers className="h-5 w-5 text-indigo-500" />
          </div>
          <div className="mt-3 text-2xl font-black text-slate-900">{totalWBS}</div>
          <div className="mt-1 text-xs text-slate-500">Hierarchical nodes</div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Logic Links</span>
            <GitFork className="h-5 w-5 text-amber-500" />
          </div>
          <div className="mt-3 text-2xl font-black text-slate-900">{totalRels}</div>
          <div className="mt-1 text-xs text-slate-500">Relationships (FS/SS/FF/SF)</div>
        </div>
      </div>

      {/* Projects List */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-slate-900">Projects Overview</h2>

        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-slate-400">
            Loading schedules from PostgreSQL...
          </div>
        ) : projects.length === 0 ? (
          <div className="rounded-xl border-2 border-dashed border-slate-300 bg-white p-12 text-center space-y-4">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-blue-600">
              <Calendar className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-800">No schedules imported yet</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Get started by importing a Primavera <code className="font-mono font-semibold">.xer</code>,{" "}
                <code className="font-mono font-semibold">.xml</code>,{" "}
                <code className="font-mono font-semibold">.csv</code>, or{" "}
                <code className="font-mono font-semibold">.xlsx</code> file.
              </p>
            </div>
            <button
              onClick={() => setIsImportOpen(true)}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-blue-500 transition-colors"
            >
              <Plus className="h-4 w-4" />
              Import First Schedule
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((proj) => (
              <Link
                key={proj.id}
                href={`/projects/${proj.id}`}
                className="group relative flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-6 shadow-sm hover:border-blue-500 hover:shadow-md transition-all"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-100">
                        {proj.project_code}
                      </span>
                      <h3 className="mt-2 text-base font-bold text-slate-900 group-hover:text-blue-600 transition-colors line-clamp-1">
                        {proj.name}
                      </h3>
                    </div>
                    <button
                      onClick={(e) => handleDelete(e, proj)}
                      className="text-slate-300 hover:text-red-600 p-1 rounded transition-colors"
                      title="Delete project"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>

                  {/* Dates */}
                  <div className="mt-4 space-y-1.5 text-xs text-slate-600">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Planned Start:</span>
                      <span className="font-medium text-slate-700">
                        {formatDate(proj.planned_start)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Planned Finish:</span>
                      <span className="font-medium text-slate-700">
                        {formatDate(proj.planned_finish)}
                      </span>
                    </div>
                    {proj.data_date && (
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Data Date:</span>
                        <span className="font-medium text-slate-700">
                          {formatDate(proj.data_date)}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Metrics Footer */}
                <div className="mt-6 border-t border-slate-100 pt-4">
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div className="rounded-lg bg-slate-50 p-2">
                      <div className="font-bold text-slate-900">{proj.activity_count}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">Activities</div>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-2">
                      <div className="font-bold text-slate-900">{proj.wbs_count}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">WBS Nodes</div>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-2">
                      <div className="font-bold text-slate-900">{proj.relationship_count}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">Links</div>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center justify-end text-xs font-semibold text-blue-600 group-hover:translate-x-0.5 transition-transform">
                    Open Project Workspace <ArrowUpRight className="ml-1 h-3.5 w-3.5" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Import Modal */}
      <ImportModal
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        onImportSuccess={() => loadProjects()}
      />
    </div>
  );
}
