import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus,
  MessageSquare,
  Archive,
  Settings,
  GitBranch,
  Cpu,
  ListTodo,
  Brain,
  ChevronLeft,
  ChevronRight,
  Trash2,
  Sparkles,
  Plug,
  Search,
  X,
} from "lucide-react";

export default function Sidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onNavigate,
  collapsed,
  onToggle,
}) {
  const [hoveredId, setHoveredId] = useState(null);
  const [query, setQuery] = useState("");

  const filteredConversations = conversations.filter((conversation) => {
    const haystack = `${conversation.title || ""} ${conversation.id || ""}`.toLowerCase();
    return haystack.includes(query.trim().toLowerCase());
  });

  const navItems = [
    { id: "templates", label: "Agent Templates", icon: Sparkles },
    { id: "jobs", label: "Job Queue", icon: ListTodo },
    { id: "memory", label: "Memory Bank", icon: Brain },
    { id: "github", label: "GitHub Sync", icon: GitBranch },
    { id: "connectors", label: "Connectors", icon: Plug },
    { id: "settings", label: "Settings", icon: Settings },
    { id: "system", label: "System", icon: Cpu },
  ];

  return (
    <motion.div
      animate={{ width: collapsed ? 60 : 280 }}
      transition={{ duration: 0.2 }}
      className="h-full bg-black border-r border-white/5 flex flex-col shrink-0"
    >
      {/* Header */}
      <div className="p-3 flex items-center justify-between border-b border-white/5">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-teal-500 flex items-center justify-center">
              <span className="text-black font-black text-sm">Ω</span>
            </div>
            <div>
              <h1 className="text-white font-bold text-sm tracking-wide">OMEGA</h1>
              <p className="text-teal-400/60 text-[10px] font-mono">Super Agent v1.0</p>
            </div>
          </div>
        )}
        {collapsed && (
          <div className="w-8 h-8 mx-auto rounded-lg bg-teal-500 flex items-center justify-center">
            <span className="text-black font-black text-sm">Ω</span>
          </div>
        )}
        <button
          onClick={onToggle}
          className="text-white/30 hover:text-white/60 transition-colors"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* New Chat */}
      <div className="p-2">
        <button
          onClick={onNewConversation}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 text-white/60 hover:text-white hover:border-teal-500/40 hover:bg-teal-500/5 transition-all text-sm"
        >
          <Plus className="w-4 h-4 shrink-0" />
          {!collapsed && <span>New Chat</span>}
        </button>
      </div>

      {/* Conversations */}
      {!collapsed && (
        <div className="flex-1 min-h-0 overflow-y-auto px-2 space-y-0.5">
          <div className="sticky top-0 z-10 bg-black/95 pt-2 pb-2">
            <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-2 focus-within:border-teal-400/40">
              <Search className="h-3.5 w-3.5 shrink-0 text-white/30" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search conversations"
                aria-label="Search conversations"
                className="min-w-0 flex-1 bg-transparent text-xs text-white outline-none placeholder:text-white/25"
              />
              {query && (
                <button type="button" onClick={() => setQuery("")} aria-label="Clear conversation search" className="text-white/30 hover:text-white">
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
            <p className="text-[10px] text-white/20 uppercase tracking-wider font-mono px-1 pt-2">
              Conversations · {filteredConversations.length}
            </p>
          </div>
          {filteredConversations.map((c) => (
            <div
              key={c.id}
              onMouseEnter={() => setHoveredId(c.id)}
              onMouseLeave={() => setHoveredId(null)}
              onClick={() => onSelectConversation(c.id)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all text-sm group ${
                activeConversationId === c.id
                  ? "bg-white/5 text-white"
                  : "text-white/40 hover:text-white/70 hover:bg-white/[0.02]"
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate flex-1">{c.title}</span>
              {hoveredId === c.id && (
                <button
                  onClick={(e) => { e.stopPropagation(); onDeleteConversation(c.id); }}
                  className="text-white/20 hover:text-red-400 transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
          {filteredConversations.length === 0 && (
            <div className="px-3 py-8 text-center text-xs text-white/25">No matching conversations</div>
          )}
        </div>
      )}

      {/* Nav */}
      <div className="border-t border-white/5 p-2 space-y-0.5">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-white/40 hover:text-white/70 hover:bg-white/[0.02] transition-all text-sm"
            >
              <Icon className="w-4 h-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </button>
          );
        })}
      </div>
    </motion.div>
  );
}