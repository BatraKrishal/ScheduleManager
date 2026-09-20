"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Send,
  Paperclip,
  Bot,
  User,
  CheckCircle2,
  Clock,
  AlertCircle,
  Sparkles,
  ArrowRight,
  RefreshCw,
  FileText,
  Menu,
  Plus,
} from "lucide-react";
import {
  startOrGetConversation,
  fetchAgentConversations,
  getAgentConversation,
  sendAgentMessage,
  uploadAgentAttachment,
  confirmUpdateProposal,
  fetchProject,
} from "@/lib/api";
import {
  TimeAgentConversation,
  TimeAgentConversationSummary,
  TimeAgentMessage,
  TimeAgentActionCard,
} from "@/lib/types";
import ConversationSidebar from "./time-agent/ConversationSidebar";
import ProposalCard from "./time-agent/ProposalCard";
import ClarificationCard from "./time-agent/ClarificationCard";

interface TimeAgentChatProps {
  projectId: string;
  projectName?: string;
  initialActivityId?: string | null;
  onScheduleUpdated?: () => void;
}

export default function TimeAgentChat({
  projectId,
  projectName: initialProjectName,
  initialActivityId,
  onScheduleUpdated,
}: TimeAgentChatProps) {
  const [conversations, setConversations] = useState<TimeAgentConversationSummary[]>([]);
  const [activeConversation, setActiveConversation] = useState<TimeAgentConversation | null>(null);
  const [messages, setMessages] = useState<TimeAgentMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [projectName, setProjectName] = useState<string>(initialProjectName || "");

  const [loadingList, setLoadingList] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Local storage key strictly scoped to current project
  const storageKey = `time_agent_selected_conv_${projectId}`;

  // Fetch project name if not passed in props
  useEffect(() => {
    if (!projectName && projectId) {
      fetchProject(projectId)
        .then((p) => setProjectName(p.name || p.project_code || ""))
        .catch(() => {});
    }
  }, [projectId, projectName]);

  // Load conversation summaries for current project
  const loadConversationList = useCallback(
    async (query?: string) => {
      if (!projectId) return;
      try {
        setLoadingList(true);
        const list = await fetchAgentConversations(projectId, query);
        setConversations(list);
      } catch (err: any) {
        console.error("Failed to fetch conversation list:", err);
      } finally {
        setLoadingList(false);
      }
    },
    [projectId]
  );

  // Debounced search query
  useEffect(() => {
    const timer = setTimeout(() => {
      loadConversationList(searchQuery);
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery, loadConversationList]);

  // Load a specific conversation by ID
  const selectConversation = useCallback(
    async (convId: string) => {
      if (!projectId || !convId) return;
      try {
        setLoadingMessages(true);
        setError(null);
        const fullConv = await getAgentConversation(projectId, convId);
        setActiveConversation(fullConv);
        setMessages(fullConv.history || []);
        // Remember in UI-local storage for browser refresh
        try {
          localStorage.setItem(storageKey, convId);
        } catch {}
      } catch (err: any) {
        console.error("Failed to load conversation:", err);
        setError(err.message || "Failed to load conversation history.");
      } finally {
        setLoadingMessages(false);
      }
    },
    [projectId, storageKey]
  );

  // Initialize workspace on project mount
  useEffect(() => {
    let isMounted = true;
    async function initWorkspace() {
      if (!projectId) return;
      setLoadingMessages(true);
      setError(null);

      try {
        // 1. Fetch conversation list strictly scoped to project
        const list = await fetchAgentConversations(projectId);
        if (!isMounted) return;
        setConversations(list);

        // 2. Check if a previously selected conversation exists in local storage
        let targetConvId: string | null = null;
        try {
          targetConvId = localStorage.getItem(storageKey);
        } catch {}

        // Verify saved convId actually belongs to this project's list
        const existsInProject = list.some((c) => c.id === targetConvId);

        if (targetConvId && existsInProject) {
          await selectConversation(targetConvId);
        } else if (list.length > 0) {
          // Select most recently updated conversation
          await selectConversation(list[0].id);
        } else {
          // If no conversations exist yet, create or retrieve initial conversation
          const newConv = await startOrGetConversation(projectId, initialActivityId || undefined);
          if (isMounted) {
            setActiveConversation(newConv);
            setMessages(newConv.history || []);
            try {
              localStorage.setItem(storageKey, newConv.conversation_id);
            } catch {}
            // Refresh conversation list
            const updatedList = await fetchAgentConversations(projectId);
            if (isMounted) setConversations(updatedList);
          }
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || "Failed to initialize Time Agent workspace.");
        }
      } finally {
        if (isMounted) setLoadingMessages(false);
      }
    }

    initWorkspace();

    return () => {
      isMounted = false;
    };
  }, [projectId, storageKey, initialActivityId, selectConversation]);

  // Scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loadingMessages, sendingMessage]);

  // Handle "+ New Chat"
  const handleNewChat = async () => {
    if (!projectId || sendingMessage) return;
    try {
      setLoadingMessages(true);
      setError(null);
      setSuccessBanner(null);

      // Force creation of a brand new clean conversation under CURRENT project
      const newConv = await startOrGetConversation(
        projectId,
        initialActivityId || undefined,
        true, // force_new = true
        "New Chat"
      );

      setActiveConversation(newConv);
      setMessages([]); // Completely clean message area
      try {
        localStorage.setItem(storageKey, newConv.conversation_id);
      } catch {}

      // Refresh sidebar list
      await loadConversationList();
    } catch (err: any) {
      setError(err.message || "Failed to create a new conversation.");
    } finally {
      setLoadingMessages(false);
    }
  };

  // Send a message
  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputText;
    if (!text.trim() || !activeConversation || sendingMessage) return;

    setInputText("");
    setError(null);
    setSuccessBanner(null);

    // Optimistically append user message to UI
    const tempUserMsg: TimeAgentMessage = {
      id: `temp-${Date.now()}`,
      sender: "USER",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setSendingMessage(true);

    try {
      const resp = await sendAgentMessage(
        projectId,
        activeConversation.conversation_id,
        text
      );

      const agentMsg: TimeAgentMessage = {
        id: resp.message_id,
        sender: resp.sender as "AGENT",
        content: resp.reply_text,
        message_metadata: resp.action_card || null,
        created_at: resp.created_at || new Date().toISOString(),
      };

      setMessages((prev) => [...prev, agentMsg]);

      // Refresh conversation list to update title and updated_at timestamp
      loadConversationList();
    } catch (err: any) {
      setError(err.message || "Failed to communicate with Time Agent.");
    } finally {
      setSendingMessage(false);
    }
  };

  // Handle Clarification Option Selection
  const handleSelectClarificationOption = (value: string) => {
    handleSendMessage(value);
  };

  // Handle Proposal Confirmation
  const handleConfirmProposal = async (proposalId: string) => {
    if (!activeConversation) return;
    try {
      setActionLoading(proposalId);
      setError(null);
      const res = await confirmUpdateProposal(
        projectId,
        activeConversation.conversation_id,
        proposalId,
        "CONFIRM"
      );

      setSuccessBanner(
        `Update confirmed! ${res.activity_code} advanced from ${res.previous_percent}% to ${res.new_percent}%.`
      );

      // Mutate local message card status to APPLIED
      setMessages((prev) =>
        prev.map((m) => {
          if (m.message_metadata?.proposal_id === proposalId) {
            return {
              ...m,
              message_metadata: {
                ...m.message_metadata,
                proposal_status: "APPLIED",
              },
            };
          }
          return m;
        })
      );

      if (onScheduleUpdated) {
        onScheduleUpdated();
      }

      // Re-fetch conversation to sync authoritative backend state
      selectConversation(activeConversation.conversation_id);
    } catch (err: any) {
      setError(err.message || "Failed to confirm update proposal.");
    } finally {
      setActionLoading(null);
    }
  };

  // Handle Proposal Rejection
  const handleRejectProposal = async (proposalId: string) => {
    if (!activeConversation) return;
    try {
      setActionLoading(proposalId);
      setError(null);
      await confirmUpdateProposal(
        projectId,
        activeConversation.conversation_id,
        proposalId,
        "REJECT"
      );

      setSuccessBanner("Proposal was rejected.");

      // Mutate local message card status to REJECTED
      setMessages((prev) =>
        prev.map((m) => {
          if (m.message_metadata?.proposal_id === proposalId) {
            return {
              ...m,
              message_metadata: {
                ...m.message_metadata,
                proposal_status: "REJECTED",
              },
            };
          }
          return m;
        })
      );

      selectConversation(activeConversation.conversation_id);
    } catch (err: any) {
      setError(err.message || "Failed to reject proposal.");
    } finally {
      setActionLoading(null);
    }
  };

  // Handle File Upload Attachment
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !activeConversation) return;

    try {
      setUploading(true);
      setError(null);
      setSuccessBanner(null);

      const userNoticeMsg: TimeAgentMessage = {
        id: `upload-${Date.now()}`,
        sender: "USER",
        content: `Uploaded shift report document: ${file.name}`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userNoticeMsg]);

      const resp = await uploadAgentAttachment(
        projectId,
        activeConversation.conversation_id,
        file
      );

      const agentMsg: TimeAgentMessage = {
        id: `agent-attach-${Date.now()}`,
        sender: "AGENT",
        content: resp.agent_message,
        message_metadata: resp.action_card || null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, agentMsg]);

      setSuccessBanner(
        `File processed: extracted ${resp.extracted_events_count} site execution events.`
      );

      loadConversationList();
    } catch (err: any) {
      setError(err.message || "Failed to process document attachment.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const samplePrompts = [
    "We poured 35 m3 concrete today for F-204",
    "Installed 18 meters of cable tray today",
    "Update CIV-1001 to 80%",
    "Show upcoming civil activities",
  ];

  return (
    <div className="flex h-[780px] bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl text-slate-100">
      {/* 1. ChatGPT-Style Conversation Sidebar */}
      <ConversationSidebar
        conversations={conversations}
        activeConversationId={activeConversation?.conversation_id || null}
        onSelectConversation={selectConversation}
        onNewChat={handleNewChat}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        loading={loadingList}
        projectName={projectName}
        isMobileDrawerOpen={isMobileDrawerOpen}
        onCloseMobileDrawer={() => setIsMobileDrawerOpen(false)}
      />

      {/* 2. Main Chat Panel */}
      <div className="flex-1 flex flex-col min-w-0 bg-slate-900">
        {/* Project Context Header */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-slate-950/90 border-b border-slate-800 backdrop-blur-md shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {/* Mobile Hamburger Toggle */}
            <button
              onClick={() => setIsMobileDrawerOpen(true)}
              className="md:hidden p-1.5 rounded-lg bg-slate-800 text-slate-300 hover:text-white"
              aria-label="Open conversation history"
            >
              <Menu className="h-4 w-4" />
            </button>

            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-blue-500/20 shrink-0">
              <Bot className="h-4.5 w-4.5" />
            </div>

            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white text-sm tracking-wide truncate">
                  {activeConversation?.title || "Time Agent"}
                </span>
                <span className="hidden sm:inline-block px-2 py-0.5 text-[10px] font-bold rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30 shrink-0">
                  Project-Scoped
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-400 truncate">
                <span className="text-slate-300 font-medium">
                  {projectName ? `Schedule: ${projectName}` : "Current Schedule"}
                </span>
                <span className="text-slate-600">·</span>
                <span className="text-slate-400">
                  {messages.length} {messages.length === 1 ? "message" : "messages"}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {activeConversation?.active_activity && (
              <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded-lg bg-slate-800/80 border border-slate-700 text-xs">
                <span className="text-slate-400 text-[10px] uppercase font-bold">Anchor:</span>
                <span className="font-semibold text-blue-400">
                  {activeConversation.active_activity.activity_code}
                </span>
                <span className="text-slate-300 truncate max-w-[120px]">
                  {activeConversation.active_activity.name}
                </span>
                <span className="px-1.5 py-0.5 rounded bg-blue-900/60 text-blue-300 text-[10px]">
                  {activeConversation.active_activity.percent_complete}%
                </span>
              </div>
            )}

            {/* Quick New Chat Button for Desktop Header */}
            <button
              onClick={handleNewChat}
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 border border-slate-700 transition-colors"
              title="Start a new chat in this schedule"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>New Chat</span>
            </button>
          </div>
        </div>

        {/* Success Notification Banner */}
        {successBanner && (
          <div className="flex items-center justify-between px-5 py-2.5 bg-emerald-950/80 border-b border-emerald-800 text-emerald-300 text-xs animate-in fade-in slide-in-from-top-2 shrink-0">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
              <span>{successBanner}</span>
            </div>
            <button
              onClick={() => setSuccessBanner(null)}
              className="text-emerald-400 hover:text-emerald-200"
            >
              ×
            </button>
          </div>
        )}

        {/* Error Notification Banner */}
        {error && (
          <div className="flex items-center justify-between px-5 py-2.5 bg-rose-950/80 border-b border-rose-800 text-rose-300 text-xs animate-in fade-in slide-in-from-top-2 shrink-0">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-rose-400 hover:text-rose-200"
            >
              ×
            </button>
          </div>
        )}

        {/* Chat Messages Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {loadingMessages ? (
            <div className="flex flex-col items-center justify-center h-full text-center space-y-3">
              <RefreshCw className="h-6 w-6 text-blue-400 animate-spin" />
              <p className="text-xs text-slate-400">Loading conversation history...</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center max-w-md mx-auto space-y-4">
              <div className="h-16 w-16 rounded-2xl bg-blue-900/20 border border-blue-500/20 flex items-center justify-center text-blue-400">
                <Sparkles className="h-8 w-8" />
              </div>
              <div>
                <h3 className="font-semibold text-lg text-white">
                  Report Site Execution Directly
                </h3>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                  Describe physical progress completed today or upload shift reports.
                  Time Agent extracts events, matches schedule activities, and prepares
                  verifiable updates for your review.
                </p>
              </div>

              <div className="w-full pt-2">
                <p className="text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-2 text-left">
                  Try saying
                </p>
                <div className="flex flex-col gap-2">
                  {samplePrompts.map((p, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(p)}
                      className="px-3.5 py-2.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 text-xs text-left border border-slate-700/60 transition-colors flex items-center justify-between group"
                    >
                      <span>"{p}"</span>
                      <ArrowRight className="h-3 w-3 text-slate-500 group-hover:text-blue-400 transition-colors" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 ${
                  msg.sender === "USER" ? "justify-end" : "justify-start"
                }`}
              >
                {msg.sender !== "USER" && (
                  <div className="h-8 w-8 rounded-lg bg-blue-600/30 border border-blue-500/40 flex items-center justify-center text-blue-300 shrink-0 text-xs font-bold">
                    {msg.sender === "SYSTEM" ? "SYS" : <Bot className="h-4 w-4" />}
                  </div>
                )}

                <div className="max-w-[82%] space-y-2">
                  <div
                    className={`p-4 rounded-2xl text-sm leading-relaxed ${
                      msg.sender === "USER"
                        ? "bg-blue-600 text-white rounded-tr-none shadow-md shadow-blue-600/20"
                        : msg.sender === "SYSTEM"
                        ? "bg-slate-800/90 text-slate-300 border border-slate-700 rounded-tl-none font-mono text-xs"
                        : "bg-slate-800/90 text-slate-200 border border-slate-700/80 rounded-tl-none"
                    }`}
                  >
                    {msg.content}
                  </div>

                  {/* Proposal Confirmation Card */}
                  {msg.message_metadata &&
                    msg.message_metadata.type === "PROPOSAL_CONFIRMATION" && (
                      <ProposalCard
                        card={msg.message_metadata}
                        onConfirm={handleConfirmProposal}
                        onReject={handleRejectProposal}
                        actionLoading={actionLoading}
                      />
                    )}

                  {/* Clarification Choice Card */}
                  {msg.message_metadata &&
                    msg.message_metadata.type === "CLARIFICATION_CHOICE" && (
                      <ClarificationCard
                        card={msg.message_metadata}
                        onSelectOption={handleSelectClarificationOption}
                        disabled={sendingMessage}
                      />
                    )}
                </div>
              </div>
            ))
          )}

          {/* Sending / Processing Indicator */}
          {sendingMessage && (
            <div className="flex gap-3 justify-start items-center">
              <div className="h-8 w-8 rounded-lg bg-blue-600/30 border border-blue-500/40 flex items-center justify-center text-blue-300 shrink-0">
                <Bot className="h-4 w-4" />
              </div>
              <div className="px-4 py-3 rounded-2xl bg-slate-800/80 border border-slate-700/60 rounded-tl-none flex items-center gap-2 text-xs text-slate-400">
                <div className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
                <div className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse delay-150" />
                <div className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse delay-300" />
                <span className="ml-1 text-slate-400">Time Agent is evaluating...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Message Composer Footer */}
        <div className="p-4 bg-slate-950/90 border-t border-slate-800 shrink-0">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              className="hidden"
              accept=".pdf,.xlsx,.csv,image/*,audio/*"
            />

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading || sendingMessage}
              className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-colors disabled:opacity-50"
              title="Attach shift report (PDF, Excel, Audio)"
            >
              {uploading ? (
                <RefreshCw className="h-4 w-4 animate-spin text-blue-400" />
              ) : (
                <Paperclip className="h-4 w-4" />
              )}
            </button>

            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Report progress (e.g. 'Poured 35 m3 concrete for F-204 today')..."
              disabled={sendingMessage || loadingMessages}
              className="flex-1 px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700/80 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all disabled:opacity-50"
            />

            <button
              type="submit"
              disabled={!inputText.trim() || sendingMessage || loadingMessages}
              className="p-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/30 transition-all disabled:opacity-40 disabled:hover:bg-blue-600"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>

          <div className="flex items-center justify-between text-[11px] text-slate-500 mt-2 px-1">
            <span>
              Press Enter to send. Proposals require human confirmation before schedule mutation.
            </span>
            <span className="hidden sm:inline text-slate-600">
              5-minute proposal TTL · PostgreSQL audit ledger
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
