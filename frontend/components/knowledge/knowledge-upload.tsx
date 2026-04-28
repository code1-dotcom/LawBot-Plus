"use client";

import { useState, useRef } from "react";
import { Upload, FileJson, AlertCircle, CheckCircle, RefreshCw, Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  uploadKnowledgeFile,
  batchUploadKnowledge,
  getKnowledgeStats,
  reindexKnowledgeBase,
  KnowledgeStats,
  UploadResult,
} from "@/lib/api";

export default function KnowledgeUpload() {
  const [activeTab, setActiveTab] = useState("upload");
  const [file, setFile] = useState<File | null>(null);
  const [jsonInput, setJsonInput] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 加载统计数据
  const loadStats = async () => {
    try {
      const data = await getKnowledgeStats();
      setStats(data);
    } catch (error) {
      console.error("Failed to load stats:", error);
    }
  };

  // 文件上传处理
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (!selectedFile.name.endsWith(".json")) {
        alert("只支持 JSON 格式文件");
        return;
      }
      setFile(selectedFile);
      setResult(null);
    }
  };

  // 文件上传
  const handleFileUpload = async () => {
    if (!file) {
      alert("请选择文件");
      return;
    }

    setUploading(true);
    setResult(null);

    try {
      const res = await uploadKnowledgeFile(file);
      setResult(res);
      await loadStats();
    } catch (error) {
      setResult({
        success: false,
        message: "",
        total_records: 0,
        new_records: 0,
        duplicates: 0,
        merged_records: 0,
        error: error instanceof Error ? error.message : "上传失败",
      });
    } finally {
      setUploading(false);
    }
  };

  // JSON 粘贴上传
  const handleJsonUpload = async () => {
    if (!jsonInput.trim()) {
      alert("请输入 JSON 数据");
      return;
    }

    setUploading(true);
    setResult(null);

    try {
      // 验证 JSON 格式
      const docs = JSON.parse(jsonInput);
      const documents = Array.isArray(docs) ? docs : [docs];

      const res = await batchUploadKnowledge(documents, sourceName || undefined);
      setResult(res);
      setJsonInput("");
      setSourceName("");
      await loadStats();
    } catch (error) {
      setResult({
        success: false,
        message: "",
        total_records: 0,
        new_records: 0,
        duplicates: 0,
        merged_records: 0,
        error: error instanceof Error ? error.message : "JSON 格式错误或上传失败",
      });
    } finally {
      setUploading(false);
    }
  };

  // 重新索引
  const handleReindex = async () => {
    setReindexing(true);
    try {
      await reindexKnowledgeBase();
      alert("重新索引完成");
      await loadStats();
    } catch (error) {
      alert(`重新索引失败: ${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      setReindexing(false);
    }
  };

  // 初始加载
  useState(() => {
    loadStats();
  });

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <div className="flex items-center gap-3 mb-6">
        <Database className="h-8 w-8 text-blue-600" />
        <h1 className="text-2xl font-bold">知识库管理</h1>
      </div>

      {/* 统计卡片 */}
      {stats && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">知识库统计</CardTitle>
            <CardDescription>当前已索引的法律条文数量</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-blue-50 rounded-lg p-4">
                <div className="text-2xl font-bold text-blue-600">{stats.total_documents}</div>
                <div className="text-sm text-gray-600">总文档数</div>
              </div>
              <div className="bg-green-50 rounded-lg p-4">
                <div className="text-2xl font-bold text-green-600">{stats.json_files_count}</div>
                <div className="text-sm text-gray-600">JSON文件</div>
              </div>
              <div className="col-span-2 bg-gray-50 rounded-lg p-4">
                <div className="text-sm text-gray-600 mb-1">最新文件</div>
                <div className="text-sm font-medium truncate">{stats.latest_file || "无"}</div>
              </div>
            </div>
            {Object.keys(stats.source_count).length > 0 && (
              <div className="mt-4">
                <div className="text-sm font-medium text-gray-700 mb-2">来源分布</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(stats.source_count).slice(0, 5).map(([source, count]) => (
                    <span
                      key={source}
                      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800"
                    >
                      {source}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="upload">上传文件</TabsTrigger>
          <TabsTrigger value="json">粘贴JSON</TabsTrigger>
        </TabsList>

        {/* 文件上传 */}
        <TabsContent value="upload">
          <Card>
            <CardHeader>
              <CardTitle>上传知识库文件</CardTitle>
              <CardDescription>
                支持 JSON 格式的法律条文文件，上传后将自动进行去重处理并添加到向量数据库
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept=".json"
                  className="hidden"
                />
                <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                {file ? (
                  <div className="space-y-2">
                    <div className="flex items-center justify-center gap-2 text-green-600">
                      <FileJson className="h-5 w-5" />
                      <span className="font-medium">{file.name}</span>
                    </div>
                    <Button variant="outline" onClick={() => fileInputRef.current?.click()}>
                      重新选择
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <p className="text-gray-600">点击下方按钮选择 JSON 文件</p>
                    <Button onClick={() => fileInputRef.current?.click()}>选择文件</Button>
                  </div>
                )}
              </div>

              {file && (
                <Button
                  onClick={handleFileUpload}
                  disabled={uploading}
                  className="w-full"
                  size="lg"
                >
                  {uploading ? "上传中..." : "上传并添加到知识库"}
                </Button>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* JSON 粘贴 */}
        <TabsContent value="json">
          <Card>
            <CardHeader>
              <CardTitle>粘贴 JSON 数据</CardTitle>
              <CardDescription>
                直接粘贴法律条文 JSON 数据，将自动添加到知识库
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="source">来源名称（可选）</Label>
                <input
                  id="source"
                  type="text"
                  value={sourceName}
                  onChange={(e) => setSourceName(e.target.value)}
                  placeholder="如：劳动合同法、司法解释"
                  className="mt-1 w-full px-3 py-2 border rounded-md"
                />
              </div>
              <div>
                <Label htmlFor="json">JSON 数据</Label>
                <Textarea
                  id="json"
                  value={jsonInput}
                  onChange={(e) => setJsonInput(e.target.value)}
                  placeholder={`[
  {
    "title": "民法典第五百二十条",
    "content": "当事人约定...",
    "article": "第五百二十条",
    "source": "中华人民共和国民法典"
  }
]`}
                  className="font-mono text-sm min-h-[200px] mt-1"
                />
              </div>
              <Button
                onClick={handleJsonUpload}
                disabled={uploading || !jsonInput.trim()}
                className="w-full"
                size="lg"
              >
                {uploading ? "处理中..." : "添加到知识库"}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 结果显示 */}
      {result && (
        <Card className={`mt-6 ${result.success ? "border-green-500" : "border-red-500"}`}>
          <CardContent className="pt-6">
            {result.success ? (
              <div className="flex items-start gap-3">
                <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-medium text-green-600">上传成功</p>
                  <p className="text-sm text-gray-600">{result.message}</p>
                  <div className="flex gap-4 mt-2 text-sm">
                    <span className="text-blue-600">新记录: {result.new_records}</span>
                    <span className="text-orange-600">重复: {result.duplicates}</span>
                    <span className="text-purple-600">合并: {result.merged_records}</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                <div>
                  <p className="font-medium text-red-600">上传失败</p>
                  <p className="text-sm text-gray-600">{result.error}</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* 重新索引按钮 */}
      <div className="mt-6 flex justify-center">
        <Button
          variant="outline"
          onClick={handleReindex}
          disabled={reindexing}
          className="gap-2"
        >
          <RefreshCw className={`h-4 w-4 ${reindexing ? "animate-spin" : ""}`} />
          {reindexing ? "重新索引中..." : "手动重新索引向量数据库"}
        </Button>
      </div>
    </div>
  );
}
