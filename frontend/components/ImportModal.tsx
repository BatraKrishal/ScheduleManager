"use client";

import React, { useState, useRef } from "react";
import {
  UploadCloud,
  FileText,
  AlertCircle,
  CheckCircle2,
  X,
  Loader2,
  FileSpreadsheet,
  FileCode,
} from "lucide-react";
import { uploadScheduleFile, ApiError } from "@/lib/api";
import { Project, ValidationErrorDetail } from "@/lib/types";

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportSuccess: (project: Project) => void;
}

type StepState = "idle" | "uploading" | "parsing" | "validating" | "importing" | "complete" | "error";

const STEPS = [
  { key: "uploading", label: "Uploading" },
  { key: "parsing", label: "Parsing Document" },
  { key: "validating", label: "Validating Logic" },
  { key: "importing", label: "Importing to PostgreSQL" },
  { key: "complete", label: "Complete" },
];

export default function ImportModal({
  isOpen,
  onClose,
  onImportSuccess,
}: ImportModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [step, setStep] = useState<StepState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<ValidationErrorDetail[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      selectFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      selectFile(e.target.files[0]);
    }
  };

  const selectFile = (selected: File) => {
    setFile(selected);
    setErrorMessage(null);
    setValidationErrors([]);
    setStep("idle");
  };

  const getFileIcon = (name: string) => {
    const ext = name.split(".").pop()?.toLowerCase();
    if (ext === "xer") return <FileText className="h-8 w-8 text-blue-600" />;
    if (ext === "xml") return <FileCode className="h-8 w-8 text-amber-600" />;
    if (ext === "csv" || ext === "xlsx") return <FileSpreadsheet className="h-8 w-8 text-emerald-600" />;
    return <FileText className="h-8 w-8 text-slate-500" />;
  };

  const handleUpload = async () => {
    if (!file) return;

    setErrorMessage(null);
    setValidationErrors([]);
    setStep("uploading");

    // Stepper progression
    const t1 = setTimeout(() => setStep("parsing"), 400);
    const t2 = setTimeout(() => setStep("validating"), 1000);
    const t3 = setTimeout(() => setStep("importing"), 1600);

    try {
      const project = await uploadScheduleFile(file);
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      setStep("complete");
      setTimeout(() => {
        onImportSuccess(project);
        handleClose();
      }, 900);
    } catch (err: any) {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      setStep("error");

      if (err instanceof ApiError && err.validation) {
        setErrorMessage(err.validation.error || "Schedule validation failed");
        setValidationErrors(err.validation.errors || []);
      } else {
        setErrorMessage(err.message || "Failed to import schedule file.");
        setValidationErrors([]);
      }
    }
  };

  const handleClose = () => {
    setFile(null);
    setStep("idle");
    setErrorMessage(null);
    setValidationErrors([]);
    onClose();
  };

  const currentStepIndex = STEPS.findIndex((s) => s.key === step);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-xl rounded-xl bg-white shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div>
            <h3 className="text-lg font-bold text-slate-900">Upload Primavera Schedule</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Import and normalize schedule into PostgreSQL database
            </p>
          </div>
          <button
            onClick={handleClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Dropzone */}
          {step === "idle" && (
            <div>
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => inputRef.current?.click()}
                className={`relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-all ${
                  dragActive
                    ? "border-blue-500 bg-blue-50/50"
                    : "border-slate-300 hover:border-blue-400 bg-slate-50/50 hover:bg-slate-50"
                }`}
              >
                <input
                  ref={inputRef}
                  type="file"
                  accept=".xer,.xml,.csv,.xlsx,.tsv"
                  onChange={handleFileChange}
                  className="hidden"
                />

                {file ? (
                  <div className="flex flex-col items-center gap-2 py-2">
                    {getFileIcon(file.name)}
                    <div className="text-center">
                      <div className="font-bold text-slate-900 text-sm">{file.name}</div>
                      <div className="text-xs text-slate-500">
                        {(file.size / 1024).toFixed(1)} KB
                      </div>
                    </div>

                    <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 text-xs font-semibold text-emerald-700">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                      File ready to import
                    </div>

                    <p className="text-xs text-slate-500 mt-1">
                      Click the blue <strong className="text-blue-600">"Import Schedule"</strong> button below to import into PostgreSQL.
                    </p>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setFile(null);
                      }}
                      className="mt-1 text-xs text-slate-400 hover:text-slate-600 hover:underline transition-colors"
                    >
                      Choose a different file
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-3">
                    <div className="rounded-full bg-blue-100 p-3 text-blue-600">
                      <UploadCloud className="h-7 w-7" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-700">
                        Click to upload or drag and drop
                      </p>
                      <p className="text-xs text-slate-500 mt-1">
                        Supported: <span className="font-medium text-slate-700">.xer, .xml, .csv, .xlsx</span>
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Supported Format Pills */}
              <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs">
                <span className="rounded-full bg-blue-50 border border-blue-200 px-2.5 py-0.5 font-medium text-blue-700">
                  Primavera XER
                </span>
                <span className="rounded-full bg-amber-50 border border-amber-200 px-2.5 py-0.5 font-medium text-amber-700">
                  P6 XML
                </span>
                <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 font-medium text-emerald-700">
                  Primavera CSV
                </span>
                <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 font-medium text-emerald-700">
                  Excel XLSX
                </span>
              </div>
            </div>
          )}

          {/* Stepper Progress */}
          {step !== "idle" && step !== "error" && (
            <div className="py-6 space-y-6">
              <div className="flex items-center justify-center gap-3">
                <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
                <span className="text-sm font-semibold text-slate-800">
                  {step === "complete" ? "Schedule Imported!" : "Processing Schedule..."}
                </span>
              </div>

              <div className="space-y-3">
                {STEPS.map((s, idx) => {
                  const isDone = currentStepIndex > idx || step === "complete";
                  const isCurrent = step === s.key;
                  return (
                    <div key={s.key} className="flex items-center gap-3">
                      <div className="flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold">
                        {isDone ? (
                          <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                        ) : isCurrent ? (
                          <div className="h-2.5 w-2.5 rounded-full bg-blue-600 animate-ping" />
                        ) : (
                          <div className="h-2 w-2 rounded-full bg-slate-300" />
                        )}
                      </div>
                      <span
                        className={`text-sm ${
                          isDone
                            ? "font-medium text-slate-800"
                            : isCurrent
                            ? "font-bold text-blue-600"
                            : "text-slate-400"
                        }`}
                      >
                        {s.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Error Display */}
          {step === "error" && (
            <div className="space-y-4">
              <div className="rounded-lg bg-red-50 border border-red-200 p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <h4 className="text-sm font-semibold text-red-900">
                      {errorMessage || "Import Error"}
                    </h4>
                    <p className="text-xs text-red-700 mt-1">
                      The schedule file failed validation or parsing checks. No changes were committed to the database.
                    </p>
                  </div>
                </div>
              </div>

              {validationErrors.length > 0 && (
                <div className="max-h-52 overflow-y-auto rounded-lg border border-slate-200 bg-white p-3 text-xs">
                  <div className="font-semibold text-slate-700 mb-2">
                    Detailed Validation Issues ({validationErrors.length}):
                  </div>
                  <ul className="divide-y divide-slate-100">
                    {validationErrors.map((v, i) => (
                      <li key={i} className="py-1.5">
                        {v.field && (
                          <span className="font-mono text-slate-500 mr-2 bg-slate-100 px-1 py-0.5 rounded">
                            {v.field}
                          </span>
                        )}
                        <span className="text-slate-800">{v.message}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <button
                type="button"
                onClick={() => setStep("idle")}
                className="w-full rounded-lg bg-slate-100 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200 transition-colors"
              >
                Try Another File
              </button>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        {step === "idle" && (
          <div className="flex items-center justify-end gap-3 border-t border-slate-100 bg-slate-50/50 px-6 py-4">
            <button
              type="button"
              onClick={handleClose}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!file}
              onClick={handleUpload}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Import Schedule
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
