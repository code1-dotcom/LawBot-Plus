import { NextRequest, NextResponse } from "next/server";
import { API_BASE_URL } from "@/lib/api";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { message, session_id } = body;

    if (!message) {
      return NextResponse.json(
        { error: "message is required" },
        { status: 400 }
      );
    }

    // 调用后端 API
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: message,
        session_id: session_id || `session-${Date.now()}`,
      }),
    });

    if (!response.ok) {
      throw new Error(`Backend API error: ${response.status}`);
    }

    const data = await response.json();

    return NextResponse.json({
      answer: data.result?.answer || data.message || "",
      session_id: data.session_id || session_id,
      sources: data.result?.sources || [],
      confidence: data.result?.confidence ?? data.confidence,
      needs_review: data.result?.needs_review ?? data.needs_review,
      rewritten_query: data.rewritten_query,
      tokenized_query: data.tokenized_query || [],
    });
  } catch (error) {
    console.error("Chat API error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
