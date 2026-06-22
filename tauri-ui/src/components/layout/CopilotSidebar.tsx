import { useState, useRef, useEffect } from "react";
import { useAppStore, Message } from "../../stores/appStore";
import { Button } from "../ui/Button";
import { Send, Plus, Clock, Wrench } from "lucide-react";

export default function CopilotSidebar() {
  const { copilotMessages, addCopilotMessage, clearCopilotMessages } =
    useAppStore();
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [copilotMessages]);

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      role: "user",
      content: inputValue,
      timestamp: new Date(),
    };
    addCopilotMessage(userMessage);
    setInputValue("");
    setIsTyping(true);

    // Simulate AI response (replace with actual API call)
    setTimeout(() => {
      const assistantMessage: Message = {
        role: "assistant",
        content: `I received your query: "${userMessage.content}". This is a placeholder response. The actual implementation will connect to the RAG pipeline.`,
        timestamp: new Date(),
      };
      addCopilotMessage(assistantMessage);
      setIsTyping(false);
    }, 1000);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <aside className="fixed right-0 top-0 w-sidebar h-screen bg-[var(--copilot-bg)] border-l border-[var(--copilot-border)] flex flex-col z-[9990]">
      {/* Header */}
      <div className="p-4 border-b border-[var(--border)]">
        <h3 className="text-heading-3 text-[var(--text0)]">Copilot Assistant</h3>
        <p className="text-body-small text-[var(--text1)]">
          Ask for content additions, data table creations, or report refinements.
        </p>
      </div>

      {/* Chat Actions Bar */}
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
        <Button variant="icon" size="sm" title="History">
          <Clock className="w-4 h-4" />
        </Button>
        <Button variant="icon" size="sm" title="Tools">
          <Wrench className="w-4 h-4" />
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {copilotMessages.length === 0 && (
          <div className="text-center text-[var(--text2)] mt-20">
            <p>No messages. Ask me to refine, extract tables, or write report sections!</p>
          </div>
        )}

        {copilotMessages.map((msg, idx) => (
          <div
            key={idx}
            className={`chat-message ${msg.role === "user" ? "user" : ""}`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-[var(--text0)] text-sm whitespace-pre-wrap">
                  {msg.content}
                </p>
              </div>
              <button className="msg-copy-btn" title="Copy message">
                📋
              </button>
            </div>
          </div>
        ))}

        {isTyping && (
          <div className="chat-message">
            <p className="text-[var(--text2)] text-sm animate-pulse">
              Copilot is thinking...
            </p>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-[var(--border)]">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Copilot helper..."
            className="flex-1 bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text0)] placeholder:text-[var(--text2)] focus:border-[rgba(0,188,242,0.5)] focus:outline-none"
          />
          <Button
            variant="primary"
            size="sm"
            onClick={handleSendMessage}
            disabled={!inputValue.trim()}
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </aside>
  );
}
