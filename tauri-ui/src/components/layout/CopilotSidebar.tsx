import { useState, useRef, useEffect } from "react";
import { useAppStore, Message } from "../../stores/appStore";
import { Button } from "../ui/Button";
import { Send, Plus, Clock, Wrench, Square, Paperclip, AlertTriangle, FileText, ArrowDown } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function CopilotSidebar({ width = 400 }: { width?: number }) {
  const { 
    chatSessions, 
    activeSessionId, 
    addCopilotMessage, 
    clearCopilotMessages, 
    deleteChatSession, 
    setActiveSessionId,
    promptTools,
    addPromptTool,
    updatePromptTool,
    deletePromptTool,
    activeReportContent,
    setActiveReportContent,
    addDebugLog,
    providers,
    ragConfig
  } = useAppStore();

  const [activeView, setActiveView] = useState<"chat" | "history" | "tools">("chat");
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef(false);

  // Dropdown states for provider overrides
  const [selProvider, setSelProvider] = useState<string>("");
  const [selModel, setSelModel] = useState<string>("");
  const [selThinking, setSelThinking] = useState<"Low" | "Medium" | "High">(ragConfig.default_thinking_intensity || "Medium");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [streamedContent, setStreamedContent] = useState("");
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  const handleSelectAttachments = async () => {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const files = await open({
        multiple: true,
        filters: [{ name: "Documents/Images", extensions: ["pdf", "docx", "xlsx", "txt", "png", "jpg", "jpeg"] }]
      });
      if (files) {
        const fileList = Array.isArray(files) ? files : [files];
        setAttachments(prev => [...prev, ...fileList]);
        addDebugLog(`[ATTACHMENT] Selected files: ${fileList.join(", ")}`);
      }
    } catch (err) {
      console.error("Failed to select attachments:", err);
      addDebugLog(`[ATTACHMENT_ERROR] Failed to select attachments: ${err}`);
    }
  };

  const [openP, setOpenP] = useState(false);
  const [openM, setOpenM] = useState(false);
  const [openT, setOpenT] = useState(false);

  useEffect(() => {
    const activeProvs = providers.filter(p => p.enabled !== false);
    if (activeProvs.length > 0) {
      const curSelectedIsActive = activeProvs.some(p => p.name === selProvider);
      if (!selProvider || !curSelectedIsActive) {
        setSelProvider(activeProvs[0].name);
      }
    } else {
      setSelProvider("");
    }
  }, [providers]);

  useEffect(() => {
    const curProv = providers.find(p => p.name === selProvider);
    if (curProv && curProv.models.length > 0) {
      setSelModel(curProv.models[0]);
    } else {
      setSelModel("");
    }
  }, [selProvider, providers]);

  // Sync default thinking intensity from selected provider
  useEffect(() => {
    const curProv = providers.find(p => p.name === selProvider);
    if (curProv && curProv.thinking_intensity) {
      setSelThinking(curProv.thinking_intensity);
    } else {
      setSelThinking(ragConfig.default_thinking_intensity || "Medium");
    }
  }, [selProvider, providers, ragConfig.default_thinking_intensity]);

  // Tools management local state
  const [editingToolId, setEditingToolId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editPrompt, setEditPrompt] = useState("");
  const [isAddingTool, setIsAddingTool] = useState(false);
  const [newToolName, setNewToolName] = useState("");
  const [newToolPrompt, setNewToolPrompt] = useState("");

  const activeSession = chatSessions.find((s) => s.id === activeSessionId) || chatSessions[0];
  const copilotMessages = activeSession ? activeSession.messages : [];

  // Auto-resize input area up to 7 lines
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  }, [inputValue]);

  // Auto-scroll to bottom only when the user is already at the bottom.
  // This lets the user scroll up to read history without being yanked back down.
  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    const el = scrollContainerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
  };

  useEffect(() => {
    if (isAtBottom) {
      scrollToBottom("smooth");
    }
  }, [copilotMessages, streamedContent]);

  // Track whether the user is near the bottom of the scroll container.
  const handleScroll = () => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const threshold = 80; // px from bottom considered "at bottom"
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
    setIsAtBottom(atBottom);
  };

  const handleStopGeneration = () => {
    abortRef.current = true;
    setIsTyping(false);
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim() && attachments.length === 0) return;

    const userMessage: Message = {
      role: "user",
      content: inputValue || (attachments.length > 0 ? `[Attached ${attachments.length} files]` : ""),
      timestamp: new Date(),
    };
    addCopilotMessage(userMessage);
    const queryText = inputValue;
    const currentAttachments = [...attachments];
    setInputValue("");
    setAttachments([]);
    setIsTyping(true);
    setStreamedContent("");
    abortRef.current = false;

    addDebugLog(`[INVOKE] query_rag starting. query: "${queryText}" (provider: ${selProvider || "default"}, model: ${selModel || "default"}, thinking: ${selThinking}, attachments: ${currentAttachments.length} files)`);
    try {
      const { invoke, Channel } = await import("@tauri-apps/api/core");
      let fullAnswer = "";
      let fullThinking = "";
      let doneReceived = false;

      const channel = new Channel();
      channel.onmessage = (event: any) => {
        if (abortRef.current) return;
        if (event.type === "token") {
          fullAnswer += event.content || "";
          setStreamedContent(fullAnswer);
        } else if (event.type === "done") {
          doneReceived = true;
          fullAnswer = event.answer || fullAnswer;
          fullThinking = event.thinking || "";
          const assistantMessage: Message = {
            role: "assistant",
            content: fullAnswer,
            thinking: fullThinking || undefined,
            citations: (event.sources || []).map((s: any) => ({
              source: s.source,
              score: s.score,
              snippet: s.content,
            })),
            timestamp: new Date(),
          };
          addCopilotMessage(assistantMessage);
          addDebugLog(`[SUCCESS] query_rag finished. answer=${fullAnswer.length} chars`);
          const extractedCanvas = extractCanvasContent(fullAnswer);
          addDebugLog(`[CANVAS_EXTRACT] extracted=${extractedCanvas ? `YES (${extractedCanvas.length} chars)` : 'NO'}`);
          if (extractedCanvas) {
            setActiveReportContent(extractedCanvas);
            addDebugLog(`[UI_SYNC] Applied canvas content (${extractedCanvas.length} chars).`);
          }
          setStreamedContent("");
        } else if (event.type === "error") {
          addDebugLog(`[ERROR] Stream error: ${event.error}`);
          const errorMessage: Message = {
            role: "assistant",
            content: `Error: ${event.error}`,
            timestamp: new Date(),
          };
          addCopilotMessage(errorMessage);
          setStreamedContent("");
        }
      };

      const activeSession = chatSessions.find(s => s.id === activeSessionId);
      const history = activeSession 
        ? activeSession.messages.map(msg => ({ role: msg.role, content: msg.content }))
        : [];

      await invoke("query_rag", {
        query: queryText,
        history,
        provider: selProvider || null,
        model: selModel || null,
        thinkingIntensity: selThinking || null,
        attachments: currentAttachments.length > 0 ? currentAttachments : null,
        canvasContent: (activeReportContent && activeReportContent !== "Start typing or ask Copilot to generate report sections.") ? activeReportContent : null,
        onEvent: channel,
      });

      if (abortRef.current) {
        addDebugLog(`[ABORT] query_rag was canceled by user.`);
        return;
      }

      if (!doneReceived) {
        addDebugLog(`[WARN] query_rag completed but no 'done' event was received.`);
      }
    } catch (err) {
      if (abortRef.current) return;
      addDebugLog(`[ERROR] query_rag command failed: ${err}`);
      const errorMessage: Message = {
        role: "assistant",
        content: `Error: ${err}`,
        timestamp: new Date(),
      };
      addCopilotMessage(errorMessage);
      setStreamedContent("");
    } finally {
      if (!abortRef.current) {
        setIsTyping(false);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isTyping) {
        handleSendMessage();
      }
    }
  };

  const extractCanvasContent = (text: string): string | null => {
    // The model may (incorrectly) emit multiple markdown-canvas blocks, e.g. when a
    // continuation restarts the document. Collect every complete block and prefer the
    // LAST one, since later blocks contain the most complete version of the document.
    const blockRegex = /```markdown-canvas\r?\n([\s\S]*?)\r?\n\s*```/g;
    const blocks: string[] = [];
    let m: RegExpExecArray | null;
    while ((m = blockRegex.exec(text)) !== null) {
      blocks.push(m[1]);
    }
    if (blocks.length > 0) {
      // Return the last complete block.
      return blocks[blocks.length - 1];
    }
    // Greedy fallback: match from opening to the LAST ``` in the string
    let match = text.match(/```markdown-canvas\r?\n([\s\S]*)```/);
    if (match) return match[1].replace(/\r?\n\s*$/, '');
    // Super-greedy fallback for truncated output (missing closing backticks)
    match = text.match(/```markdown-canvas\r?\n([\s\S]*)$/);
    return match ? match[1].replace(/\r?\n\s*$/, '') : null;
  };

  return (
    <aside
      className="fixed right-0 top-0 h-screen bg-[var(--copilot-bg)] flex flex-col z-[9990]"
      style={{ width: `${width}px` }}
    >
      {/* Header with Navigation */}
      <div className="p-4 border-b border-[var(--border)] flex items-center justify-between">
        <div className="min-w-0 pr-2">
          <h3 className="text-heading-3 text-[var(--text0)] truncate">
            {activeView === "chat" && "Copilot Assistant"}
            {activeView === "history" && "Chat Sessions"}
            {activeView === "tools" && "Prompt Tools"}
          </h3>
          <p className="text-[9px] leading-snug text-[var(--text2)] whitespace-normal break-words mt-0.5">
            {activeView === "chat" && "Ask for content additions or data table creations."}
            {activeView === "history" && "Manage and switch between your permanent chats."}
            {activeView === "tools" && "Predefined prompts to generate report sections."}
          </p>
        </div>
        {activeView !== "chat" && (
          <Button variant="ghost" size="sm" onClick={() => setActiveView("chat")} className="shrink-0 text-xs py-1 px-2.5 h-8">
            Back
          </Button>
        )}
      </div>

      {/* Chat Actions Bar (Only visible in chat view) */}
      {activeView === "chat" && (
        <div className="px-4 py-2 border-b border-[var(--border)] flex items-center gap-2">
          <span className="text-xs text-[var(--text2)]">Chat actions</span>
          <Button
            variant="icon"
            size="sm"
            onClick={clearCopilotMessages}
            title="New Chat"
          >
            <Plus className="w-4 h-4" />
          </Button>
          <Button 
            variant="icon" 
            size="sm" 
            title="History"
            onClick={() => setActiveView("history")}
          >
            <Clock className="w-4 h-4" />
          </Button>
          <Button 
            variant="icon" 
            size="sm" 
            title="Tools"
            onClick={() => setActiveView("tools")}
          >
            <Wrench className="w-4 h-4" />
          </Button>
        </div>
      )}

      {/* Canvas status: shows what we are sending to the LLM. */}
      {activeView === "chat" && (() => {
        const sent = activeReportContent && activeReportContent !== "Start typing or ask Copilot to generate report sections.";
        const len = sent ? activeReportContent.length : 0;
        return (
          <div className="px-4 py-1.5 border-b border-[var(--border)] flex items-center gap-2 text-[10px]">
            <FileText className="w-3 h-3 text-[var(--accent)] flex-shrink-0" />
            <span className="text-[var(--text2)]">
              {sent
                ? `Canvas sent to Copilot: ${len.toLocaleString()} chars`
                : "Canvas is empty - Copilot will not see anything to edit"}
            </span>
          </div>
        );
      })()}

      {/* View Switcher Container */}
      {activeView === "chat" ? (
        <div
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto p-4 space-y-3 relative"
        >
        {copilotMessages.length === 0 && (
          <div className="text-center text-[var(--text2)] mt-20">
            <p>No messages. Ask me to refine, extract tables, or write report sections!</p>
          </div>
        )}

        {copilotMessages.map((msg, idx) => {
          const canvasContent = msg.role === "assistant" ? extractCanvasContent(msg.content) : null;
          return (
            <div
              key={idx}
              className={`chat-message ${msg.role === "user" ? "user" : ""}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  {/* Thinking block — collapsed by default */}
                  {msg.thinking && (
                    <details className="mb-2 group">
                      <summary className="cursor-pointer text-[10px] font-mono text-[var(--text2)] hover:text-[var(--accent)] select-none flex items-center gap-1 list-none">
                        <span className="transition-transform group-open:rotate-90 inline-block">▶</span>
                        <span>Thinking process</span>
                      </summary>
                      <pre className="mt-1.5 text-[10px] font-mono leading-relaxed text-[var(--text2)] bg-[rgba(0,0,0,0.2)] border border-[rgba(255,255,255,0.06)] rounded-md p-2.5 whitespace-pre-wrap overflow-x-auto max-h-60 overflow-y-auto">{msg.thinking}</pre>
                    </details>
                  )}
                  <div className="markdown-content text-[var(--text0)] text-sm leading-relaxed">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                  
                  {/* Citations list */}
                  {msg.citations && msg.citations.length > 0 && (
                    <details className="mt-2 pt-2 border-t border-[rgba(255,255,255,0.06)] group">
                      <summary className="cursor-pointer text-[10px] font-mono text-[var(--text2)] hover:text-[var(--accent)] select-none flex items-center gap-1 list-none">
                        <span className="transition-transform group-open:rotate-90 inline-block">▶</span>
                        <span className="uppercase tracking-wider font-semibold">Sources ({msg.citations.length})</span>
                      </summary>
                      <div className="flex flex-wrap gap-1 mt-1.5 animate-fade-in">
                        {msg.citations.map((cit, cIdx) => (
                          <span 
                            key={cIdx} 
                            className="inline-flex items-center text-[10px] bg-[rgba(0,188,242,0.15)] text-[var(--accent)] border border-[rgba(0,188,242,0.25)] rounded px-1.5 py-0.5 cursor-help" 
                            title={`${cit.snippet}\n(Confidence: ${(cit.score * 100).toFixed(1)}%)`}
                          >
                            📄 {cit.source}
                          </span>
                        ))}
                      </div>
                    </details>
                  )}

                  {/* Apply / Force-apply to Canvas button. */}
                  {(canvasContent || msg.role === "assistant") && (() => {
                    const isLast = idx === copilotMessages.length - 1;
                    if (canvasContent) {
                      return (
                        <div className="mt-3 flex items-center gap-2">
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => {
                              useAppStore.getState().setActiveReportContent(canvasContent);
                              addDebugLog(`[UI_SYNC] Manually applied canvas block (${canvasContent.length} chars) to canvas.`);
                            }}
                            className="bg-[rgba(0,188,242,0.15)] hover:bg-[rgba(0,188,242,0.25)] text-[var(--accent)] border border-[rgba(0,188,242,0.3)] text-xs py-1 px-2.5 rounded-lg flex items-center gap-1.5"
                          >
                            Apply to Canvas
                          </Button>
                          <span className="text-[10px] text-[var(--text2)]">
                            {canvasContent.length} chars ready
                          </span>
                        </div>
                      );
                    }
                    if (!isLast) return null;
                    return (
                      <div className="mt-3 p-2 rounded-lg bg-[rgba(255,180,0,0.05)] border border-[rgba(255,180,0,0.2)]">
                        <div className="flex items-start gap-2 mb-2">
                          <AlertTriangle className="w-3.5 h-3.5 text-[rgba(255,180,0,0.9)] flex-shrink-0 mt-0.5" />
                          <p className="text-[10px] text-[var(--text2)] leading-relaxed">
                            Copilot did not return a canvas block, so the canvas was not auto-updated. You can still use this reply as the new canvas content, or append it.
                          </p>
                        </div>
                        <div className="flex gap-1.5">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              const textToUse = msg.content || "";
                              if (!textToUse) {
                                alert("There is no valid content to apply. The model may have only outputted a thinking block.");
                                return;
                              }
                              if (window.confirm("Replace the current canvas with this Copilot reply?")) {
                                setActiveReportContent(textToUse);
                                addDebugLog(`[UI_SYNC] Force-replaced canvas with assistant reply (${textToUse.length} chars).`);
                              }
                            }}
                            className="text-[10px] py-1 px-2 h-7"
                          >
                            Use as new canvas
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              const textToAppend = msg.content || "";
                              if (!textToAppend) {
                                alert("There is no valid content to append. The model may have only outputted a thinking block.");
                                return;
                              }
                              const merged = (activeReportContent || "") + "\n\n" + textToAppend;
                              setActiveReportContent(merged);
                              addDebugLog(`[UI_SYNC] Appended assistant reply (${textToAppend.length} chars) to canvas.`);
                            }}
                            className="text-[10px] py-1 px-2 h-7"
                          >
                            Append to canvas
                          </Button>
                        </div>
                      </div>
                    );
                  })()}
                </div>
                <button 
                  className="msg-copy-btn ml-2 flex-shrink-0" 
                  title="Copy message"
                  onClick={() => navigator.clipboard.writeText(msg.content)}
                >
                  📋
                </button>
              </div>
            </div>
          );
        })}

        {isTyping && (
          <div className="chat-message">
            {streamedContent ? (
              <div className="text-sm text-[var(--text1)] whitespace-pre-wrap">
                {streamedContent}
              </div>
            ) : (
              <p className="text-[var(--text2)] text-sm animate-pulse">
                Copilot is thinking...
              </p>
            )}
          </div>
        )}

        <div ref={messagesEndRef} />

        {!isAtBottom && (
          <button
            onClick={() => {
              setIsAtBottom(true);
              scrollToBottom("smooth");
            }}
            className="sticky bottom-3 left-1/2 -translate-x-1/2 z-50 flex items-center justify-center w-9 h-9 rounded-full bg-[var(--bg1)] border border-[var(--border)] shadow-lg hover:bg-[var(--bg2)] text-[var(--text1)] transition-colors"
            title="Jump to latest"
          >
            <ArrowDown className="w-4 h-4" />
          </button>
        )}
      </div>
      ) : activeView === "history" ? (
        /* History Panel View */
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {chatSessions.length === 0 ? (
            <div className="text-center text-[var(--text2)] mt-20">
              <p>No chat history yet.</p>
            </div>
          ) : (
            chatSessions.map((session) => (
              <div 
                key={session.id}
                className={`p-3 rounded-lg border flex items-center justify-between transition-all cursor-pointer ${
                  session.id === activeSessionId 
                    ? "bg-[rgba(0,188,242,0.08)] border-[var(--accent)]" 
                    : "bg-[var(--bg2)] border-[var(--border)] hover:border-[rgba(0,188,242,0.3)]"
                }`}
                onClick={() => {
                  setActiveSessionId(session.id);
                  setActiveView("chat");
                }}
              >
                <div className="flex-1 min-w-0 pr-2">
                  <h4 className="text-sm font-medium text-[var(--text0)] truncate">{session.title}</h4>
                  <span className="text-[10px] text-[var(--text2)]">
                    {new Date(session.createdAt).toLocaleString()}
                  </span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteChatSession(session.id);
                  }}
                  className="text-[var(--text2)] hover:text-red-500 p-1 rounded transition-colors text-sm"
                  title="Delete Session"
                >
                  🗑️
                </button>
              </div>
            ))
          )}
        </div>
      ) : (
        /* Tools Panel View */
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {/* Add New Tool Dialog Form */}
          {!isAddingTool ? (
            <Button 
              variant="ghost" 
              className="w-full justify-center text-xs py-2 border-dashed border-[var(--border)] hover:border-[var(--accent)] h-9" 
              onClick={() => {
                setIsAddingTool(true);
                setNewToolName("");
                setNewToolPrompt("");
              }}
            >
              + Add Predefined Report Tool
            </Button>
          ) : (
            <div className="p-3 bg-[var(--bg2)] border border-[var(--border)] rounded-lg space-y-2.5">
              <h4 className="text-xs font-semibold text-[var(--text0)]">New Report Tool</h4>
              <input
                type="text"
                value={newToolName}
                onChange={(e) => setNewToolName(e.target.value)}
                placeholder="Tool Name (e.g. 能效报告)"
                className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded px-2.5 py-1.5 text-xs text-[var(--text0)] focus:outline-none focus:border-[rgba(0,188,242,0.5)]"
              />
              <textarea
                value={newToolPrompt}
                onChange={(e) => setNewToolPrompt(e.target.value)}
                placeholder="Prompt template instructions..."
                rows={3}
                className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded px-2.5 py-1.5 text-xs text-[var(--text0)] resize-none focus:outline-none focus:border-[rgba(0,188,242,0.5)]"
              />
              <div className="flex gap-2 justify-end">
                <Button size="sm" variant="ghost" onClick={() => setIsAddingTool(false)} className="h-8 py-1 px-3 text-xs">Cancel</Button>
                <Button 
                  size="sm" 
                  variant="primary" 
                  disabled={!newToolName.trim() || !newToolPrompt.trim()}
                  className="h-8 py-1 px-3 text-xs"
                  onClick={() => {
                    addPromptTool({
                      id: Date.now().toString(),
                      name: newToolName,
                      prompt: newToolPrompt
                    });
                    setIsAddingTool(false);
                  }}
                >
                  Save
                </Button>
              </div>
            </div>
          )}

          {promptTools.map((tool) => {
            const isEditing = editingToolId === tool.id;
            return (
              <div 
                key={tool.id}
                className="p-3 bg-[var(--bg2)] border border-[var(--border)] rounded-lg space-y-2 hover:border-[rgba(0,188,242,0.2)] transition-all"
              >
                {!isEditing ? (
                  <>
                    <div className="flex justify-between items-start">
                      <h4 className="text-sm font-medium text-[var(--text0)]">{tool.name}</h4>
                      <div className="flex gap-1.5">
                        <button
                          onClick={() => {
                            setEditingToolId(tool.id);
                            setEditName(tool.name);
                            setEditPrompt(tool.prompt);
                          }}
                          className="text-xs text-[var(--text2)] hover:text-[var(--accent)] p-0.5"
                          title="Edit"
                        >
                          ✏️
                        </button>
                        <button
                          onClick={() => deletePromptTool(tool.id)}
                          className="text-xs text-[var(--text2)] hover:text-red-500 p-0.5"
                          title="Delete"
                        >
                          🗑️
                        </button>
                      </div>
                    </div>
                    <p className="text-xs text-[var(--text2)] line-clamp-2 leading-relaxed bg-[rgba(255,255,255,0.01)] p-1.5 rounded border border-[rgba(255,255,255,0.02)]">
                      {tool.prompt}
                    </p>
                    <Button
                      variant="ghost"
                      className="w-full text-xs justify-center py-1 bg-[rgba(0,188,242,0.05)] text-[var(--accent)] border border-[rgba(0,188,242,0.15)] hover:bg-[rgba(0,188,242,0.12)] h-8"
                      onClick={() => {
                        setInputValue(tool.prompt);
                        setActiveView("chat");
                        setTimeout(() => {
                          if (textareaRef.current) {
                            textareaRef.current.focus();
                            textareaRef.current.style.height = "auto";
                            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
                          }
                        }, 50);
                      }}
                    >
                      Use Prompt
                    </Button>
                  </>
                ) : (
                  <div className="space-y-2">
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded px-2.5 py-1.5 text-xs text-[var(--text0)] focus:outline-none focus:border-[rgba(0,188,242,0.5)]"
                    />
                    <textarea
                      value={editPrompt}
                      onChange={(e) => setEditPrompt(e.target.value)}
                      rows={3}
                      className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded px-2.5 py-1.5 text-xs text-[var(--text0)] resize-none focus:outline-none focus:border-[rgba(0,188,242,0.5)]"
                    />
                    <div className="flex gap-2 justify-end">
                      <Button size="sm" variant="ghost" onClick={() => setEditingToolId(null)} className="h-8 py-1 px-3 text-xs">Cancel</Button>
                      <Button 
                        size="sm" 
                        variant="primary" 
                        disabled={!editName.trim() || !editPrompt.trim()}
                        className="h-8 py-1 px-3 text-xs"
                        onClick={() => {
                          updatePromptTool(tool.id, {
                            name: editName,
                            prompt: editPrompt
                          });
                          setEditingToolId(null);
                        }}
                      >
                        Save
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Input Area (Only visible in chat view) */}
      {activeView === "chat" && (
        <div className="p-4 border-t border-[var(--border)] bg-[rgba(255,255,255,0.01)]">
          {/* Attachments list preview capsules */}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2.5 max-h-20 overflow-y-auto select-none no-print">
              {attachments.map((path, idx) => (
                <div
                  key={idx}
                  className="inline-flex items-center gap-1.5 text-[10px] bg-[var(--bg2)] hover:bg-[var(--border)] border border-[var(--border)] rounded-md pl-2 pr-1.5 py-1 text-[var(--text0)] transition-all"
                >
                  <span className="truncate max-w-[150px]">📄 {path.split(/[/\\]/).pop()}</span>
                  <button
                    onClick={() => setAttachments(prev => prev.filter((_, i) => i !== idx))}
                    className="w-4 h-4 rounded-full flex items-center justify-center text-gray-400 hover:text-red-400 hover:bg-[rgba(255,255,255,0.05)] text-xs font-bold leading-none"
                    title="Remove attachment"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-2 items-end">
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={attachments.length > 0 ? "Add message about attached files..." : "Ask Copilot helper..."}
              rows={2}
              className="flex-1 bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text0)] placeholder:text-[var(--text2)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none resize-none overflow-y-auto max-h-[158px] min-h-[80px] leading-5 font-sans"
            />
            <div className="flex flex-col gap-2 shrink-0">
              {/* Attach Paperclip button */}
              <Button
                variant="ghost"
                onClick={handleSelectAttachments}
                className="flex items-center justify-center shrink-0 rounded-lg llm-icon-btn"
                style={{ padding: 0, width: "36px", height: "36px" }}
                title="Attach files (PDF, Word, Excel, images, etc.)"
              >
                <Paperclip className="w-4 h-4" />
              </Button>

              {isTyping ? (
                <Button
                  variant="primary"
                  onClick={handleStopGeneration}
                  className="flex items-center justify-center shrink-0 rounded-lg bg-red-600 hover:bg-red-700 border-red-600 hover:border-red-700 text-white"
                  style={{ padding: 0, width: "36px", height: "36px" }}
                  title="Stop generation"
                >
                  <Square className="w-4 h-4 fill-current" />
                </Button>
              ) : (
                <Button
                  variant="primary"
                  onClick={handleSendMessage}
                  disabled={!inputValue.trim() && attachments.length === 0}
                  className="flex items-center justify-center shrink-0 rounded-lg"
                  style={{ padding: 0, width: "36px", height: "36px" }}
                >
                  <Send className="w-4 h-4" />
                </Button>
              )}
            </div>
          </div>

          {/* Flat dropdown buttons for LLM overrides */}
          <div className="flex gap-1.5 mt-2.5 text-xs relative select-none">
            {/* Provider Select */}
            <div className="relative flex-1">
              <button
                onClick={() => { setOpenP(!openP); setOpenM(false); setOpenT(false); }}
                className="w-full flex items-center justify-between border rounded-md px-2.5 py-1.5 transition-colors text-left llm-dropdown-trigger"
              >
                <span className="truncate">{selProvider || "Provider"}</span>
                <span className="text-[10px] text-[var(--text2)]">▾</span>
              </button>
              {openP && (
                <div className="absolute bottom-full left-0 mb-1 w-full bg-[var(--bg1)] border border-[var(--border)] rounded-lg shadow-2xl overflow-hidden z-[9999] py-1 max-h-40 overflow-y-auto">
                  {providers.filter(p => p.enabled !== false).length > 0 ? (
                    providers.filter(p => p.enabled !== false).map(p => (
                      <button
                        key={p.name}
                        onClick={() => { setSelProvider(p.name); setOpenP(false); }}
                        className="w-full text-left px-2.5 py-1.5 text-xs llm-dropdown-option"
                      >
                        {p.name}
                      </button>
                    ))
                  ) : (
                    <div className="px-2.5 py-1.5 text-xs text-[var(--text2)] italic">No providers</div>
                  )}
                </div>
              )}
            </div>

            {/* Model Select */}
            <div className="relative flex-1">
              <button
                onClick={() => { setOpenM(!openM); setOpenP(false); setOpenT(false); }}
                className="w-full flex items-center justify-between border rounded-md px-2.5 py-1.5 transition-colors text-left llm-dropdown-trigger"
              >
                <span className="truncate">{selModel || "Model"}</span>
                <span className="text-[10px] text-[var(--text2)]">▾</span>
              </button>
              {openM && (
                <div className="absolute bottom-full left-0 mb-1 w-full bg-[var(--bg1)] border border-[var(--border)] rounded-lg shadow-2xl overflow-hidden z-[9999] py-1 max-h-40 overflow-y-auto">
                  {selProvider && providers.find(p => p.name === selProvider)?.models.length ? (
                    providers.find(p => p.name === selProvider)?.models.map(m => (
                      <button
                        key={m}
                        onClick={() => { setSelModel(m); setOpenM(false); }}
                        className="w-full text-left px-2.5 py-1.5 text-xs llm-dropdown-option"
                      >
                        {m}
                      </button>
                    ))
                  ) : (
                    <div className="px-2.5 py-1.5 text-xs text-[var(--text2)] italic">No models</div>
                  )}
                </div>
              )}
            </div>

            {/* Thinking Select */}
            <div className="relative flex-1">
              <button
                onClick={() => { setOpenT(!openT); setOpenP(false); setOpenM(false); }}
                className="w-full flex items-center justify-between border rounded-md px-2.5 py-1.5 transition-colors text-left llm-dropdown-trigger"
              >
                <span className="truncate">{selThinking}</span>
                <span className="text-[10px] text-[var(--text2)]">▾</span>
              </button>
              {openT && (
                <div className="absolute bottom-full left-0 mb-1 w-full bg-[var(--bg1)] border border-[var(--border)] rounded-lg shadow-2xl overflow-hidden z-[9999] py-1">
                  {(["Low", "Medium", "High"] as const).map(t => (
                    <button
                      key={t}
                      onClick={() => { setSelThinking(t); setOpenT(false); }}
                      className="w-full text-left px-2.5 py-1.5 text-xs llm-dropdown-option"
                    >
                      {t}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
