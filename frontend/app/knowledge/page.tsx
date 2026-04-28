import type { Metadata } from "next";
import KnowledgeUpload from "@/components/knowledge/knowledge-upload";

export const metadata: Metadata = {
  title: "知识库管理 - LawBot+",
  description: "管理法律知识库，上传和去重法律条文",
};

export default function KnowledgePage() {
  return <KnowledgeUpload />;
}
