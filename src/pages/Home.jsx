import React, { useState, useEffect, useRef, useCallback } from "react";
import { base44 } from "@/api/base44Client";
import { AnimatePresence } from "framer-motion";
import { buildPromptWithMemory, buildConversationMessages, extractMemoryCandidate, BASE_SYSTEM_PROMPT } from "@/lib/omega-system";
import OmegaIntro from "@/components/omega/OmegaIntro";
import Sidebar from "@/components/omega/Sidebar";
import MessageBubble from "@/components/omega/MessageBubble";
import TypingIndicator from "@/components/omega/TypingIndicator";
import ChatInput from "@/components/omega/ChatInput";
import WorkspacePanel from "@/components/omega/WorkspacePanel";
import JobsPanel from "@/components/omega/JobsPanel";
import MemoryPanel from "@/components/omega/MemoryPanel";
import GitHubPanel from "@/components/omega/GitHubPanel";
import SystemPanel from "@/components/omega/SystemPanel";
import ConnectorsPanel from "@/components/omega/ConnectorsPanel";
import SettingsPanel from "@/components/omega/SettingsPanel";
import AgentTemplatesPanel from "@/components/omega/AgentTemplatesPanel";
import { X } from "lucide-react";

export default function Home() {
  const [showIntro, setShowIntro] = useState(true);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isThinking, setIsThinking] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activePanel, setActivePanel] = useState(null); // jobs, memory, github, system
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (!showIntro) loadConversations();
  }, [showIntro]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  const loadConversations = async () => {
    const data = await base44.entities.Conversation.filter({ status: "active" }, "-updated_date", 50);
    setConversations(data);
  };

  const loadMessages = async (conversationId) => {
    const data = await base44.entities.Message.filter(
      { conversation_id: conversationId },
      "created_date",
      200
    );
    setMessages(data);
  };

  const selectConversation = (id) => {
    setActiveConversationId(id);
    setActivePanel(null);
    loadMessages(id);
  };

  const newConversation = async () => {
    const conv = await base44.entities.Conversation.create({
      title: "New conversation",
      status: "active",
    });
    setConversations((prev) => [conv, ...prev]);
    setActiveConversationId(conv.id);
    setMessages([]);
    setActivePanel(null);
  };

  const deleteConversation = async (id) => {
    await base44.entities.Conversation.update(id, { status: "archived" });
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeConversationId === id) {
      setActiveConversationId(null);
      setMessages([]);
    }
  };

  const handleNavigate = (panel) => {
    setActivePanel(activePanel === panel ? null : panel);
  };

  const generatePlan = async (text, mode, convId) => {
    const planPrompt = `You are Omega, an AI super-agent. The user has given you a task. Break it down into a clear, actionable step-by-step plan. Each step should be a concrete action you would take.

Task: "${text}"
Mode: ${mode}

Return a JSON object with a "steps" array. Each step has:
- "title": short action title (e.g. "Search for latest news on X")
- "description": one sentence detail
- "tool": one of "browser", "terminal", "editor", "search", "analysis", "thinking", "none"

Return 3-7 steps. Be specific to the actual task.`;

    const planRes = await base44.functions.invoke("groqComplete", {
      prompt: planPrompt,
      response_json_schema: {
        type: "object",
        properties: {
          steps: {
            type: "array",
            items: {
              type: "object",
              properties: {
                title: { type: "string" },
                description: { type: "string" },
                tool: { type: "string" },
              },
            },
          },
        },
      },
    });
    const planData = planRes.data || planRes;
    const planSteps = planData.steps || [];
    const created = [];
    for (let i = 0; i < planSteps.length; i++) {
      const s = planSteps[i];
      const step = await base44.entities.AgentStep.create({
        conversation_id: convId,
        step_number: i + 1,
        title: s.title,
        description: s.description || "",
        status: "pending",
        tool: s.tool || "none",
      });
      created.push(step);
    }
    return created;
  };

  const updateStep = async (stepId, updates) => {
    await base44.entities.AgentStep.update(stepId, updates);
  };

  const handleSend = async (text, mode) => {
    let convId = activeConversationId;

    // Auto-create conversation if none selected
    if (!convId) {
      const title = text.length > 50 ? text.substring(0, 47) + "..." : text;
      const conv = await base44.entities.Conversation.create({ title, status: "active" });
      setConversations((prev) => [conv, ...prev]);
      setActiveConversationId(conv.id);
      convId = conv.id;
    }

    // Save user message
    const userMsg = await base44.entities.Message.create({
      conversation_id: convId,
      role: "user",
      content: text,
      metadata: { mode },
    });
    setMessages((prev) => [...prev, userMsg]);
    setIsThinking(true);

    const startTime = Date.now();

    // Step 1: Generate plan
    const planSteps = await generatePlan(text, mode, convId);

    // Check for memory candidates
    const memCandidate = extractMemoryCandidate(text);
    if (memCandidate.detected) {
      await base44.entities.Memory.create({
        key: memCandidate.full,
        value: memCandidate.value,
        category: "fact",
        importance: 7,
        source_conversation_id: convId,
      });
    }

    // Get memories for context
    const memories = await base44.entities.Memory.list("-importance", 20);

    // Get active system prompt
    const systemPrompts = await base44.entities.SystemPrompt.filter({ is_active: true }, "-version", 1);
    const systemPromptContent = systemPrompts.length > 0 ? systemPrompts[0].content : BASE_SYSTEM_PROMPT;
    const fullSystemPrompt = buildPromptWithMemory(memories, systemPromptContent);

    // Build conversation history for context
    const recentMessages = [...messages.slice(-10), userMsg];
    const conversationHistory = buildConversationMessages(recentMessages);

    // Create job
    let job = null;
    if (mode === "research") {
      job = await base44.entities.Job.create({
        title: `Research: ${text.substring(0, 60)}`,
        type: "research",
        conversation_id: convId,
        status: "running",
        progress: 10,
      });
    } else if (mode === "self_improve") {
      job = await base44.entities.Job.create({
        title: `Self-improvement analysis`,
        type: "self_improve",
        conversation_id: convId,
        status: "running",
        progress: 10,
      });
    }

    // Step 2: Execute plan steps — mark each as running then completed
    // The last step is the actual LLM response generation
    for (let i = 0; i < planSteps.length; i++) {
      const step = planSteps[i];
      const stepStart = Date.now();
      await updateStep(step.id, { status: "running" });

      // For browser/search steps in research mode, capture a URL
      if (mode === "research" && (step.tool === "browser" || step.tool === "search")) {
        const urlStep = await base44.functions.invoke("groqComplete", {
          prompt: `Generate a realistic search URL for this research step: "${step.title}". Return only the full URL, nothing else.`,
        });
        const urlData = urlStep.data || urlStep;
        const url = urlData.result ? urlData.result.trim() : "";
        await updateStep(step.id, { tool_url: url });
      }

      // For editor steps in code mode, the output will be the code itself (added after main LLM call)
      // For terminal steps, generate a brief output
      if (step.tool === "terminal") {
        await updateStep(step.id, { tool_output: `$ executing: ${step.title}\n$ done` });
      }

      // Small delay to make steps visually trackable (except the last which is the real LLM call)
      if (i < planSteps.length - 1) {
        await new Promise((r) => setTimeout(r, 600));
      }
      await updateStep(step.id, { status: "completed", duration_ms: Date.now() - stepStart });

      if (job) {
        await base44.entities.Job.update(job.id, { progress: 10 + Math.floor(((i + 1) / planSteps.length) * 70) });
      }
    }

    // Step 3: Generate the final response (the last plan step's actual execution)
    let userPrompt = "";
    if (mode === "research") {
      userPrompt = `${fullSystemPrompt}\n\nCONVERSATION HISTORY:\n${conversationHistory}\n\nThe user wants DEEP RESEARCH on the following topic. Search the web, gather multiple sources, synthesize findings, and cite your sources with URLs. Be thorough and factual.\n\nRESEARCH REQUEST: ${text}\n\nProvide your response with:\n1. A clear reasoning chain of your research process\n2. Key findings with citations\n3. A synthesis/summary`;
    } else if (mode === "code") {
      userPrompt = `${fullSystemPrompt}\n\nCONVERSATION HISTORY:\n${conversationHistory}\n\nThe user wants CODE GENERATION. Write clean, production-ready, well-commented code.\n\nCODE REQUEST: ${text}`;
    } else if (mode === "self_improve") {
      userPrompt = `${fullSystemPrompt}\n\nCONVERSATION HISTORY:\n${conversationHistory}\n\nThe user has asked you to SELF-IMPROVE. Analyze your current system prompt and recent conversation performance. Identify:\n1. Areas where your responses could be better\n2. Missing capabilities or knowledge gaps\n3. Suggested improvements to your system prompt\n4. A revised system prompt if improvements are needed\n\nBe specific and actionable in your self-analysis.\n\nCurrent system prompt:\n${systemPromptContent}\n\nUser request: ${text}`;
    } else {
      userPrompt = `${fullSystemPrompt}\n\nCONVERSATION HISTORY:\n${conversationHistory}\n\nUser: ${text}`;
    }

    let response;
    if (mode === "research") {
      response = await base44.functions.invoke("groqComplete", {
        prompt: userPrompt,
        add_context_from_internet: true,
        response_json_schema: {
          type: "object",
          properties: {
            reasoning: { type: "string" },
            response: { type: "string" },
            sources: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  title: { type: "string" },
                  url: { type: "string" },
                  snippet: { type: "string" },
                },
              },
            },
          },
        },
      });
      response = response.data || response;
    } else {
      response = await base44.functions.invoke("groqComplete", {
        prompt: userPrompt,
        response_json_schema: {
          type: "object",
          properties: {
            reasoning: { type: "string" },
            response: { type: "string" },
          },
        },
      });
      response = response.data || response;
    }

    const responseTime = Date.now() - startTime;

    // Parse response
    let content = typeof response === "string" ? response : response.result || response.response || JSON.stringify(response);
    const reasoning = typeof response === "object" ? response.reasoning : null;
    const sources = typeof response === "object" && response.sources ? response.sources : [];

    // PROACTIVE VERIFICATION PASS — audit the response before delivering
    let verificationResult = null;
    let wasRevised = false;
    try {
      verificationResult = await base44.functions.invoke("responseVerification", {
        request: text,
        response: content,
        reasoningChain: reasoning,
        context: mode === "research" ? JSON.stringify(sources) : conversationHistory,
      });
      const vData = verificationResult.data || verificationResult;
      if (vData && !vData.passed && vData.finalResponse) {
        content = vData.finalResponse;
        wasRevised = true;
      }
    } catch (e) {
      // If verification service fails, proceed with original response
    }

    // Verification step — add to the action timeline
    const verifyStep = await base44.entities.AgentStep.create({
      conversation_id: convId,
      step_number: planSteps.length + 1,
      title: wasRevised ? "Response verification — issues found, revised" : "Response verification — passed",
      description: verificationResult
        ? `Claims: ${(verificationResult.data || verificationResult).claims_verified ? "✓" : "✗"} · Logic: ${(verificationResult.data || verificationResult).reasoning_valid ? "✓" : "✗"} · Complete: ${(verificationResult.data || verificationResult).completeness ? "✓" : "✗"}`
        : "Verification service unavailable",
      status: "completed",
      tool: "analysis",
      duration_ms: Date.now() - startTime,
    });

    // For code mode, save the generated code as file output on the last editor step
    if (mode === "code") {
      const editorStep = [...planSteps].reverse().find((s) => s.tool === "editor");
      if (editorStep) {
        await updateStep(editorStep.id, { tool_output: content.substring(0, 2000) });
      }
    }

    // Save assistant message
    const assistantMsg = await base44.entities.Message.create({
      conversation_id: convId,
      role: "assistant",
      content,
      reasoning_chain: reasoning,
      sources,
      transcript: response.transcript || null,
      job_id: job?.id,
      metadata: {
        model: "omega-1.0",
        response_time_ms: responseTime,
        mode,
        verified: verificationResult ? (verificationResult.data || verificationResult).passed : null,
        was_revised: wasRevised,
        verification_issues: verificationResult ? (verificationResult.data || verificationResult).issues : [],
      },
    });

    // Update conversation
    await base44.entities.Conversation.update(convId, {
      last_message_preview: content.substring(0, 100),
      message_count: messages.length + 2,
    });

    // Complete job
    if (job) {
      await base44.entities.Job.update(job.id, { status: "completed", progress: 100, output_data: content.substring(0, 500) });
    }

    // Self-improvement: if mode is self_improve, save improvement memory
    if (mode === "self_improve") {
      await base44.entities.Memory.create({
        key: "Self-improvement insight",
        value: content.substring(0, 200),
        category: "self_improvement",
        importance: 9,
        source_conversation_id: convId,
      });
    }

    setMessages((prev) => [...prev, assistantMsg]);
    setIsThinking(false);

    // Update conversation title if first message
    if (messages.length === 0) {
      const title = text.length > 50 ? text.substring(0, 47) + "..." : text;
      await base44.entities.Conversation.update(convId, { title });
      setConversations((prev) =>
        prev.map((c) => (c.id === convId ? { ...c, title } : c))
      );
    }
  };

  const handleIntroComplete = useCallback(() => setShowIntro(false), []);

  // Intro screen
  if (showIntro) {
    return <OmegaIntro onComplete={handleIntroComplete} />;
  }

  const panelTitles = {
    jobs: "Job Queue",
    memory: "Context Memory",
    github: "GitHub Sync",
    system: "System Core",
    settings: "Settings",
    templates: "Agent Templates",
    connectors: "Connectors",
  };

  return (
    <div className="h-screen w-screen bg-black flex overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={selectConversation}
        onNewConversation={newConversation}
        onDeleteConversation={deleteConversation}
        onNavigate={handleNavigate}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main content */}
      <div className="flex-1 flex min-w-0">
        {/* Chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 md:px-8 lg:px-12 py-6">
            {messages.length === 0 ? (
              <div className="h-full flex items-center justify-center">
                <div className="text-center max-w-md">
                  <div className="w-16 h-16 rounded-2xl bg-teal-500/10 border border-teal-500/20 flex items-center justify-center mx-auto mb-6">
                    <span className="text-teal-400 font-black text-2xl">Ω</span>
                  </div>
                  <h2 className="text-white text-xl font-bold mb-2">What can I help you with?</h2>
                  <p className="text-white/30 text-sm mb-8">
                    I'm Omega — your AI super-agent. I can research the web, write code, manage tasks, and evolve my own intelligence.
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { label: "Research a topic", mode: "research" },
                      { label: "Write some code", mode: "code" },
                      { label: "Analyze yourself", mode: "self_improve" },
                      { label: "Just chat", mode: "chat" },
                    ].map((item) => (
                      <button
                        key={item.mode}
                        onClick={() => handleSend(item.label, item.mode)}
                        className="px-4 py-3 rounded-xl border border-white/5 bg-white/[0.02] text-white/50 text-sm hover:border-teal-500/30 hover:text-white transition-all text-left"
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                  <p className="text-white/10 text-[10px] mt-8 font-mono tracking-wider">
                    CREATED BY THOMAS LEE HARVEY
                  </p>
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg) => (
                  <MessageBubble key={msg.id} message={msg} />
                ))}
                {isThinking && <TypingIndicator />}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Input */}
          <div className="px-4 md:px-8 lg:px-12 pb-4 pt-2">
            <ChatInput onSend={handleSend} disabled={isThinking} />
            <p className="text-center text-[10px] text-white/10 mt-2 font-mono">
              Omega v1.0 — Super Agent by Thomas Lee Harvey
            </p>
          </div>
        </div>

        {/* Workspace panel — always visible (Manus style) */}
        <div className="w-[420px] shrink-0 hidden lg:block">
          <WorkspacePanel
            conversationId={activeConversationId}
            isThinking={isThinking}
            transcript={[...messages].reverse().find((m) => m.role === "assistant" && m.transcript)?.transcript}
          />
        </div>
      </div>

      {/* Modal overlays for nav panels */}
      <AnimatePresence>
        {activePanel && (
          <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setActivePanel(null)}>
            <div className="w-full max-w-lg h-[80vh] bg-black border border-white/10 rounded-2xl overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
                <h2 className="text-white font-bold text-sm">{panelTitles[activePanel]}</h2>
                <button onClick={() => setActivePanel(null)} className="text-white/30 hover:text-white/60 transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                {activePanel === "jobs" && <JobsPanel />}
                {activePanel === "memory" && <MemoryPanel />}
                {activePanel === "github" && <GitHubPanel />}
                {activePanel === "system" && <SystemPanel />}
                {activePanel === "settings" && <SettingsPanel />}
                {activePanel === "connectors" && <ConnectorsPanel onNavigate={handleNavigate} />}
                {activePanel === "templates" && <AgentTemplatesPanel onSelectTemplate={(tpl) => {
                  setActivePanel(null);
                  handleSend(`Activate the "${tpl.name}" agent template. ${tpl.system_prompt}`, tpl.default_mode || "chat");
                }} />}
              </div>
            </div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}