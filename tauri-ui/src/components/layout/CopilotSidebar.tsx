import { useState, useRef, useEffect } from "react";
import { useAppStore, Message } from "../../stores/appStore";
import { Button } from "../ui/Button";
import { Send, Plus, Clock, Wrench, Square } from "lucide-react";

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
    setActiveReportContent 
  } = useAppStore();

  const [activeView, setActiveView] = useState<"chat" | "history" | "tools">("chat");
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef(false);

  // Tools management local state
  const [editingToolId, setEditingToolId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editPrompt, setEditPrompt] = useState("");
  const [isAddingTool, setIsAddingTool] = useState(false);
  const [newToolName, setNewToolName] = useState("");
  const [newToolPrompt, setNewToolPrompt] = useState("");

  const activeSession = chatSessions.find((s) => s.id === activeSessionId) || chatSessions[0];
  const copilotMessages = activeSession ? activeSession.messages : [];

  // Auto-resize input area up to 5 lines
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  }, [inputValue]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [copilotMessages]);

  const handleStopGeneration = () => {
    abortRef.current = true;
    setIsTyping(false);
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      role: "user",
      content: inputValue,
      timestamp: new Date(),
    };
    addCopilotMessage(userMessage);
    const queryText = inputValue;
    setInputValue("");
    setIsTyping(true);
    abortRef.current = false;

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const resp: { answer: string; sources: any[] } = await invoke("query_rag", { query: queryText });

      if (abortRef.current) return;

      const assistantMessage: Message = {
        role: "assistant",
        content: resp.answer,
        citations: resp.sources.map((s: any) => ({
          source: s.source,
          score: s.score,
          snippet: s.content,
        })),
        timestamp: new Date(),
      };
      addCopilotMessage(assistantMessage);

      // Auto-apply canvas content to active canvas
      const canvasContent = extractCanvasContent(resp.answer);
      if (canvasContent) {
        setActiveReportContent(canvasContent);
      }
    } catch (err) {
      if (abortRef.current) return;

      const errorMessage: Message = {
        role: "assistant",
        content: `Error: ${err}`,
        timestamp: new Date(),
      };
      addCopilotMessage(errorMessage);
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
    const match = text.match(/```markdown-canvas\n([\s\S]*?)\n```/);
    return match ? match[1] : null;
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

      {/* View Switcher Container */}
      {activeView === "chat" ? (
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
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
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <p className="text-[var(--text0)] text-sm whitespace-pre-wrap">
                    {msg.content}
                  </p>
                  
                  {/* Citations list */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-[rgba(255,255,255,0.06)] space-y-1">
                      <p className="text-[10px] uppercase tracking-wider text-[var(--text2)] font-semibold">Sources:</p>
                      <div className="flex flex-wrap gap-1">
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
                    </div>
                  )}

                  {/* Apply to Canvas Button */}
                  {canvasContent && (
                    <div className="mt-3">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => {
                          useAppStore.getState().setActiveReportContent(canvasContent);
                        }}
                        className="bg-[rgba(0,188,242,0.15)] hover:bg-[rgba(0,188,242,0.25)] text-[var(--accent)] border border-[rgba(0,188,242,0.3)] text-xs py-1 px-2.5 rounded-lg flex items-center gap-1.5"
                      >
                        ✨ Apply to Canvas
                      </Button>
                    </div>
                  )}
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
            <p className="text-[var(--text2)] text-sm animate-pulse">
              Copilot is thinking...
            </p>
          </div>
        )}

        <div ref={messagesEndRef} />
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
        <div className="p-4 border-t border-[var(--border)]">
          <div className="flex gap-2 items-end">
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask Copilot helper..."
              rows={1}
              className="flex-1 bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text0)] placeholder:text-[var(--text2)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none resize-none overflow-y-auto max-h-[120px] min-h-[36px] leading-normal"
            />
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
                disabled={!inputValue.trim()}
                className="flex items-center justify-center shrink-0 rounded-lg"
                style={{ padding: 0, width: "36px", height: "36px" }}
              >
                <Send className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}
