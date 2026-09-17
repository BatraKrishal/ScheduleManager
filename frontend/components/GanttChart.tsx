"use client";

import React, { useState, useEffect, useMemo } from "react";
import { Calendar, ZoomIn, ZoomOut, RefreshCw } from "lucide-react";
import { fetchActivities } from "@/lib/api";
import { Activity } from "@/lib/types";

interface GanttChartProps {
  projectId: string;
  onEditActivity?: (activity: Activity) => void;
}

export default function GanttChart({ projectId, onEditActivity }: GanttChartProps) {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [zoomLevel, setZoomLevel] = useState<"days" | "weeks">("weeks");

  useEffect(() => {
    setLoading(true);
    fetchActivities(projectId, { page_size: 100, sort_by: "planned_start", sort_dir: "asc" })
      .then((res) => {
        // Only show activities that have planned dates
        const withDates = res.items.filter((a) => a.planned_start && a.planned_finish);
        setActivities(withDates.length > 0 ? withDates : res.items);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [projectId]);

  // Compute timeline boundaries
  const { minDate, maxDate, totalDays } = useMemo(() => {
    if (activities.length === 0) {
      const now = new Date();
      const end = new Date(now);
      end.setDate(end.getDate() + 60);
      return { minDate: now, maxDate: end, totalDays: 60 };
    }

    let earliest = new Date(activities[0].planned_start || new Date());
    let latest = new Date(activities[0].planned_finish || earliest);

    for (const a of activities) {
      if (a.planned_start) {
        const s = new Date(a.planned_start);
        if (s < earliest) earliest = s;
      }
      if (a.planned_finish) {
        const f = new Date(a.planned_finish);
        if (f > latest) latest = f;
      }
    }

    // Add padding days
    earliest.setDate(earliest.getDate() - 3);
    latest.setDate(latest.getDate() + 7);

    const diff = Math.max(7, Math.ceil((latest.getTime() - earliest.getTime()) / (1000 * 3600 * 24)));
    return { minDate: earliest, maxDate: latest, totalDays: diff };
  }, [activities]);

  const dayWidth = zoomLevel === "days" ? 32 : 12;
  const timelineWidth = totalDays * dayWidth;

  const getPosition = (startStr: string | null, finishStr: string | null) => {
    if (!startStr) return { left: 0, width: 40 };

    const start = new Date(startStr);
    const finish = finishStr ? new Date(finishStr) : new Date(start.getTime() + 24 * 3600 * 1000);

    const startDiff = (start.getTime() - minDate.getTime()) / (1000 * 3600 * 24);
    const durDays = Math.max(1, (finish.getTime() - start.getTime()) / (1000 * 3600 * 24));

    const left = Math.max(0, startDiff * dayWidth);
    const width = Math.max(16, durDays * dayWidth);

    return { left, width };
  };

  // Generate date markers for header
  const headerMarks = useMemo(() => {
    const marks = [];
    const step = zoomLevel === "days" ? 1 : 7;
    for (let d = 0; d < totalDays; d += step) {
      const curDate = new Date(minDate);
      curDate.setDate(curDate.getDate() + d);
      marks.push({
        offset: d * dayWidth,
        label: curDate.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      });
    }
    return marks;
  }, [minDate, totalDays, dayWidth, zoomLevel]);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
      {/* Header controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 pb-4">
        <div>
          <h3 className="text-base font-bold text-slate-900">Schedule Gantt Timeline</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Visual activity schedule timeline with progress tracking
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center rounded-lg border border-slate-200 p-1 text-xs bg-slate-50">
            <button
              onClick={() => setZoomLevel("weeks")}
              className={`px-3 py-1 rounded font-medium transition-colors ${
                zoomLevel === "weeks"
                  ? "bg-white text-blue-600 shadow-sm font-semibold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Weeks
            </button>
            <button
              onClick={() => setZoomLevel("days")}
              className={`px-3 py-1 rounded font-medium transition-colors ${
                zoomLevel === "days"
                  ? "bg-white text-blue-600 shadow-sm font-semibold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Days
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="py-16 text-center text-sm text-slate-400">Loading Gantt timeline...</div>
      ) : activities.length === 0 ? (
        <div className="py-16 text-center text-sm text-slate-400">
          No activities available to plot on timeline.
        </div>
      ) : (
        <div className="flex border border-slate-200 rounded-lg overflow-hidden bg-white">
          {/* Left frozen columns: Activity Info */}
          <div className="w-80 flex-shrink-0 border-r border-slate-200 bg-slate-50/50">
            <div className="h-10 border-b border-slate-200 px-4 flex items-center font-bold text-xs uppercase tracking-wider text-slate-500 bg-slate-100">
              Activity
            </div>
            <div className="divide-y divide-slate-100">
              {activities.map((act) => (
                <div
                  key={act.id}
                  onClick={() => onEditActivity && onEditActivity(act)}
                  className="h-12 px-4 flex items-center justify-between hover:bg-blue-50/40 cursor-pointer transition-colors"
                >
                  <div className="min-w-0 pr-2">
                    <div className="font-semibold text-slate-900 text-xs truncate">
                      {act.name}
                    </div>
                    <div className="font-mono text-[10px] text-slate-500">
                      {act.activity_code} {act.wbs_code ? `• ${act.wbs_code}` : ""}
                    </div>
                  </div>
                  <span className="text-[11px] font-mono text-slate-500 flex-shrink-0">
                    {act.original_duration !== null ? `${act.original_duration}d` : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Right scrollable timeline area */}
          <div className="flex-1 overflow-x-auto">
            <div style={{ width: `${timelineWidth}px` }} className="relative">
              {/* Timeline date header */}
              <div className="h-10 border-b border-slate-200 bg-slate-100 relative">
                {headerMarks.map((m, idx) => (
                  <div
                    key={idx}
                    style={{ left: `${m.offset}px` }}
                    className="absolute top-0 bottom-0 border-l border-slate-200 pl-1.5 flex items-center text-[10px] font-mono font-medium text-slate-500 whitespace-nowrap select-none"
                  >
                    {m.label}
                  </div>
                ))}
              </div>

              {/* Timeline activity bars */}
              <div className="divide-y divide-slate-100 relative">
                {activities.map((act) => {
                  const { left, width } = getPosition(act.planned_start, act.planned_finish);
                  const pct = Math.min(100, Math.max(0, act.percent_complete || 0));

                  const isComplete = act.status === "COMPLETED";
                  const isInProgress = act.status === "IN_PROGRESS";

                  const barColor = isComplete
                    ? "bg-emerald-600 border-emerald-700"
                    : isInProgress
                    ? "bg-blue-600 border-blue-700"
                    : "bg-slate-400 border-slate-500";

                  return (
                    <div
                      key={act.id}
                      className="h-12 relative flex items-center hover:bg-slate-50/50"
                    >
                      <div
                        style={{ left: `${left}px`, width: `${width}px` }}
                        onClick={() => onEditActivity && onEditActivity(act)}
                        title={`${act.activity_code}: ${act.name}\nStart: ${act.planned_start || "N/A"}\nFinish: ${act.planned_finish || "N/A"}\nDuration: ${act.original_duration || 0}d\nProgress: ${pct}%`}
                        className={`absolute h-6 rounded border shadow-sm cursor-pointer transition-transform hover:scale-[1.02] flex items-center overflow-hidden ${barColor}`}
                      >
                        {/* Shaded Progress Bar */}
                        {pct > 0 && (
                          <div
                            style={{ width: `${pct}%` }}
                            className="h-full bg-white/20 border-r border-white/30"
                          />
                        )}
                        <span className="absolute inset-0 flex items-center px-2 text-[10px] font-semibold text-white truncate drop-shadow-sm pointer-events-none">
                          {act.activity_code} ({pct}%)
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
