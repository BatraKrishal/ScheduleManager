"use client";

import React from "react";
import {
  Plus,
  Search,
  MessageSquare,
  Clock,
  ChevronRight,
  X,
  Sparkles,
  Bot,
} from "lucide-react";
import { TimeAgentConversationSummary } from "@/lib/types";

interface ConversationSidebarProps {
  conversations: TimeAgentConversationSummary[];
  activeConversationId: string | null;
  onSelectConversation: (conversationId: string) => void;
  onNewChat: () => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  loading: boolean;
  projectName?: string;
  isMobileDrawerOpen: boolean;
  onCloseMobileDrawer: () => void;
}

interface GroupedConversations {
  today: TimeAgentConversationSummary[];
  yesterday: TimeAgentConversationSummary[];
  previous7Days: TimeAgentConversationSummary[];
  older: TimeAgentConversationSummary[];
}

function groupConversations(
  conversations: TimeAgentConversationSummary[]
): GroupedConversations {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart);
  yesterdayStart.setDate(yesterdayStart.getDate() - 1);
  const sevenDaysAgoStart = new Date(todayStart);
  sevenDaysAgoStart.setDate(sevenDaysAgoStart.getDate() - 7);

  const grouped: GroupedConversations = {
    today: [],
    yesterday: [],
    previous7Days: [],
    older: [],
  };

  for (const conv of conversations) {
    const d = new Date(conv.updated_at || conv.created_at);
    if (d >= todayStart) {
      grouped.today.push(conv);
    } else if (d >= yesterdayStart) {
      grouped.yesterday.push(conv);
    } else if (d >= sevenDaysAgoStart) {
      grouped.previous7Days.push(conv);
    } else {
      grouped.older.push(conv);
    }
  }

  return grouped;
}

function formatRelativeTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export default function ConversationSidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  searchQuery,
  onSearchChange,
  loading,
  projectName,
  isMobileDrawerOpen,
  onCloseMobileDrawer,
}: ConversationSidebarProps) {
  const grouped = groupConversations(conversations);

  const renderGroup = (
    title: string,
    items: TimeAgentConversationSummary[]
  ) => {
    if (items.length === 0) return null;

    return (
      <div key={title} className="mb-4">
        <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-500">
          {title}
        </div>
        <div className="space-y-1">
          {items.map((conv) => {
            const isSelected = conv.id === activeConversationId;
            return (
              <button
                key={conv.id}
                onClick={() => {
                  onSelectConversation(conv.id);
                  onCloseMobileDrawer();
                }}
                className={`w-full text-left px-3 py-2.5 rounded-lg text-xs transition-all flex items-center justify-between group ${
                  isSelected
                    ? "bg-blue-600/20 text-blue-200 border border-blue-500/40 font-medium shadow-sm"
                    : "text-slate-300 hover:bg-slate-800/80 hover:text-white border border-transparent"
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0 flex-1 mr-2">
                  <MessageSquare
                    className={`h-3.5 w-3.5 shrink-0 ${
                      isSelected
                        ? "text-blue-400"
                        : "text-slate-500 group-hover:text-slate-300"
                    }`}
                  />
                  <div className="truncate">
                    <span className="truncate block font-medium">
                      {conv.title || "New Chat"}
                    </span>
                    <span className="text-[10px] text-slate-500 block truncate">
                      {formatRelativeTime(conv.updated_at || conv.created_at)}
                      {conv.message_count > 0 && ` · ${conv.message_count} msgs`}
                    </span>
                  </div>
                </div>

                {isSelected ? (
                  <span className="h-1.5 w-1.5 rounded-full bg-blue-400 shrink-0" />
                ) : (
                  <ChevronRight className="h-3 w-3 text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  const content = (
    <div className="flex flex-col h-full bg-slate-950/95 border-r border-slate-800/80 text-slate-100 w-72 shrink-0">
      {/* Sidebar Header */}
      <div className="p-4 border-b border-slate-800/80 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
              <Bot className="h-4 w-4" />
            </div>
            <div>
              <span className="font-semibold text-xs text-white tracking-wide">
                Time Agent
              </span>
              <span className="block text-[10px] text-slate-400 truncate max-w-[150px]">
                {projectName ? `Project: ${projectName}` : "Schedule Scope"}
              </span>
            </div>
          </div>

          <button
            onClick={onCloseMobileDrawer}
            className="md:hidden text-slate-400 hover:text-white p-1 rounded-md"
            aria-label="Close sidebar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* + New Chat Button */}
        <button
          onClick={() => {
            onNewChat();
            onCloseMobileDrawer();
          }}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/30 transition-all border border-blue-500/40 group"
        >
          <Plus className="h-3.5 w-3.5 group-hover:rotate-90 transition-transform duration-200" />
          <span>New Chat</span>
        </button>

        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-8 pr-7 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/60 focus:ring-1 focus:ring-blue-500/30 transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange("")}
              className="absolute right-2 top-2 text-slate-500 hover:text-slate-300"
              aria-label="Clear search"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Grouped History List */}
      <div className="flex-1 overflow-y-auto p-3 scrollbar-thin scrollbar-thumb-slate-800">
        {loading && conversations.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500">
            Loading conversations...
          </div>
        ) : conversations.length === 0 ? (
          <div className="py-8 px-4 text-center space-y-2">
            <Sparkles className="h-5 w-5 text-slate-600 mx-auto" />
            <p className="text-xs text-slate-400 font-medium">
              {searchQuery ? "No matching chats found" : "No chats yet"}
            </p>
            <p className="text-[11px] text-slate-500">
              {searchQuery
                ? "Try a different search term"
                : "Click + New Chat to begin reporting execution progress."}
            </p>
          </div>
        ) : (
          <>
            {renderGroup("Today", grouped.today)}
            {renderGroup("Yesterday", grouped.yesterday)}
            {renderGroup("Previous 7 Days", grouped.previous7Days)}
            {renderGroup("Older", grouped.older)}
          </>
        )}
      </div>

      {/* Sidebar Footer with Hard Isolation Notice */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950/60 text-[10px] text-slate-500 flex items-center justify-between">
        <span className="flex items-center gap-1">
          <Clock className="h-3 w-3 text-slate-400" />
          <span>Schedule-Isolated</span>
        </span>
        <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/50">
          No Global Memory
        </span>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <div className="hidden md:flex h-full shrink-0">{content}</div>

      {/* Mobile Drawer Overlay */}
      {isMobileDrawerOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
            onClick={onCloseMobileDrawer}
          />
          <div className="relative z-10 flex h-full shadow-2xl animate-in slide-in-from-left duration-200">
            {content}
          </div>
        </div>
      )}
    </>
  );
}
