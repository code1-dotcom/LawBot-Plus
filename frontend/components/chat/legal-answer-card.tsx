"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Source } from "@/lib/api";
import { ChevronDown } from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Types                                                               */
/* ------------------------------------------------------------------ */

export interface ParsedAnswer {
  conclusion: string;
  keyPoints: Array<{ title: string; body: string }>;
  legalArticles: Array<{ title: string; content: string }>;
  rawSources: Source[];
}

/* ------------------------------------------------------------------ */
/*  Markdown 解析器                                                      */
/* ------------------------------------------------------------------ */

export function parseMarkdownToAnswer(
  markdown: string,
  sources: Source[]
): ParsedAnswer {
  const lines = markdown.split("\n");
  let currentSection = "";
  let currentBlock: string[] = [];
  const conclusionBlocks: string[] = [];
  const keyPointsBlocks: string[] = [];
  const legalArticleBlocks: string[] = [];
  const sourceBlocks: string[] = [];

  const flush = () => {
    const block = currentBlock.join("\n").trim();
    if (!block) return;
    switch (currentSection) {
      case "conclusion":
        conclusionBlocks.push(block);
        break;
      case "keypoint":
        keyPointsBlocks.push(block);
        break;
      case "legal":
        legalArticleBlocks.push(block);
        break;
      case "source":
        sourceBlocks.push(block);
        break;
    }
    currentBlock = [];
  };

  for (const line of lines) {
    const h2 = line.match(/^##\s+(.+)/);
    const h3 = line.match(/^###\s+(.+)/);

    if (h2 || h3) {
      flush();
      const title = (h2 || h3)?.[1] ?? "";

      if (/结[论论]|总结|一句话/i.test(title)) {
        currentSection = "conclusion";
      } else if (/要点|建议|核心/i.test(title)) {
        currentSection = "keypoint";
      } else if (/法条|法律依据|法津/i.test(title)) {
        currentSection = "legal";
      } else if (/来源|参考/i.test(title)) {
        currentSection = "source";
      } else {
        currentSection = "";
      }
    } else {
      if (line.trim()) {
        currentBlock.push(line);
      } else if (currentBlock.length > 0) {
        currentBlock.push(line);
      }
    }
  }
  flush();

  const keyPoints: ParsedAnswer["keyPoints"] = keyPointsBlocks.flatMap((block) => {
    return block.split(/\n(?=\d+\.)/).map((p) => {
      p = p.trim();
      const boldMatch = p.match(/^(\d+\.)\s*\*\*(.+?)\*\*(.*)/s);
      if (boldMatch) {
        return {
          title: `${boldMatch[1]} ${boldMatch[2]}`,
          body: boldMatch[3].trim().replace(/\*\*/g, ""),
        };
      }
      const numMatch = p.match(/^(\d+\.)\s*(.*)/s);
      if (numMatch) {
        return { title: numMatch[1], body: numMatch[2].trim().replace(/\*\*/g, "") };
      }
      return { title: "", body: p };
    }).filter((p) => p.body);
  });

  const legalArticles: ParsedAnswer["legalArticles"] = legalArticleBlocks
    .join("\n\n")
    .split(/\n\n+/)
    .map((block) => {
      block = block.trim();
      if (!block) return null;
      const lines = block.split("\n");
      return {
        title: lines[0].replace(/^[-*]\s*/, "").trim(),
        content: lines.slice(1).join("\n").trim() || lines[0],
      };
    })
    .filter((a): a is { title: string; content: string } => a !== null);

  let conclusion = conclusionBlocks.join("\n").trim();
  if (!conclusion && lines.length > 0) {
    const firstPara = lines
      .filter((l) => !l.startsWith("#") && l.trim())
      .join("\n")
      .trim();
    conclusion = firstPara;
  }

  return {
    conclusion,
    keyPoints,
    legalArticles,
    rawSources: sources,
  };
}

/* ------------------------------------------------------------------ */
/*  法条折叠卡片 (白底，独立于气泡)                                       */
/* ------------------------------------------------------------------ */

function LegalArticleItem({
  title,
  content,
}: {
  title: string;
  content: string;
}) {
  const [open, setOpen] = React.useState(false);

  return (
    <div className="border rounded-md bg-white overflow-hidden transition-all duration-200">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left hover:bg-slate-50 transition-colors"
      >
        <span className="text-sm font-medium text-slate-700 flex-1 min-w-0">
          {title}
        </span>
        <ChevronDown
          className={cn(
            "w-4 h-4 shrink-0 text-slate-400 transition-transform duration-200",
            open && "rotate-180"
          )}
        />
      </button>
      <div
        className={cn(
          "overflow-hidden transition-all duration-200 ease-in-out",
          open ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
        )}
      >
        <p className="px-3 pb-3 pt-0 text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">
          {content}
        </p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  主组件：统一气泡 + 底部法条卡片                                       */
/* ------------------------------------------------------------------ */

interface LegalAnswerCardProps {
  content: string;
  sources?: Source[];
  confidence?: number;
  rewrittenQuery?: string;
  tokenizedQuery?: string[];
}

export function LegalAnswerCard({
  content,
  sources = [],
  confidence,
  rewrittenQuery,
  tokenizedQuery,
}: LegalAnswerCardProps) {
  const parsed = React.useMemo(
    () => parseMarkdownToAnswer(content, sources),
    [content, sources]
  );

  const finalArticles = React.useMemo(() => {
    if (sources.length > 0) {
      return sources.map((s) => ({
        title: s.title || s.article || "法律条文",
        content: s.content,
      }));
    }
    return parsed.legalArticles;
  }, [sources, parsed.legalArticles]);

  const hasContent =
    parsed.conclusion || (parsed.keyPoints && parsed.keyPoints.length > 0);
  const hasArticles = finalArticles && finalArticles.length > 0;

  if (!hasContent && !hasArticles) return null;

  return (
    <div className="space-y-2">
      {/* ---- 主气泡：知识匹配度 + 结论 + 要点 ---- */}
      <div className="bg-slate-100 rounded-2xl rounded-tl-sm px-4 py-3 space-y-2.5">
        {/* 知识匹配度 Badge */}
        {confidence !== undefined && (
          <div className="flex items-center gap-2 mb-1">
            <span
              className={cn(
                "text-xs font-semibold px-2 py-0.5 rounded-full",
                confidence >= 0.8
                  ? "bg-green-100 text-green-700"
                  : confidence >= 0.5
                  ? "bg-amber-100 text-amber-700"
                  : "bg-red-100 text-red-700"
              )}
            >
              知识匹配度 {Math.round(confidence * 100)}%
            </span>
          </div>
        )}

        {/* 查询改写与分词结果 */}
        {(rewrittenQuery || (tokenizedQuery && tokenizedQuery.length > 0)) && (
          <div className="bg-blue-50 rounded-lg px-3 py-2 text-xs space-y-1.5">
            {rewrittenQuery && (
              <div className="flex items-start gap-2">
                <span className="text-blue-600 font-medium shrink-0">检索式:</span>
                <span className="text-slate-700 whitespace-pre-wrap">{rewrittenQuery}</span>
              </div>
            )}
            {tokenizedQuery && tokenizedQuery.length > 0 && (
              <div className="flex items-start gap-2">
                <span className="text-blue-600 font-medium shrink-0">分词:</span>
                <div className="flex flex-wrap gap-1">
                  {tokenizedQuery.map((token, idx) => (
                    <span
                      key={idx}
                      className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-xs"
                    >
                      {token}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 结论 */}
        {parsed.conclusion && (
          <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">
            {parsed.conclusion.replace(/\*\*/g, "")}
          </p>
        )}

        {/* 要点列表 */}
        {parsed.keyPoints && parsed.keyPoints.length > 0 && (
          <ul className="space-y-1.5">
            {parsed.keyPoints.map((point, index) => (
              <li key={index} className="flex gap-2 text-sm text-slate-700 leading-relaxed">
                <span className="text-blue-600 font-semibold shrink-0">
                  {index + 1}.
                </span>
                <span className="leading-relaxed">
                  {point.title && (
                    <strong className="font-bold text-slate-900">
                      {point.title.replace(/^\d+\.\s*/, "")}
                    </strong>
                  )}
                  {point.body && (
                    <span> {point.body.replace(/\*\*/g, "")}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ---- 底部白底法条卡片 ---- */}
      {hasArticles && (
        <div className="space-y-1.5">
          {finalArticles.map((article, index) => (
            <LegalArticleItem
              key={`${article.title || index}-${index}`}
              title={article.title}
              content={article.content}
            />
          ))}
        </div>
      )}
    </div>
  );
}
