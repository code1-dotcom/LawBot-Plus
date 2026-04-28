"use client";

import * as React from "react";
import { ChatInterface } from "@/components/chat/chat-interface";
import { Sidebar } from "@/components/sidebar/sidebar";
import { useToast } from "@/hooks/use-toast";
import {
  ChatMessage,
  ChatSession,
  Tool,
  Skill,
  getSessions,
  getSession,
  deleteSession as apiDeleteSession,
  getTools,
  toggleTool as apiToggleTool,
  createTool as apiCreateTool,
  deleteTool as apiDeleteTool,
  getSkills,
  toggleSkill as apiToggleSkill,
  createSkill as apiCreateSkill,
  deleteSkill as apiDeleteSkill,
} from "@/lib/api";

export default function HomePage() {
  const { toast } = useToast();
  
  // 状态
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [sessions, setSessions] = React.useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [tools, setTools] = React.useState<Tool[]>([]);
  const [skills, setSkills] = React.useState<Skill[]>([]);

  // 初始化加载
  React.useEffect(() => {
    loadSessions();
    loadTools();
    loadSkills();
  }, []);

  // 加载会话
  const loadSessions = async () => {
    try {
      const data = await getSessions();
      setSessions(data);
    } catch (error) {
      console.error("Failed to load sessions:", error);
    }
  };

  // 加载工具
  const loadTools = async () => {
    try {
      const data = await getTools();
      setTools(data);
    } catch (error) {
      console.error("Failed to load tools:", error);
    }
  };

  // 加载技能
  const loadSkills = async () => {
    try {
      const data = await getSkills();
      setSkills(data);
    } catch (error) {
      console.error("Failed to load skills:", error);
    }
  };

  // 创建新会话
  const handleNewSession = () => {
    setMessages([]);
    setCurrentSessionId(null);
  };

  // 选择会话
  const handleSelectSession = async (sessionId: string) => {
    try {
      const session = await getSession(sessionId);
      setCurrentSessionId(sessionId);
      
      // 转换历史消息（rewrittenQuery/tokenizedQuery 已在 getSession 中映射为 camelCase）
      const historyMessages: ChatMessage[] = session.messages.map((msg, idx) => ({
        id: msg.id || `msg-${idx}`,
        role: msg.role as "user" | "assistant",
        content: msg.content,
        timestamp: session.createdAt + idx * 1000,
        sources: msg.sources || [],
        confidence: msg.confidence,
        needsReview: msg.needsReview || false,
        reasoningChain: msg.reasoningChain,
        extraData: msg.extraData,
        rewrittenQuery: msg.rewrittenQuery,
        tokenizedQuery: msg.tokenizedQuery,
      }));
      
      setMessages(historyMessages);
    } catch (error) {
      console.error("Failed to load session:", error);
      toast({ title: "加载会话失败", variant: "destructive" });
    }
  };

  // 删除会话
  const handleDeleteSession = async (sessionId: string) => {
    try {
      await apiDeleteSession(sessionId);
      setSessions(sessions.filter((s) => s.id !== sessionId));
      if (currentSessionId === sessionId) {
        setMessages([]);
        setCurrentSessionId(null);
      }
      toast({ title: "会话已删除" });
    } catch (error) {
      toast({ title: "删除失败", variant: "destructive" });
    }
  };

  // 发送消息
  const handleSendMessage = async (message: string) => {
    // 并发保护：请求进行中时拒绝新消息
    if (isLoading) return;

    const tempUserId = `user-${Date.now()}`;

    // 使用函数式更新，避免闭包陷阱
    setMessages((prev) => [
      ...prev,
      { id: tempUserId, role: "user", content: message, timestamp: Date.now() } as ChatMessage,
    ]);
    setIsLoading(true);

    try {
      const sessionId = currentSessionId || `session-${Date.now()}`;
      setCurrentSessionId(sessionId);

      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: message,
          session_id: sessionId,
        }),
      });

      if (!response.ok) throw new Error("Chat request failed");

      const data = await response.json();

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.result?.answer || data.answer || "",
        timestamp: Date.now(),
        sources: data.result?.sources || data.sources || [],
        confidence: data.result?.confidence || data.confidence,
        needsReview: data.result?.needs_review || data.needs_review,
        rewrittenQuery: data.rewritten_query,
        tokenizedQuery: data.tokenized_query,
      };

      // 使用函数式更新，保证始终基于最新状态追加
      // ★ 会话保存由后端 POST /chat 统一处理，前端不再单独保存
      setMessages((prev) => [...prev, assistantMessage]);

      // 更新会话列表
      loadSessions();
    } catch (error) {
      console.error("Chat error:", error);
      // 请求失败时移除临时插入的用户消息
      setMessages((prev) => prev.filter((m) => m.id !== tempUserId));
      toast({ title: "发送消息失败，请重试", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  };

  // 删除消息
  const handleDeleteMessage = (messageId: string) => {
    setMessages((prev) => prev.filter((m) => m.id !== messageId));
  };

  // 清空聊天
  const handleClearChat = () => {
    setMessages([]);
    setCurrentSessionId(null);
  };

  // 工具操作
  const handleToggleTool = async (toolId: number, enabled: boolean) => {
    try {
      await apiToggleTool(toolId, enabled);
      setTools((prev) =>
        prev.map((t) => (t.id === toolId ? { ...t, enabled } : t))
      );
      toast({ title: enabled ? "工具已启用" : "工具已禁用" });
    } catch (error) {
      toast({ title: "操作失败", variant: "destructive" });
    }
  };

  const handleCreateTool = async (data: Partial<Tool>) => {
    try {
      const newTool = await apiCreateTool({ ...data, enabled: true });
      setTools((prev) => [...prev, newTool]);
      toast({ title: "工具创建成功" });
    } catch (error) {
      toast({ title: "创建失败", variant: "destructive" });
    }
  };

  const handleDeleteTool = async (toolId: number) => {
    try {
      await apiDeleteTool(toolId);
      setTools((prev) => prev.filter((t) => t.id !== toolId));
      toast({ title: "工具已删除" });
    } catch (error) {
      toast({ title: "删除失败", variant: "destructive" });
    }
  };

  // 技能操作
  const handleToggleSkill = async (skillId: number, enabled: boolean) => {
    try {
      await apiToggleSkill(skillId, enabled);
      setSkills((prev) =>
        prev.map((s) => (s.id === skillId ? { ...s, enabled } : s))
      );
      toast({ title: enabled ? "技能已启用" : "技能已禁用" });
    } catch (error) {
      toast({ title: "操作失败", variant: "destructive" });
    }
  };

  const handleCreateSkill = async (data: Partial<Skill>) => {
    try {
      const newSkill = await apiCreateSkill({ ...data, enabled: true });
      setSkills((prev) => [...prev, newSkill]);
      toast({ title: "技能创建成功" });
    } catch (error) {
      toast({ title: "创建失败", variant: "destructive" });
    }
  };

  const handleDeleteSkill = async (skillId: number) => {
    try {
      await apiDeleteSkill(skillId);
      setSkills((prev) => prev.filter((s) => s.id !== skillId));
      toast({ title: "技能已删除" });
    } catch (error) {
      toast({ title: "删除失败", variant: "destructive" });
    }
  };

  return (
    <div className="h-screen flex">
      {/* 侧边栏 */}
      <div className="w-72 shrink-0">
        <Sidebar
          sessions={sessions}
          currentSessionId={currentSessionId}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
          tools={tools}
          skills={skills}
          onToggleTool={handleToggleTool}
          onToggleSkill={handleToggleSkill}
          onCreateTool={handleCreateTool}
          onCreateSkill={handleCreateSkill}
          onDeleteTool={handleDeleteTool}
          onDeleteSkill={handleDeleteSkill}
        />
      </div>

      {/* 主内容区 */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* 顶部栏 */}
        <header className="h-14 border-b bg-background px-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-xl">⚖️</span>
              <h1 className="font-semibold">LawBot+ 法律咨询</h1>
            </div>
            <a
              href="/knowledge"
              className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
            >
              知识库管理
            </a>
          </div>
          <div className="text-sm text-muted-foreground">
            {messages.length > 0 && `${messages.length} 条消息`}
          </div>
        </header>

        {/* 聊天区域 */}
        <div className="flex-1 overflow-hidden">
          <ChatInterface
            messages={messages}
            isLoading={isLoading}
            onSendMessage={handleSendMessage}
            onDeleteMessage={handleDeleteMessage}
            onClearChat={handleClearChat}
          />
        </div>
      </main>
    </div>
  );
}
