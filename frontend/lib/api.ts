// API 客户端配置
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  sources?: Source[];
  confidence?: number;
  needsReview?: boolean;
  reasoningChain?: unknown[];
  extraData?: Record<string, unknown>;
  rewrittenQuery?: string;
  tokenizedQuery?: string[];
}

export interface Source {
  id?: string;
  content: string;
  title?: string;
  article?: string;
  source?: string;
  relevance_score?: number;
  metadata?: Record<string, unknown>;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

export interface Tool {
  id: number;
  name: string;
  description: string;
  tool_type: string;
  enabled: boolean;
  config?: Record<string, unknown>;
}

export interface Skill {
  id: number;
  name: string;
  description: string;
  skill_type: string;
  enabled: boolean;
  prompt?: string;
}

// Chat API
export async function sendChatMessage(
  message: string,
  sessionId: string
): Promise<{
  answer: string;
  session_id: string;
  sources: Source[];
  rewrittenQuery?: string;
  tokenizedQuery?: string[];
}> {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: message,
      session_id: sessionId,
    }),
  });

  if (!response.ok) {
    throw new Error("Chat request failed");
  }

  // 处理 SSE 流式响应
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  let answer = "";
  let doneData: Record<string, unknown> = {};

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("event:")) {
        const eventType = line.slice(6).trim();
        continue;
      }
      if (line.startsWith("data:")) {
        const dataStr = line.slice(5).trim();
        try {
          const data = JSON.parse(dataStr);
          if (data.content) {
            answer += data.content;
          }
          if (data.session_id) {
            doneData = { ...doneData, ...data };
          }
        } catch {
          // ignore parse errors
        }
      }
    }
  }

  return {
    answer,
    session_id: doneData.session_id as string || sessionId,
    sources: (doneData.sources as Source[]) || [],
    rewrittenQuery: doneData.rewritten_query as string | undefined,
    tokenizedQuery: doneData.tokenized_query as string[] | undefined,
  };
}

// Tools API
export async function getTools(): Promise<Tool[]> {
  const response = await fetch(`${API_BASE_URL}/tools/`);
  if (!response.ok) throw new Error("Failed to fetch tools");
  return response.json();
}

export async function toggleTool(toolId: number, enabled: boolean): Promise<void> {
  await fetch(`${API_BASE_URL}/tools/${toolId}/toggle`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
}

export async function createTool(data: Partial<Tool>): Promise<Tool> {
  const response = await fetch(`${API_BASE_URL}/tools/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to create tool");
  return response.json();
}

export async function deleteTool(toolId: number): Promise<void> {
  await fetch(`${API_BASE_URL}/tools/${toolId}`, {
    method: "DELETE",
  });
}

// Skills API
export async function getSkills(): Promise<Skill[]> {
  const response = await fetch(`${API_BASE_URL}/skills/`);
  if (!response.ok) throw new Error("Failed to fetch skills");
  return response.json();
}

export async function toggleSkill(skillId: number, enabled: boolean): Promise<void> {
  await fetch(`${API_BASE_URL}/skills/${skillId}/toggle`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
}

export async function createSkill(data: Partial<Skill>): Promise<Skill> {
  const response = await fetch(`${API_BASE_URL}/skills/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Failed to create skill");
  return response.json();
}

export async function deleteSkill(skillId: number): Promise<void> {
  await fetch(`${API_BASE_URL}/skills/${skillId}`, {
    method: "DELETE",
  });
}

// Sessions API
export async function getSessions(): Promise<ChatSession[]> {
  const response = await fetch(`${API_BASE_URL}/sessions/`);
  if (!response.ok) throw new Error("Failed to fetch sessions");
  const data = await response.json();
  
    // 转换后端数据格式为前端格式
  return data.map((session: any) => ({
    id: session.session_id,
    title: session.title || "新会话",
    messages: (session.messages || []).map((msg: any, idx: number) => ({
      id: `msg-${idx}`,
      role: msg.role || "user",
      content: msg.content || "",
      timestamp: new Date(session.created_at || Date.now()).getTime() + idx * 1000,
      sources: msg.sources || [],
      confidence: msg.confidence,
      needsReview: msg.needs_review || false,
      reasoningChain: msg.reasoning_chain,
      extraData: msg.extra_data,
      rewrittenQuery: msg.rewritten_query,
      tokenizedQuery: msg.tokenized_query,
    })),
    createdAt: new Date(session.created_at || Date.now()).getTime(),
    updatedAt: new Date(session.updated_at || Date.now()).getTime(),
  }));
}

export async function getSession(sessionId: string): Promise<ChatSession> {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`);
  if (!response.ok) throw new Error("Failed to fetch session");
  const session = await response.json();
  
  // 转换后端数据格式
  return {
    id: session.session_id || sessionId,
    title: session.title || "新会话",
    messages: (session.messages || []).map((msg: any, idx: number) => ({
      id: `msg-${idx}`,
      role: msg.role || "user",
      content: msg.content || "",
      timestamp: new Date(session.created_at || Date.now()).getTime() + idx * 1000,
      sources: msg.sources || [],
      confidence: msg.confidence,
      needsReview: msg.needs_review || false,
      reasoningChain: msg.reasoning_chain,
      extraData: msg.extra_data,
      rewrittenQuery: msg.rewritten_query,
      tokenizedQuery: msg.tokenized_query,
    })),
    createdAt: new Date(session.created_at || Date.now()).getTime(),
    updatedAt: new Date(session.updated_at || Date.now()).getTime(),
  };
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

// ============== 知识库管理 API ==============

export interface KnowledgeStats {
  total_documents: number;
  source_count: Record<string, number>;
  latest_file: string | null;
  json_files_count: number;
}

export interface UploadResult {
  success: boolean;
  message: string;
  total_records: number;
  new_records: number;
  duplicates: number;
  merged_records: number;
  error?: string;
}

export interface KnowledgeDocument {
  title?: string;
  content: string;
  source?: string;
  article?: string;
  domain?: string;
  doc_type?: string;
  keywords?: string[];
}

export async function getKnowledgeStats(): Promise<KnowledgeStats> {
  const response = await fetch(`${API_BASE_URL}/knowledge/stats`);
  if (!response.ok) throw new Error("Failed to fetch knowledge stats");
  return response.json();
}

export async function uploadKnowledgeFile(file: File): Promise<UploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/knowledge/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Upload failed");
  }

  return response.json();
}

export async function batchUploadKnowledge(
  documents: KnowledgeDocument[],
  sourceName?: string
): Promise<UploadResult> {
  const response = await fetch(`${API_BASE_URL}/knowledge/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      documents,
      source_name: sourceName
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Batch upload failed");
  }

  return response.json();
}

export async function reindexKnowledgeBase(): Promise<{ success: boolean; message: string; total_documents: number }> {
  const response = await fetch(`${API_BASE_URL}/knowledge/reindex`, {
    method: "POST",
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Reindex failed");
  }

  return response.json();
}

// ============== HITL 审核 API ==============

export interface HITLTask {
  id: number;
  task_id: string;
  user_question: string;
  agent_reasoning: string;
  suggested_answer: string;
  confidence_score: number;
  risk_level: string;
  status: string;
  created_at: string;
}

export async function getHITLTasks(limit = 20): Promise<HITLTask[]> {
  const response = await fetch(`${API_BASE_URL}/hitl/tasks?limit=${limit}`);
  if (!response.ok) throw new Error("Failed to fetch HITL tasks");
  return response.json();
}

export async function reviewHITLTask(
  taskId: string,
  action: "approve" | "reject" | "modify",
  options?: { comments?: string; modified_answer?: string }
): Promise<{ status: string; task_id: string; new_status: string }> {
  const response = await fetch(`${API_BASE_URL}/hitl/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task_id: taskId,
      action,
      comments: options?.comments,
      modified_answer: options?.modified_answer,
    }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Review failed");
  }
  return response.json();
}
