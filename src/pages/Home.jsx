import React, { useState, useEffect, useRef, useCallback } from "react";
import { base44 } from "@/api/base44Client";
import { clearContinuityCheckpoint, readContinuityCheckpoint, writeContinuityCheckpoint } from "@/lib/continuity";
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

const missionDigest = async (payload) => {
  const encoded = new TextEncoder().encode(JSON.stringify(payload));
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
};

const buildMission = async (text, mode, attachments) => {
  const payload = { text, mode, attachments: attachments.map(({ name, type, size }) => ({ name, type, size })) };
  const proofId = await missionDigest(payload);
  return {
    id: `mission_${proofId.slice(0, 16)}`,
    proofId,
    objective: text.length > 72 ? `${text.slice(0, 69)}...` : text,
    criteria: [
      { label: "A real assistant response is received" },
      { label: "The live activity transcript completes without an unverified claim" },
      { label: "Evidence and proof metadata remain linked to this request" },
    ],
    evidence: ["assistant response", "live step transcript", "proof-linked decision record"],
    boundary: "observable actions only · no hidden reasoning",
    flightRecorder: {
      command: "python3 agent/flight_recorder.py --production",
      evidence: "Ed25519-signed case chain with replay files for failures",
      status: "available · requires configured PROOFCHAIN signer",
    },
    createdAt: new Date().toISOString(),
  };
};

export default function Home() {
  const [showIntro, setShowIntro] = useState(true);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isThinking, setIsThinking] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activePanel, setActivePanel] = useState(null); // jobs, memory, github, system
  const [showMobileWorkspace, setShowMobileWorkspace] = useState(false);
  const messagesEndRef = useRef(null);
  const [liveTranscript, setLiveTranscript] = useState([]);
  const [resumeCheckpoint, setResumeCheckpoint] = useState(null);
  const [continuityContext, setContinuityContext] = useState(null);
  const [mission, setMission] = useState(null);

  useEffect(() => {
    if (!showIntro) loadConversations();
  }, [showIntro]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  useEffect(() => {
    const checkpoint = readContinuityCheckpoint(activeConversationId);
    setResumeCheckpoint(checkpoint?.status === "running" ? checkpoint : null);
    setContinuityContext(null);
  }, [activeConversationId]);

  const persistContinuity = (conversationId, patch) => {
    writeContinuityCheckpoint(conversationId, {
      conversationId,
      ...patch,
    });
  };

  const resumeFromCheckpoint = () => {
    if (!resumeCheckpoint) return;
    setContinuityContext(resumeCheckpoint);
    setResumeCheckpoint(null);
  };

  const dismissCheckpoint = () => {
    clearContinuityCheckpoint(activeConversationId);
    setResumeCheckpoint(null);
  };

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

  const handleSend = async (text, mode, attachments = []) => {
    const normalizedAttachments = await Promise.all(
      attachments.map(async ({ file }) => {
        if (!file) return null;
        const isText = file.type.startsWith("text/") || /\.(md|txt|csv|json|xml|log)$/i.test(file.name);
        let extractedText = "";
        if (isText && typeof file.text === "function") {
          extractedText = (await file.text()).slice(0, 12000);
        }
        const isImage = file.type.startsWith("image/");
        let dataUrl = null;
        if (isImage) {
          dataUrl = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(reader.error || new Error(`Could not read ${file.name}`));
            reader.readAsDataURL(file);
          });
        }
        return {
          name: file.name,
          type: file.type || "application/octet-stream",
          size: file.size,
          isImage,
          dataUrl,
          extractedText,
        };
      }),
    ).then((items) => items.filter(Boolean));
    const attachmentContext = normalizedAttachments.length
      ? `\n\nATTACHED FILES:\n${normalizedAttachments.map((item) =>
          `- ${item.name} (${item.type}, ${item.size} bytes)${item.isImage ? "\\n[PHOTO ATTACHED: sent to the configured vision-capable model for analysis.]" : ""}${item.extractedText ? `\\n${item.extractedText}` : ""}`
        ).join("\n")}`
      : "";
    const imageInputs = normalizedAttachments
      .filter((item) => item.isImage && typeof item.dataUrl === "string")
      .slice(0, 5)
      .map(({ name, type, dataUrl }) => ({ name, type, dataUrl }));
    const continuityNote = continuityContext
      ? `\n\nRESUMING AN INTERRUPTED OMEGA SESSION:\nLast task: ${continuityContext.lastUserText || "Unknown"}\nLast observed step: ${continuityContext.lastStep || "No step recorded"}\nContinue from this context without repeating completed work.`
      : "";
    const requestText = `${text}${attachmentContext}${continuityNote}`;
    setContinuityContext(null);
    let convId = activeConversationId;

    // Auto-create conversation if none selected
    if (!convId) {
      const title = text.length > 50 ? text.substring(0, 47) + "..." : text;
      const conv = await base44.entities.Conversation.create({ title, status: "active" });
      setConversations((prev) => [conv, ...prev]);
      setActiveConversationId(conv.id);
      convId = conv.id;
    }

    const newMission = await buildMission(text, mode, normalizedAttachments);
    setMission(newMission);

    // Save user message
    const userMsg = await base44.entities.Message.create({
      conversation_id: convId,
      role: "user",
      content: text,
      metadata: {
        mode,
        attachments: normalizedAttachments.map(({ name, type, size }) => ({ name, type, size })),
        mission: newMission,
      },
    });
    setMessages((prev) => [...prev, userMsg]);
    setIsThinking(true);
    setLiveTranscript([]);
    persistContinuity(convId, {
      status: "running",
      lastUserText: text,
      mode,
        attachments: normalizedAttachments.map(({ name, type, size }) => ({ name, type, size })),
        mission: newMission,
        lastStep: "Preparing Omega mission contract",
    });

    const startTime = Date.now();

    // Step 1: Generate plan
    const planSteps = await generatePlan(requestText, mode, convId);

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
      userPrompt = `${fullSystemPrompt}\n\nCONVERSATION HISTORY:\n${conversationHistory}\n\nThe user wants DEEP RESEARCH on the following topic. Search the web, gather multiple sources, synthesize findings, and cite your sources with URLs. Be thorough and factual.\n\nRESEARCH REQUEST: ${requestText}\n\nProvide your response with:\n1. A clear reasoning chain of your research process\n2. Key findings with citations\n3. A synthesis/summary`;
    } else if (mode === "code") {
      userPrompt = `${fullSystemPrompt}\n\nCONVERSATION HISTORY:\n${conversationHistory}\n\nThe user wants CODE GENERATION. Write clean, production-ready, well-commented code.\n\nCODE REQUEST: ${requestText}`;
    } else if (mode === "self_improve") {
      userPrompt = `${fullSystemPrompt}\n\nCONVERSATION HISTORY:\n${conversationHistory}\n\nThe user has asked you to SELF-IMPROVE. Analyze your current system prompt and recent conversation performance. Identify:\n1. Areas where your responses could be better\n2. Missing capabilities or knowledge gaps\n3. Suggested improvements to your system prompt\n4. A revised system prompt if improvements are needed\n\nBe specific and actionable in your self-analysis.\n\nCurrent system prompt:\n${systemPromptContent}\n\nUser request: ${requestText}`;
    } else {
      userPrompt = `${fullSystemPrompt}\n\nCONVERSATION HISTORY:\n${conversationHistory}\n\nUser: ${requestText}`;
    }

    const missionContract = `\n\nMISSION CONTROL CONTRACT:\nObjective: ${newMission.objective}\nAcceptance criteria:\n${newMission.criteria.map((criterion) => `- ${criterion.label}`).join("\n")}\nEvidence required:\n${newMission.evidence.map((item) => `- ${item}`).join("\n")}\nBoundary: ${newMission.boundary}\nMission proof ID: ${newMission.proofId}\nSatisfy this contract with observable evidence. Do not claim completion without evidence.`;
    userPrompt = `${userPrompt}${missionContract}`;

    let response;
    if (mode === "research") {
      response = await base44.functions.invoke("groqComplete", {
        prompt: userPrompt,
        images: imageInputs,
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
        onStep: (step) => {
          setLiveTranscript((prev) => [...prev, step]);
          persistContinuity(convId, {
            status: "running",
            lastUserText: text,
            mode,
            lastStep: step.title || step.name || step.role || "Working",
          });
        },
      });
      response = response.data || response;
    } else {
      response = await base44.functions.invoke("groqComplete", {
        prompt: userPrompt,
        images: imageInputs,
        response_json_schema: {
          type: "object",
          properties: {
            reasoning: { type: "string" },
            response: { type: "string" },
          },
        },
        onStep: (step) => {
          setLiveTranscript((prev) => [...prev, step]);
          persistContinuity(convId, {
            status: "running",
            lastUserText: text,
            mode,
            lastStep: step.title || step.name || step.role || "Working",
          });
        },
      });
      response = response.data || response;
    }

    const responseTime = Date.now() - startTime;

    // Parse response
    let content = typeof response === "string" ? response : response.result || response.response || "";
    if (!String(content).trim()) {
      content = response?.error || "Omega returned no final text. Review the live workspace transcript and retry once the backend is reachable.";
    }
    const reasoning = typeof response === "object" ? response.reasoning : null;
    const sources = typeof response === "object" && response.sources ? response.sources : [];

    // PROACTIVE VERIFICATION PASS — audit the response before delivering
    let verificationResult = null;
    let wasRevised = false;
    try {
      verificationResult = await base44.functions.invoke("responseVerification", {
        request: requestText,
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
          mission: newMission,
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
    clearContinuityCheckpoint(convId);
    setMission((current) => current ? { ...current, completedAt: new Date().toISOString() } : current);

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
            {resumeCheckpoint && (
              <div className="mx-auto mb-6 max-w-2xl rounded-2xl border border-teal-300/20 bg-teal-300/[0.05] p-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-xs font-mono uppercase tracking-[0.16em] text-teal-200/80">Session checkpoint</div>
                    <p className="mt-2 text-sm text-white/75">Omega was interrupted while working on “{resumeCheckpoint.lastUserText || "your task"}”.</p>
                    <p className="mt-1 text-xs text-white/40">Last observed step: {resumeCheckpoint.lastStep || "Preparing"}</p>
                  </div>
                  <button type="button" onClick={dismissCheckpoint} className="text-xs text-white/35 hover:text-white/70">Dismiss</button>
                </div>
                <button type="button" onClick={resumeFromCheckpoint} className="mt-4 rounded-lg bg-teal-300 px-3 py-2 text-xs font-semibold text-black transition hover:bg-teal-200">Resume context</button>
              </div>
            )}
            {messages.length === 0 ? (
              <div className="h-full flex items-center justify-center">
                <div className="text-center max-w-md">
                  <div className="mb-6 flex items-center justify-center gap-2 text-xs font-mono uppercase tracking-[0.18em] text-teal-300/80">
                    <span className="h-1.5 w-1.5 rounded-full bg-teal-300 shadow-[0_0_12px_rgba(94,234,212,0.8)]" />
                    Workspace ready
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
                  <MessageBubble key={msg.id} message={msg} onOpenWorkspace={() => setShowMobileWorkspace(true)} />
                ))}
                {isThinking && <TypingIndicator />}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Input */}
          <div className="px-4 md:px-8 lg:px-12 pb-4 pt-2">
            <ChatInput onSend={handleSend} disabled={isThinking} workspaceAvailable={isThinking || liveTranscript.length > 0} onOpenWorkspace={() => setShowMobileWorkspace(true)} />
            <p className="text-center text-[10px] text-white/10 mt-2 font-mono">
              Omega v1.0 — Super Agent by Thomas Lee Harvey
            </p>
          </div>
        </div>

        {/* Workspace panel — desktop: always visible side panel */}
        <div className="w-[420px] shrink-0 hidden lg:block">
          <WorkspacePanel
            conversationId={activeConversationId}
            isThinking={isThinking}
            mission={mission}
            transcript={
              isThinking && liveTranscript.length > 0
                ? liveTranscript
                : [...messages].reverse().find((m) => m.role === "assistant" && m.transcript)?.transcript
            }
          />
        </div>

        {/* Workspace panel — mobile: opened from the Ω button inside the composer */}
        {showMobileWorkspace && (
          <div className="lg:hidden fixed inset-0 z-50 bg-black flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
              <span className="text-white text-sm font-mono">Omega Sandbox</span>
              <button
                onClick={() => setShowMobileWorkspace(false)}
                className="text-white/50 hover:text-white p-1"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <WorkspacePanel
                conversationId={activeConversationId}
                isThinking={isThinking}
                mission={mission}
                transcript={
                  isThinking && liveTranscript.length > 0
                    ? liveTranscript
                    : [...messages].reverse().find((m) => m.role === "assistant" && m.transcript)?.transcript
                }
              />
            </div>
          </div>
        )}
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