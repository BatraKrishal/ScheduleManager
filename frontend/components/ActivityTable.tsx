"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Search,
  SlidersHorizontal,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  Edit2,
  Trash2,
  Plus,
  RefreshCw,
} from "lucide-react";
import { fetchActivities, deleteActivity, fetchProjectWbs } from "@/lib/api";
import { Activity, ActivityStatus, WBSNode } from "@/lib/types";

interface ActivityTableProps {
  projectId: string;
  onEditActivity: (activity: Activity) => void;
  onAddActivity: () => void;
  refreshTrigger: number;
}

export default function ActivityTable({
  projectId,
  onEditActivity,
  onAddActivity,
  refreshTrigger,
}: ActivityTableProps) {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);

  // Filters
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [wbsFilter, setWbsFilter] = useState<string>("");
  const [sortBy, setSortBy] = useState<string>("activity_code");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  // WBS List for filter
  const [wbsList, setWbsList] = useState<WBSNode[]>([]);

  useEffect(() => {
    fetchProjectWbs(projectId)
      .then(setWbsList)
      .catch((err) => console.error("Error loading WBS:", err));
  }, [projectId]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchActivities(projectId, {
        activity_code: searchTerm || undefined,
        name: searchTerm || undefined,
        status: statusFilter || undefined,
        wbs_id: wbsFilter || undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
        page,
        page_size: pageSize,
      });
      setActivities(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      console.error("Failed to load activities:", err);
    } finally {
      setLoading(false);
    }
  }, [projectId, searchTerm, statusFilter, wbsFilter, sortBy, sortDir, page, pageSize]);

  useEffect(() => {
    loadData();
  }, [loadData, refreshTrigger]);

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(column);
      setSortDir("asc");
    }
    setPage(1);
  };

  const handleDelete = async (activity: Activity) => {
    if (
      confirm(
        `Are you sure you want to delete activity '${activity.activity_code} - ${activity.name}'?`
      )
    ) {
      try {
        await deleteActivity(activity.id);
        loadData();
      } catch (err: any) {
        alert(err.message || "Failed to delete activity.");
      }
    }
  };

  const formatDate = (dtStr: string | null) => {
    if (!dtStr) return "-";
    try {
      const d = new Date(dtStr);
      return d.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return dtStr;
    }
  };

  const getStatusBadge = (status: ActivityStatus) => {
    switch (status) {
      case "COMPLETED":
        return (
          <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 border border-emerald-200">
            Completed
          </span>
        );
      case "IN_PROGRESS":
        return (
          <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700 border border-blue-200">
            In Progress
          </span>
        );
      case "NOT_STARTED":
      default:
        return (
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 border border-slate-200">
            Not Started
          </span>
        );
    }
  };

  return (
    <div className="space-y-4">
      {/* Search & Filter Header Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex flex-wrap items-center gap-3 flex-1">
          {/* Search Box */}
          <div className="relative min-w-[240px] flex-1 max-w-sm">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search code or name..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setPage(1);
              }}
              className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="NOT_STARTED">Not Started</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="COMPLETED">Completed</option>
          </select>

          {/* WBS Filter */}
          {wbsList.length > 0 && (
            <select
              value={wbsFilter}
              onChange={(e) => {
                setWbsFilter(e.target.value);
                setPage(1);
              }}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 max-w-[200px] truncate"
            >
              <option value="">All WBS</option>
              {wbsList.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} - {w.name}
                </option>
              ))}
            </select>
          )}

          <button
            onClick={loadData}
            title="Refresh"
            className="rounded-lg border border-slate-300 p-2 text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>

        <button
          onClick={onAddActivity}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 transition-colors whitespace-nowrap"
        >
          <Plus className="h-4 w-4" />
          Add Activity
        </button>
      </div>

      {/* Spreadsheet Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
              <tr>
                <th
                  onClick={() => handleSort("activity_code")}
                  className="px-4 py-3 cursor-pointer hover:text-slate-900 transition-colors whitespace-nowrap"
                >
                  <div className="flex items-center gap-1">
                    Activity ID
                    <ArrowUpDown className="h-3 w-3 text-slate-400" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("name")}
                  className="px-4 py-3 cursor-pointer hover:text-slate-900 transition-colors"
                >
                  <div className="flex items-center gap-1">
                    Activity Name
                    <ArrowUpDown className="h-3 w-3 text-slate-400" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("wbs")}
                  className="px-4 py-3 cursor-pointer hover:text-slate-900 transition-colors"
                >
                  <div className="flex items-center gap-1">
                    WBS
                    <ArrowUpDown className="h-3 w-3 text-slate-400" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("status")}
                  className="px-4 py-3 cursor-pointer hover:text-slate-900 transition-colors"
                >
                  <div className="flex items-center gap-1">
                    Status
                    <ArrowUpDown className="h-3 w-3 text-slate-400" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("planned_start")}
                  className="px-4 py-3 cursor-pointer hover:text-slate-900 transition-colors whitespace-nowrap"
                >
                  <div className="flex items-center gap-1">
                    Start
                    <ArrowUpDown className="h-3 w-3 text-slate-400" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("planned_finish")}
                  className="px-4 py-3 cursor-pointer hover:text-slate-900 transition-colors whitespace-nowrap"
                >
                  <div className="flex items-center gap-1">
                    Finish
                    <ArrowUpDown className="h-3 w-3 text-slate-400" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("original_duration")}
                  className="px-4 py-3 cursor-pointer hover:text-slate-900 transition-colors whitespace-nowrap text-right"
                >
                  <div className="flex items-center justify-end gap-1">
                    Dur (d)
                    <ArrowUpDown className="h-3 w-3 text-slate-400" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("percent_complete")}
                  className="px-4 py-3 cursor-pointer hover:text-slate-900 transition-colors whitespace-nowrap"
                >
                  <div className="flex items-center gap-1">
                    % Complete
                    <ArrowUpDown className="h-3 w-3 text-slate-400" />
                  </div>
                </th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-normal">
              {loading ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-400">
                    Loading schedule activities...
                  </td>
                </tr>
              ) : activities.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-400">
                    No activities found matching your criteria.
                  </td>
                </tr>
              ) : (
                activities.map((act) => (
                  <tr
                    key={act.id}
                    onClick={() => onEditActivity(act)}
                    className="hover:bg-blue-50/40 cursor-pointer transition-colors group"
                  >
                    <td className="px-4 py-3 font-semibold text-slate-900 whitespace-nowrap font-mono text-xs">
                      {act.activity_code}
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-800 max-w-xs truncate">
                      {act.name}
                    </td>
                    <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                      {act.wbs_code || "-"}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {getStatusBadge(act.status)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-600">
                      {formatDate(act.planned_start)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-600">
                      {formatDate(act.planned_finish)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right font-mono text-xs text-slate-700">
                      {act.original_duration !== null ? `${act.original_duration}d` : "-"}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 rounded-full bg-slate-100 overflow-hidden">
                          <div
                            className="h-full bg-blue-600 rounded-full"
                            style={{ width: `${act.percent_complete || 0}%` }}
                          />
                        </div>
                        <span className="text-xs font-mono text-slate-700">
                          {Math.round(act.percent_complete || 0)}%
                        </span>
                      </div>
                    </td>
                    <td
                      className="px-4 py-3 text-right whitespace-nowrap"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => onEditActivity(act)}
                          className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-blue-600 transition-colors"
                          title="Edit activity"
                        >
                          <Edit2 className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(act)}
                          className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-red-600 transition-colors"
                          title="Delete activity"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/50 px-4 py-3 text-xs text-slate-500">
          <div>
            Showing <span className="font-semibold text-slate-700">{activities.length}</span> of{" "}
            <span className="font-semibold text-slate-700">{total}</span> activities
          </div>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="rounded border border-slate-200 bg-white p-1 hover:bg-slate-50 disabled:opacity-40 transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span>
              Page <span className="font-semibold text-slate-700">{page}</span> of{" "}
              <span className="font-semibold text-slate-700">{totalPages}</span>
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="rounded border border-slate-200 bg-white p-1 hover:bg-slate-50 disabled:opacity-40 transition-colors"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
