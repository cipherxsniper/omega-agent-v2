import React, { useState, useRef, useEffect } from "react";
import { Send, Globe, Code, Brain, Zap, Plus, Camera, Image as ImageIcon, FileText, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const MODES = [
  { id: "chat", label: "Chat", icon: Zap, color: "text-white" },
  { id: "research", label: "Deep Research", icon: Globe, color: "text-teal-400" },
  { id: "code", label: "Code", icon: Code, color: "text-blue-400" },
  { id: "self_improve", label: "Self-Improve", icon: Brain, color: "text-purple-400" },
];

export default function ChatInput({ onSend, disabled, onOpenWorkspace, workspaceAvailable }) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState("chat");
  const [showModes, setShowModes] = useState(false);
  const [showAttach, setShowAttach] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const textareaRef = useRef(null);
  const galleryInputRef = useRef(null);
  const cameraInputRef = useRef(null);
  const docInputRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + "px";
    }
  }, [text]);

  const handleSend = () => {
    if ((!text.trim() && attachments.length === 0) || disabled) return;
    onSend(text.trim(), mode, attachments);
    setText("");
    setMode("chat");
    attachments.forEach((a) => a.url && URL.revokeObjectURL(a.url));
    setAttachments([]);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFiles = (fileList) => {
    const files = Array.from(fileList || []);
    setAttachments((prev) => [...prev, ...files.map((file) => ({
      id: `${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
      url: file.type.startsWith("image/") ? URL.createObjectURL(file) : null,
      file,
    }))]);
    setShowAttach(false);
  };

  const removeAttachment = (id) => {
    setAttachments((prev) => {
      const found = prev.find((a) => a.id === id);
      if (found?.url) URL.revokeObjectURL(found.url);
      return prev.filter((a) => a.id !== id);
    });
  };

  const currentMode = MODES.find((m) => m.id === mode);
  const ModeIcon = currentMode.icon;

  return (
    <div className="relative">
      <input ref={galleryInputRef} type="file" accept="image/*" multiple className="hidden" onChange={(e) => handleFiles(e.target.files)} />
      <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => handleFiles(e.target.files)} />
      <input ref={docInputRef} type="file" accept=".pdf,.doc,.docx,.txt,.md,.csv,.xlsx,.json" multiple className="hidden" onChange={(e) => handleFiles(e.target.files)} />

      <AnimatePresence>
        {showModes && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} className="absolute bottom-full mb-2 left-12 bg-black border border-white/10 rounded-xl p-1 flex gap-1 z-20">
            {MODES.map((m) => {
              const Icon = m.icon;
              return <button key={m.id} onClick={() => { setMode(m.id); setShowModes(false); }} className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-all ${mode === m.id ? "bg-white/10 text-white" : "text-white/40 hover:text-white hover:bg-white/5"}`}><Icon className="w-3.5 h-3.5" />{m.label}</button>;
            })}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showAttach && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} className="absolute bottom-full mb-2 left-0 bg-black border border-white/10 rounded-xl p-1 flex flex-col gap-0.5 min-w-[180px] z-20">
            <button onClick={() => cameraInputRef.current?.click()} className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm text-white/70 hover:text-white hover:bg-white/5"><Camera className="w-4 h-4" />Take Photo</button>
            <button onClick={() => galleryInputRef.current?.click()} className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm text-white/70 hover:text-white hover:bg-white/5"><ImageIcon className="w-4 h-4" />Upload Photo</button>
            <button onClick={() => docInputRef.current?.click()} className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm text-white/70 hover:text-white hover:bg-white/5"><FileText className="w-4 h-4" />Upload Document</button>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="bg-white/[0.03] border border-white/10 rounded-2xl overflow-hidden focus-within:border-teal-500/40 transition-colors">
        {attachments.length > 0 && <div className="flex gap-2 px-3 pt-3 flex-wrap">{attachments.map((a) => <div key={a.id} className="relative w-14 h-14 rounded-lg overflow-hidden border border-white/10 shrink-0 bg-white/5 flex items-center justify-center">{a.url ? <img src={a.url} alt={a.file.name} className="w-full h-full object-cover" /> : <FileText className="w-5 h-5 text-white/40" />}<button onClick={() => removeAttachment(a.id)} className="absolute top-0.5 right-0.5 w-4 h-4 rounded-full bg-black/70 text-white/80 flex items-center justify-center"><X className="w-2.5 h-2.5" /></button></div>)}</div>}

        <div className="flex items-end gap-1.5 p-3">
          <button onClick={() => { setShowAttach(!showAttach); setShowModes(false); }} className={`p-2 rounded-lg transition-colors shrink-0 ${showAttach || attachments.length > 0 ? "bg-teal-500/10 text-teal-400" : "text-white/40 hover:text-white"}`} title="Attach photo or document" aria-label="Attach photo or document"><Plus className="w-5 h-5" /></button>
          <button onClick={() => { setShowModes(!showModes); setShowAttach(false); }} className={`p-2 rounded-lg transition-colors shrink-0 ${mode !== "chat" ? "bg-teal-500/10 text-teal-400" : "text-white/30 hover:text-white/60"}`} title="Switch mode" aria-label="Switch mode"><ModeIcon className="w-5 h-5" /></button>
          <button onClick={onOpenWorkspace} disabled={!workspaceAvailable} className={`p-2 rounded-lg transition-colors shrink-0 text-lg leading-none font-semibold ${workspaceAvailable ? "text-teal-300 hover:bg-teal-400/10 hover:text-teal-200" : "text-white/15 cursor-not-allowed"}`} title={workspaceAvailable ? "Open Omega workspace" : "Workspace appears when Omega starts working"} aria-label="Open Omega workspace">Ω</button>
          <textarea ref={textareaRef} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={handleKeyDown} placeholder={mode === "research" ? "Ask Omega to research anything..." : mode === "code" ? "Describe what you want Omega to build..." : mode === "self_improve" ? "Ask Omega to analyze and improve itself..." : "Message Omega..."} className="flex-1 bg-transparent text-white text-sm resize-none outline-none placeholder:text-white/20 min-h-[24px] max-h-[160px] py-1" rows={1} disabled={disabled} />
          <button onClick={handleSend} disabled={(!text.trim() && attachments.length === 0) || disabled} className={`p-2 rounded-lg shrink-0 transition-all ${(text.trim() || attachments.length > 0) && !disabled ? "bg-teal-500 text-black hover:bg-teal-400" : "text-white/10"}`} title="Send message" aria-label="Send message"><Send className="w-5 h-5" /></button>
        </div>
        {mode !== "chat" && <div className="px-4 pb-2"><span className={`text-[10px] font-mono tracking-wider uppercase ${currentMode.color}`}>{currentMode.label} Mode Active</span></div>}
      </div>
    </div>
  );
}
