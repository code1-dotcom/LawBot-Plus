"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Send, Loader2, Trash2, Copy, CheckCheck, ArrowDown } from "lucide-react";
import { ChatMessage } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { LegalAnswerCard } from "./legal-answer-card";

interface ChatInterfaceProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onSendMessage: (message: string) => void;
  onDeleteMessage: (messageId: string) => void;
  onClearChat: () => void;
  disabled?: boolean;
}

export function ChatInterface({
  messages,
  isLoading,
  onSendMessage,
  onDeleteMessage,
  onClearChat,
  disabled,
}: ChatInterfaceProps) {
  const [input, setInput] = React.useState("");
  const [copiedId, setCopiedId] = React.useState<string | null>(null);
  const [showScrollBtn, setShowScrollBtn] = React.useState(false);
  const scrollAreaRef = React.useRef<HTMLDivElement>(null);

  // 定位 ScrollArea 内部的可滚动 viewport
  React.useEffect(() => {
    const el = scrollAreaRef.current;
    if (!el) return;
    const viewport = el.querySelector<HTMLElement>("[data-radix-scroll-area-viewport]");
    if (!viewport) return;

    const handleScroll = () => {
      const distFromBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
      console.log("[Scroll] distFromBottom:", distFromBottom, "show:", distFromBottom > 200);
      setShowScrollBtn(distFromBottom > 200);
    };

    viewport.addEventListener("scroll", handleScroll, { passive: true });
    return () => viewport.removeEventListener("scroll", handleScroll);
  }, []);

  // 新消息 / loading 结束 → 滚动到底部并隐藏按钮
  React.useEffect(() => {
    const el = scrollAreaRef.current;
    if (!el) return;
    const viewport = el.querySelector<HTMLElement>("[data-radix-scroll-area-viewport]");
    if (!viewport) return;
    viewport.scrollTop = viewport.scrollHeight;
    setShowScrollBtn(false);
  }, [messages, isLoading]);

  const scrollToBottom = React.useCallback(() => {
    const el = scrollAreaRef.current;
    if (!el) return;
    const viewport = el.querySelector<HTMLElement>("[data-radix-scroll-area-viewport]");
    if (!viewport) return;
    viewport.scrollTo({ top: viewport.scrollHeight, behavior: "smooth" });
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput("");
  };

  const handleCopy = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex flex-col h-full">
      {/* 消息列表 */}
      <div className="relative flex-1 overflow-hidden">
        <ScrollArea className="h-full p-4" ref={scrollAreaRef}>
          <div className="max-w-3xl mx-auto space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-12 text-muted-foreground">
              <div className="text-4xl mb-4">⚖️</div>
              <h3 className="text-lg font-medium mb-2">欢迎使用 LawBot+</h3>
              <p className="text-sm">基于多智能体的法律咨询助手，可以帮您分析法律问题</p>
            </div>
          )}

          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              onCopy={handleCopy}
              onDelete={onDeleteMessage}
              copiedId={copiedId}
            />
          ))}

          {isLoading && (
            <div className="flex gap-3">
              <Avatar className="h-8 w-8">
                <AvatarImage src="/bot-avatar.png" />
                <AvatarFallback className="bg-primary text-primary-foreground text-sm">AI</AvatarFallback>
              </Avatar>
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">分析中...</span>
              </div>
            </div>
          )}
        </div>
        </ScrollArea>

        {/* 滚动到底部按钮 */}
        {showScrollBtn && (
          <button
            type="button"
            onClick={scrollToBottom}
            className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1.5 bg-primary text-primary-foreground text-xs font-medium px-3 py-1.5 rounded-full shadow-md hover:bg-primary/90 transition-colors"
          >
            <ArrowDown className="h-3.5 w-3.5" />
            跳至底部
          </button>
        )}
      </div>

      {/* 输入区域 */}
      <div className="border-t bg-background p-4">
        <div className="max-w-3xl mx-auto">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="请输入您的法律问题..."
              className="min-h-[56px] max-h-[200px] resize-none"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              disabled={disabled || isLoading}
            />
            <div className="flex flex-col gap-2">
              <Button
                type="submit"
                size="icon"
                disabled={!input.trim() || isLoading}
                className="h-[56px] w-[56px]"
              >
                <Send className="h-5 w-5" />
              </Button>
              {messages.length > 0 && (
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={onClearChat}
                  className="h-[40px] w-[56px]"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          </form>
          <p className="text-xs text-muted-foreground mt-2 text-center">
            按 Enter 发送，Shift + Enter 换行
          </p>
        </div>
      </div>
    </div>
  );
}

interface MessageBubbleProps {
  message: ChatMessage;
  onCopy: (text: string, id: string) => void;
  onDelete: (id: string) => void;
  copiedId: string | null;
}

function MessageBubble({ message, onCopy, onDelete, copiedId }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <Avatar className={cn("h-8 w-8 shrink-0", !isUser && "bg-primary")}>
        {isUser ? (
          <AvatarFallback>U</AvatarFallback>
        ) : (
          <AvatarFallback className="bg-primary text-primary-foreground text-sm">AI</AvatarFallback>
        )}
      </Avatar>

      <div className={cn("flex flex-col gap-1 max-w-[85%]", isUser && "items-end")}>
        {/* 用户消息：纯文本气泡 */}
        {isUser ? (
          <div
            className={cn(
              "rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap",
              "bg-primary text-primary-foreground rounded-tr-sm"
            )}
          >
            {message.content}
          </div>
        ) : (
          /* AI 消息：卡片式布局 */
          <div className="w-full">
            <LegalAnswerCard
              content={message.content}
              sources={message.sources}
              confidence={message.confidence}
              rewrittenQuery={message.rewrittenQuery}
              tokenizedQuery={message.tokenizedQuery}
            />

            {/* 元信息栏 */}
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <span className="text-xs text-muted-foreground">
                {new Date(message.timestamp).toLocaleTimeString()}
              </span>

              {message.needsReview && (
                <Badge variant="destructive" className="text-xs">
                  待人工审核
                </Badge>
              )}

              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs gap-1 ml-auto"
                onClick={() => onCopy(message.content, message.id)}
              >
                {copiedId === message.id ? (
                  <>
                    <CheckCheck className="h-3 w-3" />
                    已复制
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" />
                    复制
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
