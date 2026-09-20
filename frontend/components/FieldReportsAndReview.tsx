"use client";

import React, { useState, useEffect } from "react";
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  Clock,
  ExternalLink,
  RefreshCw,
  Sliders,
  Check,
  X,
  FileSpreadsheet,
  Mic,
  ShieldCheck,
  Download,
} from "lucide-react";
import {
  uploadFieldArtifact,
  fetchProjectArtifacts,
  extractArtifact,
  evaluateMatching,
  fetchReviewQueue,
  submitReviewDecision,
  fetchAuditTrail,
  getExportXerUrl,
} from "@/lib/api";
import { Artifact, ReviewQueueItem, AuditLogItem } from "@/lib/types";

interface FieldReportsAndReviewProps {
  projectId: string;
  onScheduleUpdated: () => void;
}

export default function FieldReportsAndReview({
  projectId,
  onScheduleUpdated,
}: FieldReportsAndReviewProps) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [queueItems, setQueueItems] = useState<ReviewQueueItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [reportId, setReportId] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadSuccessMsg, setUploadSuccessMsg] = useState<string | null>(null);
  const [activeArtifactId, setActiveArtifactId] = useState<string | null>(null);

  // Processing state
  const [extracting, setExtracting] = useState(false);
  const [matching, setMatching] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Review decision state for each item
  const [selectedCandidates, setSelectedCandidates] = useState<Record<string, string>>({});
  const [adjustPercents, setAdjustPercents] = useState<Record<string, string>>({});
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [submittingReview, setSubmittingReview] = useState<Record<string, boolean>>({});

  const refreshAll = async () => {
    setLoading(true);
    try {
      const [artList, qRes, auditRes] = await Promise.all([
        fetchProjectArtifacts(projectId),
        fetchReviewQueue(projectId),
        fetchAuditTrail(projectId),
      ]);
      setArtifacts(artList);
      setQueueItems(qRes.items);
      setAuditLogs(auditRes.audit_trail);
    } catch (err) {
      console.error("Failed to fetch integration data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectId) {
      refreshAll();
    }
  }, [projectId]);

  const [autoProcess, setAutoProcess] = useState(true);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setUploading(true);
    setUploadSuccessMsg(null);
    setActionMessage(null);

    try {
      const res = await uploadFieldArtifact(projectId, selectedFile, reportId.trim() || undefined);
      const artId = res.artifact.artifact_id;
      setActiveArtifactId(artId);
      setSelectedFile(null);
      setReportId("");

      if (autoProcess) {
        setUploadSuccessMsg("Uploaded to MinIO. Running extraction and matching...");
        setExtracting(true);
        try {
          const extRes = await extractArtifact(artId);
          setMatching(true);
          const matchRes = await evaluateMatching(projectId);
          setActionMessage(
            `Automated Pipeline Complete: Extracted ${extRes.events_extracted} event(s) | ${matchRes.auto_linked_count} auto-linked, ${matchRes.review_queued_count} queued for review.`
          );
          setUploadSuccessMsg(
            `Artifact saved in MinIO (${res.artifact.original_filename}) • ${extRes.events_extracted} events extracted & matched!`
          );
          onScheduleUpdated();
        } catch (pipeErr: any) {
          setActionMessage(`Uploaded to MinIO, but automated extraction/matching encountered: ${pipeErr.message}. You can retry using the buttons below.`);
        } finally {
          setExtracting(false);
          setMatching(false);
        }
      } else {
        setUploadSuccessMsg(
          `${res.is_duplicate ? "Duplicate detected: " : "Success: "} ${res.message} (SHA-256: ${res.artifact.sha256.substring(0, 12)}...)`
        );
      }

      await refreshAll();
    } catch (err: any) {
      setActionMessage(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleRunExtraction = async (artId: string, forceReextract: boolean = false) => {
    setExtracting(true);
    setActionMessage(null);
    try {
      const res = await extractArtifact(artId, forceReextract);
      if (forceReextract) {
        setActionMessage(
          `Re-extraction complete: ${res.events_extracted} structured execution event(s) parsed fresh from MinIO.`
        );
      } else {
        setActionMessage(
          `Artifact verified: ${res.events_extracted} event(s) loaded (already extracted, duplicate creation prevented).`
        );
      }
      await refreshAll();
    } catch (err: any) {
      setActionMessage(`Extraction failed: ${err.message}`);
    } finally {
      setExtracting(false);
    }
  };

  const handleRunMatching = async () => {
    setMatching(true);
    setActionMessage(null);
    try {
      const res = await evaluateMatching(projectId);
      setActionMessage(
        `Matching complete: ${res.auto_linked_count} auto-linked, ${res.review_queued_count} placed in Planner Review.`
      );
      onScheduleUpdated();
      await refreshAll();
    } catch (err: any) {
      setActionMessage(`Matching failed: ${err.message}`);
    } finally {
      setMatching(false);
    }
  };

  const handleDecision = async (
    eventId: string,
    decision: "APPROVED" | "REJECTED",
    defaultActivityId?: string
  ) => {
    const actId = selectedCandidates[eventId] || defaultActivityId;
    const adjStr = adjustPercents[eventId];
    const adjPct = adjStr ? parseFloat(adjStr) : undefined;
    const notes = reviewNotes[eventId] || "";

    setSubmittingReview((prev) => ({ ...prev, [eventId]: true }));
    try {
      await submitReviewDecision({
        event_id: eventId,
        decision,
        activity_id: actId,
        adjustment_percent: adjPct,
        reviewer_id: "planner-user",
        notes,
      });
      onScheduleUpdated();
      await refreshAll();
    } catch (err: any) {
      alert(`Decision error: ${err.message}`);
    } finally {
      setSubmittingReview((prev) => ({ ...prev, [eventId]: false }));
    }
  };

  return (
    <div className="space-y-8">
      {/* Action Notification Banner */}
      {actionMessage && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-xs font-semibold text-blue-900 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-blue-600" />
            {actionMessage}
          </div>
          <button
            onClick={() => setActionMessage(null)}
            className="text-blue-500 hover:text-blue-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Top Controls: Upload & Pipeline Trigger */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload Card */}
        <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="rounded-lg bg-blue-50 p-2 text-blue-600 border border-blue-100">
                <UploadCloud className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Ingest Field Execution Artifact
                </h3>
                <p className="text-xs text-slate-500">
                  Store PDF reports, contractor spreadsheets, or voice memos permanently in MinIO.
                </p>
              </div>
            </div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
              MinIO S3 Storage
            </span>
          </div>

          <form onSubmit={handleUpload} className="space-y-3 pt-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Select Field Report (PDF / Excel / CSV / Audio)
                </label>
                <input
                  type="file"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="block w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                  accept=".pdf,.xlsx,.xls,.csv,.m4a,.mp3,.wav,.ogg"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Daily Report Grouping ID (Optional)
                </label>
                <input
                  type="text"
                  value={reportId}
                  onChange={(e) => setReportId(e.target.value)}
                  placeholder="e.g. rep-2026-09-18"
                  className="w-full text-xs rounded-lg border border-slate-200 px-3 py-1.5 focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
              <div className="flex items-center gap-2">
                <button
                  type="submit"
                  disabled={!selectedFile || uploading}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-500 disabled:opacity-50 transition-colors flex items-center gap-2"
                >
                  {uploading ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Processing...
                    </>
                  ) : (
                    <>
                      <UploadCloud className="h-3.5 w-3.5" />
                      {autoProcess ? "Upload & Auto-Process" : "Upload to MinIO"}
                    </>
                  )}
                </button>

                <label className="flex items-center gap-1.5 text-xs text-slate-600 select-none cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoProcess}
                    onChange={(e) => setAutoProcess(e.target.checked)}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span>Auto-extract & match immediately</span>
                </label>
              </div>

              {uploadSuccessMsg && (
                <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1.5">
                  <Check className="h-4 w-4" /> {uploadSuccessMsg}
                </span>
              )}
            </div>
          </form>
        </div>

        {/* Pipeline Control Card */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center gap-2 text-slate-900 font-bold text-base">
              <Sliders className="h-5 w-5 text-indigo-600" />
              Pipeline Operations
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Trigger asynchronous extraction and multi-signal CPM matching.
            </p>
          </div>

          <div className="space-y-2.5">
            {activeArtifactId && (
              <button
                onClick={() => {
                  const isExtracted = artifacts.find((x) => x.artifact_id === activeArtifactId)?.extraction_status === "EXTRACTED";
                  if (isExtracted) {
                    if (window.confirm("This artifact has already been extracted. Re-extract fresh with the LLM? (Unapproved events will be refreshed cleanly)")) {
                      handleRunExtraction(activeArtifactId, true);
                    }
                  } else {
                    handleRunExtraction(activeArtifactId, false);
                  }
                }}
                disabled={extracting}
                className="w-full rounded-lg bg-indigo-50 border border-indigo-200 px-3 py-2 text-xs font-bold text-indigo-700 hover:bg-indigo-100 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${extracting ? "animate-spin" : ""}`} />
                {artifacts.find((x) => x.artifact_id === activeArtifactId)?.extraction_status === "EXTRACTED"
                  ? "Re-extract Stored Artifact"
                  : "Extract Stored Artifact"}
              </button>
            )}

            <button
              onClick={handleRunMatching}
              disabled={matching}
              className="w-full rounded-lg bg-slate-900 px-3 py-2 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-50 flex items-center justify-center gap-2 shadow-sm"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${matching ? "animate-spin" : ""}`} />
              Run Matching & Auto-Link
            </button>

            <a
              href={getExportXerUrl(projectId)}
              download
              className="w-full rounded-lg bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs font-bold text-emerald-800 hover:bg-emerald-100 flex items-center justify-center gap-2"
            >
              <Download className="h-3.5 w-3.5" />
              Export Updated P6 (.XER)
            </a>
          </div>
        </div>
      </div>

      {/* Planner Review Queue Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold text-slate-900">Planner Human Review Queue</h3>
            <span className="rounded-full bg-amber-100 border border-amber-200 text-amber-800 font-mono text-xs px-2.5 py-0.5 font-bold">
              {queueItems.length} Ambiguous
            </span>
          </div>
          <button
            onClick={refreshAll}
            className="text-xs font-semibold text-slate-500 hover:text-slate-800 flex items-center gap-1"
          >
            <RefreshCw className="h-3 w-3" /> Refresh
          </button>
        </div>

        {queueItems.length === 0 ? (
          <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-xs text-slate-400">
            No pending ambiguous events in review queue. All field progress has been processed or auto-linked.
          </div>
        ) : (
          <div className="space-y-4">
            {queueItems.map((item) => {
              const ev = item.event;
              const isSubmitting = submittingReview[ev.event_id] || false;
              const topCand = item.candidates[0];

              return (
                <div
                  key={ev.event_id}
                  className="rounded-xl border border-amber-200 bg-amber-50/30 p-5 space-y-4 shadow-sm"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-amber-100 pb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-amber-900 bg-amber-100 px-2 py-0.5 rounded border border-amber-200">
                        {ev.source_document_name}
                      </span>
                      <span className="text-xs text-slate-500">
                        Date: {ev.execution_date} | Page {ev.page_number}
                      </span>
                    </div>

                    {item.artifact_view_url && (
                      <a
                        href={item.artifact_view_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-xs font-bold text-blue-600 hover:text-blue-800 underline"
                      >
                        <ExternalLink className="h-3 w-3" /> View Original Evidence in MinIO
                      </a>
                    )}
                  </div>

                  {/* Verbatim Excerpt */}
                  <div className="rounded-lg bg-white p-3 border border-slate-200 text-xs">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                      Verbatim Field Report Excerpt
                    </div>
                    <div className="font-mono text-slate-800">{ev.verbatim_excerpt}</div>
                    {ev.quantity && (
                      <div className="mt-1 text-slate-500 text-[11px]">
                        Reported Quantity: <strong className="text-slate-700">{ev.quantity} {ev.unit}</strong> | Location: <strong className="text-slate-700">{ev.location || "N/A"}</strong>
                      </div>
                    )}
                  </div>

                  {/* Candidate Selection */}
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1.5">
                      Candidate Activities & Confidence Breakdown
                    </label>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {item.candidates.map((cand) => {
                        const isSelected =
                          (selectedCandidates[ev.event_id] || topCand?.activity_id) === cand.activity_id;

                        return (
                          <div
                            key={cand.activity_id}
                            onClick={() =>
                              setSelectedCandidates((prev) => ({
                                ...prev,
                                [ev.event_id]: cand.activity_id,
                              }))
                            }
                            className={`cursor-pointer rounded-lg p-3 text-xs border transition-colors ${
                              isSelected
                                ? "border-blue-500 bg-blue-50/50 shadow-sm"
                                : "border-slate-200 bg-white hover:border-slate-300"
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-mono font-bold text-slate-800">
                                {cand.activity_code}
                              </span>
                              <span
                                className={`font-bold px-1.5 py-0.5 rounded text-[10px] ${
                                  cand.match_score >= 0.85
                                    ? "bg-emerald-100 text-emerald-800"
                                    : "bg-amber-100 text-amber-800"
                                }`}
                              >
                                Score: {Math.round(cand.match_score * 100)}%
                              </span>
                            </div>
                            <div className="font-semibold text-slate-700 mt-1">
                              {cand.activity_name}
                            </div>
                            <div className="text-[10px] text-slate-400 mt-1 flex gap-2">
                              <span>Text: {cand.score_breakdown.s_text}</span>
                              <span>WBS: {cand.score_breakdown.s_wbs}</span>
                              <span>Temp: {cand.score_breakdown.s_temp}</span>
                              <span>Ctx: {cand.score_breakdown.s_context}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Planner Actions */}
                  <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-amber-100">
                    <div className="flex items-center gap-3">
                      <div>
                        <label className="text-[10px] font-bold text-slate-600 block">
                          Adjust Progress % (Optional)
                        </label>
                        <input
                          type="number"
                          placeholder="e.g. 50"
                          min="0"
                          max="100"
                          value={adjustPercents[ev.event_id] || ""}
                          onChange={(e) =>
                            setAdjustPercents((prev) => ({
                              ...prev,
                              [ev.event_id]: e.target.value,
                            }))
                          }
                          className="w-24 text-xs rounded border border-slate-300 px-2 py-1"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] font-bold text-slate-600 block">
                          Reviewer Notes
                        </label>
                        <input
                          type="text"
                          placeholder="Sign-off justification..."
                          value={reviewNotes[ev.event_id] || ""}
                          onChange={(e) =>
                            setReviewNotes((prev) => ({
                              ...prev,
                              [ev.event_id]: e.target.value,
                            }))
                          }
                          className="w-48 sm:w-64 text-xs rounded border border-slate-300 px-2 py-1"
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleDecision(ev.event_id, "REJECTED")}
                        disabled={isSubmitting}
                        className="rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-bold text-red-600 hover:bg-red-50 disabled:opacity-50 flex items-center gap-1"
                      >
                        <X className="h-3.5 w-3.5" /> Reject Match
                      </button>

                      <button
                        onClick={() =>
                          handleDecision(ev.event_id, "APPROVED", topCand?.activity_id)
                        }
                        disabled={isSubmitting}
                        className="rounded-lg bg-emerald-600 px-4 py-1.5 text-xs font-bold text-white hover:bg-emerald-500 disabled:opacity-50 flex items-center gap-1 shadow-sm"
                      >
                        <Check className="h-3.5 w-3.5" /> Approve & Update Schedule
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Stored Artifacts Repository */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold text-slate-900">Stored MinIO Field Artifacts</h3>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-50 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-200">
              <tr>
                <th className="px-4 py-3">Artifact File</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">SHA-256 Digest</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {artifacts.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-400">
                    No field artifacts stored yet.
                  </td>
                </tr>
              ) : (
                artifacts.map((a) => (
                  <tr key={a.artifact_id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-semibold text-slate-900 flex items-center gap-2">
                      {a.artifact_type === "PDF_REPORT" ? (
                        <FileText className="h-4 w-4 text-red-500" />
                      ) : a.artifact_type === "VOICE_MEMO" ? (
                        <Mic className="h-4 w-4 text-purple-500" />
                      ) : (
                        <FileSpreadsheet className="h-4 w-4 text-emerald-500" />
                      )}
                      {a.original_filename}
                    </td>
                    <td className="px-4 py-3 font-mono text-[10px] text-slate-500">
                      {a.artifact_type}
                    </td>
                    <td className="px-4 py-3 font-mono text-[10px] text-slate-500">
                      {a.sha256.substring(0, 16)}...
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {(a.size_bytes / 1024).toFixed(1)} KB
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                          a.extraction_status === "EXTRACTED"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : a.extraction_status === "PROCESSING"
                            ? "bg-blue-50 text-blue-700 border border-blue-200"
                            : "bg-slate-100 text-slate-700 border border-slate-200"
                        }`}
                      >
                        {a.extraction_status === "EXTRACTED" && <Check className="h-3 w-3" />}
                        {a.extraction_status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {a.extraction_status === "EXTRACTED" ? (
                        <div className="inline-flex items-center gap-2 justify-end">
                          <span className="text-[11px] text-emerald-700 font-semibold flex items-center gap-1">
                            <Check className="h-3 w-3" /> Extracted
                          </span>
                          <button
                            onClick={() => {
                              if (window.confirm("Re-extract this report with the LLM? This will refresh all unapproved events and prevent duplicates.")) {
                                handleRunExtraction(a.artifact_id, true);
                              }
                            }}
                            className="text-[10px] text-slate-400 hover:text-blue-600 underline font-medium transition-colors"
                            title="Re-run LLM extraction fresh from MinIO"
                          >
                            Re-extract
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleRunExtraction(a.artifact_id, false)}
                          className="font-bold text-blue-600 hover:text-blue-800 text-[11px]"
                        >
                          Extract
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Forensic Audit Trail */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-emerald-600" />
            <h3 className="text-lg font-bold text-slate-900">Forensic Audit Trail & Schedule Lineage</h3>
          </div>
          <span className="text-xs text-slate-400">
            {auditLogs.length} Verified Mutations
          </span>
        </div>

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-50 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-200">
              <tr>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Activity</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Authorized By</th>
                <th className="px-4 py-3">Source MinIO Evidence Artifact</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {auditLogs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-400">
                    No schedule mutations recorded yet.
                  </td>
                </tr>
              ) : (
                auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-mono text-[10px] text-slate-500">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-mono font-bold text-slate-800">
                        {log.activity_code || log.activity_id}
                      </div>
                      <div className="text-[11px] text-slate-500">{log.activity_name}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                        {log.action}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700 font-semibold">{log.user_id}</td>
                    <td className="px-4 py-3">
                      {log.artifact ? (
                        <div>
                          <div className="font-semibold text-slate-800">
                            {log.artifact.original_filename}
                          </div>
                          <div className="font-mono text-[10px] text-slate-400">
                            {log.artifact.storage_key}
                          </div>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">Manual mutation</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
