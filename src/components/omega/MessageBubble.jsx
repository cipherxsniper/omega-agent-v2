import React, { useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { ChevronDown, ChevronUp, ExternalLink, Brain, Clock, Copy, Check } from "lucide-react";

function CodeBlock({ inline, className, children }) {
  const [copied, setCopied] = useState(false);
  const codeString = String(children).replace(/\n$/, "");

  if (inline) {
    return (
      <code className="bg-white/10 text-teal-300 px-1.5 py-0.5 rounded text-[13px] font-mono">
        {codeString}
      </code>
    );
  }

  const language = (className || "").replace("language-", "");

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(codeString);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (e) {
      // clipboard unavailable — fail silently, button just won't confirm
    }
  };

  return (
    <div className="relative group my-2 rounded-lg overflow-hidden border border-white/10 bg-black/40">
      <div className="flex items-center justify-between px-3 py-1.5 bg-white/[0.04] border-b border-white/10">
        <span className="text-[10px] uppercase tracking-wider text-white/30 font-mono">
          {language || "code"}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[11px] text-white/40 hover:text-teal-400 transition-colors"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3" /> Copied
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" /> Copy
            </>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto px-3 py-2.5 text-[13px] leading-relaxed font-mono text-white/90">
        <code>{codeString}</code>
      </pre>
    </div>
  );
}

function MessageMarkdown({ content }) {
  return (
    <ReactMarkdown
      components={{
        code({ inline, className, children, ...props }) {
          return (
            <CodeBlock inline={inline} className={className} {...props}>
              {children}
            </CodeBlock>
          );
        },
        p({ children }) {
          return <p className="mb-2 last:mb-0">{children}</p>;
        },
        ul({ children }) {
          return <ul className="list-disc pl-5 mb-2 space-y-0.5">{children}</ul>;
        },
        ol({ children }) {
          return <ol className="list-decimal pl-5 mb-2 space-y-0.5">{children}</ol>;
        },
        a({ href, children }) {
          return (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-teal-400 underline underline-offset-2">
              {children}
            </a>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

export default function MessageBubble({ message }) {
  const [showReasoning, setShowReasoning] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [msgCopied, setMsgCopied] = useState(false);

  const handleCopyMessage = async () => {
    try {
      await navigator.clipboard.writeText(message.content || "");
      setMsgCopied(true);
      setTimeout(() => setMsgCopied(false), 1500);
    } catch (e) {
      // clipboard unavailable — button just won't confirm
    }
  };
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  if (isSystem) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}
    >
      <div className={`max-w-[80%] ${isUser ? "order-1" : "order-1"}`}>
        {/* Avatar + Name */}
        <div className={`flex items-center gap-2 mb-1 ${isUser ? "justify-end" : "justify-start"}`}>
          {!isUser && (
            <div className="w-6 h-6 rounded-full bg-teal-500 flex items-center justify-center">
              <span className="text-black text-xs font-black">Ω</span>
            </div>
          )}
          <span className="text-xs text-white/40 font-mono">
            {isUser ? "You" : "Omega"}
          </span>
          {message.metadata?.response_time_ms && (
            <span className="text-xs text-white/20 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {(message.metadata.response_time_ms / 1000).toFixed(1)}s
            </span>
          )}
        </div>

        {/* Message bubble */}
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? "bg-teal-500 text-black rounded-br-sm"
              : "bg-white/5 text-white border border-white/10 rounded-bl-sm"
          }`}
        >
          <div className="text-sm leading-relaxed">
            {isUser ? (
              <div className="whitespace-pre-wrap">{message.content}</div>
            ) : (
              <MessageMarkdown content={message.content} />
            )}
          </div>
        </div>

        {/* Copy message */}
        <button
          onClick={handleCopyMessage}
          className={`mt-1 flex items-center gap-1 text-[11px] text-white/25 hover:text-teal-400 transition-colors ${isUser ? "ml-auto" : ""}`}
        >
          {msgCopied ? (
            <>
              <Check className="w-3 h-3" /> Copied
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" /> Copy
            </>
          )}
        </button>

        {/* Reasoning Chain */}
        {message.reasoning_chain && !isUser && (
          <button
            onClick={() => setShowReasoning(!showReasoning)}
            className="mt-2 flex items-center gap-1 text-xs text-teal-400/60 hover:text-teal-400 transition-colors"
          >
            <Brain className="w-3 h-3" />
            Reasoning Chain
            {showReasoning ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        )}
        {showReasoning && message.reasoning_chain && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            className="mt-1 px-3 py-2 bg-white/[0.02] border border-white/5 rounded-lg text-xs text-white/40 font-mono whitespace-pre-wrap"
          >
            {message.reasoning_chain}
          </motion.div>
        )}

        {/* Sources */}
        {message.sources?.length > 0 && !isUser && (
          <>
            <button
              onClick={() => setShowSources(!showSources)}
              className="mt-2 flex items-center gap-1 text-xs text-teal-400/60 hover:text-teal-400 transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              {message.sources.length} Sources
              {showSources ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            {showSources && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                className="mt-1 space-y-1"
              >
                {message.sources.map((s, i) => (
                  <a
                    key={i}
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block px-3 py-2 bg-white/[0.02] border border-white/5 rounded-lg text-xs hover:border-teal-500/30 transition-colors"
                  >
                    <span className="text-teal-400">{s.title}</span>
                    {s.snippet && <p className="text-white/30 mt-0.5">{s.snippet}</p>}
                  </a>
                ))}
              </motion.div>
            )}
          </>
        )}

        {/* Mode badge */}
        {message.metadata?.mode && message.metadata.mode !== "chat" && !isUser && (
          <div className="mt-2">
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-400 border border-teal-500/20 uppercase tracking-wider font-mono">
              {message.metadata.mode}
            </span>
          </div>
        )}
      </div>
    </motion.div>
  );
}
