"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import {
  Plus,
  Trash2,
  Search,
  Settings,
  MessageSquare,
  History,
  Sparkles,
  Wrench,
  FileText,
  Loader2,
  Shield,
  RefreshCw,
  CheckCircle,
  XCircle,
  Eye,
} from "lucide-react";
import { Tool, Skill, ChatSession } from "@/lib/api";
import { HITLTask, getHITLTasks, reviewHITLTask } from "@/lib/api";

interface SidebarProps {
  sessions: ChatSession[];
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  tools: Tool[];
  skills: Skill[];
  onToggleTool: (toolId: number, enabled: boolean) => Promise<void>;
  onToggleSkill: (skillId: number, enabled: boolean) => Promise<void>;
  onCreateTool: (data: Partial<Tool>) => Promise<void>;
  onCreateSkill: (data: Partial<Skill>) => Promise<void>;
  onDeleteTool: (toolId: number) => Promise<void>;
  onDeleteSkill: (skillId: number) => Promise<void>;
}

export function Sidebar({
  sessions,
  currentSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  tools,
  skills,
  onToggleTool,
  onToggleSkill,
  onCreateTool,
  onCreateSkill,
  onDeleteTool,
  onDeleteSkill,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(false);

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="h-full flex flex-col border-r bg-card">
      <Tabs defaultValue="chat" className="flex-1 flex flex-col">
        <TabsList className="w-full grid grid-cols-4 rounded-none border-b bg-muted/50">
          <TabsTrigger value="chat" className="rounded-none data-[state=active]:bg-background">
            <MessageSquare className="h-4 w-4 mr-1" />
            聊天
          </TabsTrigger>
          <TabsTrigger value="tools" className="rounded-none data-[state=active]:bg-background">
            <Wrench className="h-4 w-4 mr-1" />
            工具
          </TabsTrigger>
          <TabsTrigger value="skills" className="rounded-none data-[state=active]:bg-background">
            <Sparkles className="h-4 w-4 mr-1" />
            技能
          </TabsTrigger>
          <TabsTrigger value="hitl" className="rounded-none data-[state=active]:bg-background">
            <Shield className="h-4 w-4 mr-1" />
            审核
          </TabsTrigger>
        </TabsList>

        {/* 聊天会话列表 */}
        <TabsContent value="chat" className="flex-1 flex flex-col m-0">
          <div className="p-3">
            <Button onClick={onNewSession} className="w-full" size="sm">
              <Plus className="h-4 w-4 mr-2" />
              新对话
            </Button>
          </div>
          
          <div className="px-3 pb-2">
            <div className="relative">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="搜索会话..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 h-8 text-sm"
              />
            </div>
          </div>

          <ScrollArea className="flex-1">
            <div className="space-y-1 p-2">
              {filteredSessions.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">
                  暂无会话记录
                </p>
              ) : (
                filteredSessions.map((session) => (
                  <div
                    key={session.id}
                    className={cn(
                      "group flex items-center gap-2 rounded-md px-2 py-2 text-sm cursor-pointer transition-colors",
                      session.id === currentSessionId
                        ? "bg-primary/10 text-primary"
                        : "hover:bg-muted"
                    )}
                    onClick={() => onSelectSession(session.id)}
                  >
                    <History className="h-4 w-4 shrink-0" />
                    <span className="truncate flex-1">{session.title}</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(session.id);
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        {/* 工具管理 */}
        <TabsContent value="tools" className="flex-1 m-0 overflow-auto p-3">
          <ToolsManager
            tools={tools}
            onToggle={onToggleTool}
            onCreate={onCreateTool}
            onDelete={onDeleteTool}
          />
        </TabsContent>

        {/* 技能管理 */}
        <TabsContent value="skills" className="flex-1 m-0 overflow-auto p-3">
          <SkillsManager
            skills={skills}
            onToggle={onToggleSkill}
            onCreate={onCreateSkill}
            onDelete={onDeleteSkill}
          />
        </TabsContent>

        {/* HITL 审核 */}
        <TabsContent value="hitl" className="flex-1 m-0 overflow-auto p-3">
          <HITLManager />
        </TabsContent>
      </Tabs>

      {/* 底部设置 */}
      <div className="p-3 border-t">
        <Button variant="ghost" className="w-full justify-start" size="sm">
          <Settings className="h-4 w-4 mr-2" />
          系统设置
        </Button>
      </div>
    </div>
  );
}

// 工具管理器
function ToolsManager({
  tools,
  onToggle,
  onCreate,
  onDelete,
}: {
  tools: Tool[];
  onToggle: (id: number, enabled: boolean) => Promise<void>;
  onCreate: (data: Partial<Tool>) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
}) {
  const [isCreating, setIsCreating] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(false);
  const [formData, setFormData] = React.useState({
    name: "",
    description: "",
    tool_type: "custom",
  });

  const handleCreate = async () => {
    if (!formData.name) return;
    setIsLoading(true);
    try {
      await onCreate(formData);
      setFormData({ name: "", description: "", tool_type: "custom" });
      setIsCreating(false);
    } finally {
      setIsLoading(false);
    }
  };

  const typeIcons: Record<string, string> = {
    weather: "🌤️",
    search: "🔍",
    calculator: "🧮",
    translator: "🌐",
    custom: "⚙️",
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">已配置的工具</h3>
        <Dialog open={isCreating} onOpenChange={setIsCreating}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm">
              <Plus className="h-3 w-3 mr-1" />
              添加
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>添加工具</DialogTitle>
              <DialogDescription>配置一个新的工具</DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-3">
              <div className="space-y-1.5">
                <Label htmlFor="tool-name">名称</Label>
                <Input
                  id="tool-name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="天气查询"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="tool-desc">描述</Label>
                <Input
                  id="tool-desc"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="查询城市天气信息"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="tool-type">类型</Label>
                <Select
                  value={formData.tool_type}
                  onValueChange={(v) => setFormData({ ...formData, tool_type: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="weather">🌤️ 天气</SelectItem>
                    <SelectItem value="search">🔍 搜索</SelectItem>
                    <SelectItem value="calculator">🧮 计算</SelectItem>
                    <SelectItem value="translator">🌐 翻译</SelectItem>
                    <SelectItem value="custom">⚙️ 自定义</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsCreating(false)}>取消</Button>
              <Button onClick={handleCreate} disabled={isLoading || !formData.name}>
                {isLoading && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
                添加
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="space-y-2">
        {tools.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">暂无工具</p>
        ) : (
          tools.map((tool) => (
            <Card key={tool.id} className={cn(!tool.enabled && "opacity-60")}>
              <CardHeader className="p-3 pb-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span>{typeIcons[tool.tool_type] || "📦"}</span>
                    <CardTitle className="text-sm">{tool.name}</CardTitle>
                  </div>
                  <Switch
                    checked={tool.enabled}
                    onCheckedChange={(checked) => onToggle(tool.id, checked)}
                  />
                </div>
              </CardHeader>
              <CardContent className="p-3 pt-1">
                <CardDescription className="text-xs">
                  {tool.description}
                </CardDescription>
                <div className="flex justify-end mt-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs text-destructive"
                    onClick={() => onDelete(tool.id)}
                  >
                    <Trash2 className="h-3 w-3 mr-1" />
                    删除
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}

// HITL 人工审核管理器
function HITLManager() {
  const [tasks, setTasks] = React.useState<HITLTask[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [selectedTask, setSelectedTask] = React.useState<HITLTask | null>(null);
  const [reviewComments, setReviewComments] = React.useState("");
  const [modifiedAnswer, setModifiedAnswer] = React.useState("");
  const [reviewing, setReviewing] = React.useState(false);
  const [filter, setFilter] = React.useState<"all" | "pending" | "approved" | "rejected" | "modified">("pending");

  const loadTasks = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getHITLTasks(50);
      setTasks(data);
    } catch (error) {
      console.error("Failed to load HITL tasks:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const filteredTasks = React.useMemo(() => {
    if (filter === "all") return tasks;
    return tasks.filter((t) => t.status === filter);
  }, [tasks, filter]);

  const { toast } = useToast();

  const handleApprove = async (task: HITLTask) => {
    setReviewing(true);
    try {
      await reviewHITLTask(task.task_id, "approve", { comments: reviewComments });
      toast({ title: "已通过", description: "审核通过，任务已完成" });
      await loadTasks();
      setSelectedTask(null);
      setReviewComments("");
    } catch (error) {
      console.error("Approve failed:", error);
      toast({ title: "操作失败", variant: "destructive" });
    } finally {
      setReviewing(false);
    }
  };

  const handleReject = async (task: HITLTask) => {
    if (!reviewComments.trim()) {
      alert("拒绝时必须填写理由");
      return;
    }
    setReviewing(true);
    try {
      await reviewHITLTask(task.task_id, "reject", { comments: reviewComments });
      toast({ title: "已拒绝", description: "该任务已标记为拒绝" });
      await loadTasks();
      setSelectedTask(null);
      setReviewComments("");
    } catch (error) {
      console.error("Reject failed:", error);
      toast({ title: "操作失败", variant: "destructive" });
    } finally {
      setReviewing(false);
    }
  };

  const handleModify = async (task: HITLTask) => {
    if (!modifiedAnswer.trim()) {
      alert("修改时必须填写新答案");
      return;
    }
    setReviewing(true);
    try {
      await reviewHITLTask(task.task_id, "modify", {
        comments: reviewComments,
        modified_answer: modifiedAnswer,
      });
      toast({ title: "已修改并通过", description: "任务已更新为新答案" });
      await loadTasks();
      setSelectedTask(null);
      setReviewComments("");
      setModifiedAnswer("");
    } catch (error) {
      console.error("Modify failed:", error);
      toast({ title: "操作失败", variant: "destructive" });
    } finally {
      setReviewing(false);
    }
  };

  const riskBadgeClass = (level: string) => {
    switch (level) {
      case "high": return "bg-red-100 text-red-700";
      case "critical": return "bg-red-200 text-red-800";
      case "medium": return "bg-yellow-100 text-yellow-700";
      case "low": return "bg-green-100 text-green-700";
      default: return "bg-gray-100 text-gray-700";
    }
  };

  const statusBadgeClass = (status: string) => {
    switch (status) {
      case "pending": return "bg-orange-100 text-orange-700";
      case "approved": return "bg-green-100 text-green-700";
      case "rejected": return "bg-red-100 text-red-700";
      case "modified": return "bg-blue-100 text-blue-700";
      default: return "bg-gray-100 text-gray-700";
    }
  };

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">待审核任务</h3>
        <Button variant="outline" size="sm" onClick={loadTasks} disabled={isLoading}>
          <RefreshCw className={cn("h-3 w-3 mr-1", isLoading && "animate-spin")} />
          刷新
        </Button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 flex-wrap">
        {(["pending", "approved", "rejected", "modified", "all"] as const).map((f) => (
          <Button
            key={f}
            variant={filter === f ? "default" : "outline"}
            size="sm"
            className="h-7 text-xs"
            onClick={() => setFilter(f)}
          >
            {f === "all" ? "全部" : f === "pending" ? "待审核" : f === "approved" ? "已通过" : f === "rejected" ? "已拒绝" : "已修改"}
          </Button>
        ))}
      </div>

      {/* Task list */}
      <div className="space-y-2">
        {isLoading && tasks.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : filteredTasks.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">暂无审核任务</p>
        ) : (
          filteredTasks.map((task) => (
            <Card
              key={task.id}
              className={cn(
                "cursor-pointer transition-colors",
                selectedTask?.id === task.id && "ring-2 ring-primary"
              )}
              onClick={() => {
                setSelectedTask(task);
                setReviewComments("");
                setModifiedAnswer("");
              }}
            >
              <CardHeader className="p-3 pb-1">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Badge className={statusBadgeClass(task.status)} variant="outline">
                      {task.status === "pending" ? "待审核" : task.status === "approved" ? "已通过" : task.status === "rejected" ? "已拒绝" : "已修改"}
                    </Badge>
                    <Badge className={riskBadgeClass(task.risk_level)} variant="outline">
                      风险: {task.risk_level}
                    </Badge>
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0">
                    {new Date(task.created_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="p-3 pt-1">
                <p className="text-xs text-muted-foreground truncate">
                  {task.user_question || "无问题内容"}
                </p>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-xs text-muted-foreground">
                    置信度: <span className={task.confidence_score < 0.5 ? "text-red-600 font-medium" : task.confidence_score < 0.75 ? "text-yellow-600 font-medium" : "text-green-600 font-medium"}>{task.confidence_score.toFixed(3)}</span>
                  </span>
                  {task.status === "pending" && (
                    <Eye className="h-3 w-3 text-muted-foreground" />
                  )}
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Review detail panel */}
      <Dialog open={!!selectedTask} onOpenChange={(open) => !open && setSelectedTask(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>审核详情</DialogTitle>
            <DialogDescription>查看 AI 分析结果并执行审核操作</DialogDescription>
          </DialogHeader>
          {selectedTask && (
            <div className="space-y-4 py-3">
              {/* Meta info */}
              <div className="flex gap-2 flex-wrap">
                <Badge className={statusBadgeClass(selectedTask.status)}>
                  {selectedTask.status === "pending" ? "待审核" : selectedTask.status === "approved" ? "已通过" : selectedTask.status === "rejected" ? "已拒绝" : "已修改"}
                </Badge>
                <Badge className={riskBadgeClass(selectedTask.risk_level)}>
                  风险等级: {selectedTask.risk_level}
                </Badge>
                <Badge variant="outline">
                  置信度: {selectedTask.confidence_score.toFixed(3)}
                </Badge>
              </div>

              {/* User question */}
              <div className="space-y-1">
                <Label className="text-sm font-medium">用户问题</Label>
                <div className="p-3 bg-muted rounded-md text-sm">
                  {selectedTask.user_question}
                </div>
              </div>

              {/* AI reasoning */}
              <div className="space-y-1">
                <Label className="text-sm font-medium">AI 推理过程</Label>
                <div className="p-3 bg-muted rounded-md text-sm whitespace-pre-wrap max-h-48 overflow-y-auto">
                  {selectedTask.agent_reasoning || "无推理过程"}
                </div>
              </div>

              {/* Suggested answer */}
              <div className="space-y-1">
                <Label className="text-sm font-medium">AI 建议答案</Label>
                <div className="p-3 bg-blue-50 border border-blue-100 rounded-md text-sm whitespace-pre-wrap max-h-48 overflow-y-auto">
                  {selectedTask.suggested_answer || "无建议答案"}
                </div>
              </div>

              {/* Action area — only for pending tasks */}
              {selectedTask.status === "pending" && (
                <>
                  <div className="space-y-1">
                    <Label htmlFor="review-comments" className="text-sm font-medium">审核意见（拒绝时必填）</Label>
                    <Textarea
                      id="review-comments"
                      value={reviewComments}
                      onChange={(e) => setReviewComments(e.target.value)}
                      placeholder="填写审核意见..."
                      rows={2}
                    />
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="modified-answer" className="text-sm font-medium">修改后的答案（选择"修改"时填写）</Label>
                    <Textarea
                      id="modified-answer"
                      value={modifiedAnswer}
                      onChange={(e) => setModifiedAnswer(e.target.value)}
                      placeholder="填写修改后的答案..."
                      rows={4}
                    />
                  </div>

                  <div className="flex gap-2 justify-end">
                    <Button
                      variant="outline"
                      onClick={() => handleApprove(selectedTask)}
                      disabled={reviewing}
                      className="text-green-600 border-green-200 hover:bg-green-50 hover:text-green-700"
                    >
                      {reviewing ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <CheckCircle className="h-4 w-4 mr-1" />}
                      通过
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => handleModify(selectedTask)}
                      disabled={reviewing}
                      className="text-blue-600 border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                    >
                      {reviewing ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />}
                      修改后通过
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => handleReject(selectedTask)}
                      disabled={reviewing}
                    >
                      {reviewing ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <XCircle className="h-4 w-4 mr-1" />}
                      拒绝
                    </Button>
                  </div>
                </>
              )}

              {selectedTask.status !== "pending" && (
                <div className="text-sm text-muted-foreground text-center py-2">
                  此任务已完成审核（{selectedTask.status === "approved" ? "已通过" : selectedTask.status === "rejected" ? "已拒绝" : "已修改"}）
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

// 技能管理器
function SkillsManager({
  skills,
  onToggle,
  onCreate,
  onDelete,
}: {
  skills: Skill[];
  onToggle: (id: number, enabled: boolean) => Promise<void>;
  onCreate: (data: Partial<Skill>) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
}) {
  const [isCreating, setIsCreating] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(false);
  const [formData, setFormData] = React.useState({
    name: "",
    description: "",
    skill_type: "custom",
    prompt: "",
  });

  const handleCreate = async () => {
    if (!formData.name) return;
    setIsLoading(true);
    try {
      await onCreate(formData);
      setFormData({ name: "", description: "", skill_type: "custom", prompt: "" });
      setIsCreating(false);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">已配置的技能</h3>
        <Dialog open={isCreating} onOpenChange={setIsCreating}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm">
              <Plus className="h-3 w-3 mr-1" />
              添加
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>添加技能</DialogTitle>
              <DialogDescription>配置一个新的AI技能</DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="skill-name">名称</Label>
                  <Input
                    id="skill-name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="法律分析"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="skill-type">类型</Label>
                  <Select
                    value={formData.skill_type}
                    onValueChange={(v) => setFormData({ ...formData, skill_type: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="legal_analysis">⚖️ 法律分析</SelectItem>
                      <SelectItem value="contract_draft">📝 合同起草</SelectItem>
                      <SelectItem value="case_search">🔍 案例检索</SelectItem>
                      <SelectItem value="custom">⚙️ 自定义</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="skill-desc">描述</Label>
                <Input
                  id="skill-desc"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="专业法律问题分析能力"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="skill-prompt">系统提示词</Label>
                <Textarea
                  id="skill-prompt"
                  value={formData.prompt}
                  onChange={(e) => setFormData({ ...formData, prompt: e.target.value })}
                  placeholder="你是一位专业的法律顾问..."
                  rows={4}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsCreating(false)}>取消</Button>
              <Button onClick={handleCreate} disabled={isLoading || !formData.name}>
                {isLoading && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
                添加
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="space-y-2">
        {skills.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">暂无技能</p>
        ) : (
          skills.map((skill) => (
            <Card key={skill.id} className={cn(!skill.enabled && "opacity-60")}>
              <CardHeader className="p-3 pb-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-primary" />
                    <CardTitle className="text-sm">{skill.name}</CardTitle>
                  </div>
                  <Switch
                    checked={skill.enabled}
                    onCheckedChange={(checked) => onToggle(skill.id, checked)}
                  />
                </div>
              </CardHeader>
              <CardContent className="p-3 pt-1">
                <CardDescription className="text-xs">
                  {skill.description}
                </CardDescription>
                <div className="flex justify-end mt-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs text-destructive"
                    onClick={() => onDelete(skill.id)}
                  >
                    <Trash2 className="h-3 w-3 mr-1" />
                    删除
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
