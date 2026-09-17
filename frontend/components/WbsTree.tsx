"use client";

import React, { useState, useEffect } from "react";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  Layers,
  RefreshCw,
} from "lucide-react";
import { fetchProjectWbsTree } from "@/lib/api";
import { WBSTreeNode } from "@/lib/types";

interface WbsTreeProps {
  projectId: string;
  onSelectWbs?: (wbsId: string) => void;
}

interface TreeNodeItemProps {
  node: WBSTreeNode;
  level?: number;
  onSelectWbs?: (wbsId: string) => void;
}

function TreeNodeItem({ node, level = 0, onSelectWbs }: TreeNodeItemProps) {
  const [isOpen, setIsOpen] = useState(true);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div className="select-none">
      <div
        style={{ paddingLeft: `${level * 24 + 12}px` }}
        className="flex items-center justify-between py-2.5 pr-4 hover:bg-blue-50/50 rounded-lg cursor-pointer transition-colors group"
        onClick={() => {
          if (hasChildren) setIsOpen(!isOpen);
          if (onSelectWbs) onSelectWbs(node.id);
        }}
      >
        <div className="flex items-center gap-2">
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsOpen(!isOpen);
              }}
              className="p-0.5 text-slate-400 hover:text-slate-700"
            >
              {isOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </button>
          ) : (
            <span className="w-5" />
          )}

          {hasChildren ? (
            isOpen ? (
              <FolderOpen className="h-4 w-4 text-blue-600" />
            ) : (
              <Folder className="h-4 w-4 text-blue-500" />
            )
          ) : (
            <Layers className="h-4 w-4 text-slate-400" />
          )}

          <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
            {node.code}
          </span>
          <span className="text-sm font-medium text-slate-800">{node.name}</span>
        </div>

        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600 border border-slate-200">
          {node.activity_count} {node.activity_count === 1 ? "activity" : "activities"}
        </span>
      </div>

      {hasChildren && isOpen && (
        <div className="relative border-l border-slate-200 ml-6 pl-2 space-y-0.5">
          {node.children.map((child) => (
            <TreeNodeItem
              key={child.id}
              node={child}
              level={level + 1}
              onSelectWbs={onSelectWbs}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function WbsTree({ projectId, onSelectWbs }: WbsTreeProps) {
  const [treeData, setTreeData] = useState<WBSTreeNode[]>([]);
  const [loading, setLoading] = useState(true);

  const loadTree = () => {
    setLoading(true);
    fetchProjectWbsTree(projectId)
      .then(setTreeData)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTree();
  }, [projectId]);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 pb-4">
        <div>
          <h3 className="text-base font-bold text-slate-900">Work Breakdown Structure (WBS)</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Hierarchical breakdown of project phases, disciplines, and packages
          </p>
        </div>
        <button
          onClick={loadTree}
          className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-50 transition-colors"
          title="Refresh WBS Tree"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {loading ? (
        <div className="py-12 text-center text-sm text-slate-400">Loading WBS hierarchy...</div>
      ) : treeData.length === 0 ? (
        <div className="py-12 text-center text-sm text-slate-400">
          No WBS hierarchy defined for this project.
        </div>
      ) : (
        <div className="space-y-1">
          {treeData.map((node) => (
            <TreeNodeItem key={node.id} node={node} onSelectWbs={onSelectWbs} />
          ))}
        </div>
      )}
    </div>
  );
}
