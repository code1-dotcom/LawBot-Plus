"""RAGAS 离线批量评估脚本

从 RetrievalEvalLog 表读取最近 N 天的埋点数据，
转换为 RAGAS Dataset 格式，使用 Judge LLM 计算忠实度、精确度、召回率，
输出终端格式化报告并导出 CSV。

依赖检查：ragas 未安装时打印提示并退出。

用法:
    python eval/run_ragas_eval.py                    # 默认最近 30 天
    python eval/run_ragas_eval.py --days 7          # 最近 7 天
    python eval/run_ragas_eval.py --output my.csv    # 指定导出路径
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ============== 依赖检查 ==============
try:
    from ragas import evaluate
    from ragas.dataset_schema import Dataset
    from ragas.metrics import Faithfulness, ContextPrecision, ContextRecall
except ImportError:
    print("=" * 60)
    print("[ERROR] ragas 未安装，无法运行评估。")
    print("请运行: pip install ragas")
    print("=" * 60)
    sys.exit(1)

from langchain_openai import ChatOpenAI

from src.config import get_settings
from src.db.database import sync_engine
from src.db.models import RetrievalEvalLog
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import select, text


# ============== 配置 ==============

settings = get_settings()
SyncSession = sessionmaker(bind=sync_engine, expire_on_commit=False)


def load_eval_data(days: int = 30) -> list[dict[str, Any]]:
    """
    从 RetrievalEvalLog 表读取最近 N 天的埋点数据。

    Args:
        days: 回看天数，默认 30 天

    Returns:
        每条记录转为 dict，包含 query / contexts / answer / ground_truth
    """
    cutoff = datetime.now() - timedelta(days=days)

    with SyncSession() as db:
        records = (
            db.execute(
                select(RetrievalEvalLog)
                .where(RetrievalEvalLog.created_at >= cutoff)
                .order_by(RetrievalEvalLog.created_at.desc())
            )
            .scalars()
            .all()
        )

    rows = []
    for r in records:
        # contexts: RAGAS 要求 List[List[str]]，每条 context 为一段文本
        contexts_raw: list[str] = r.reranked_doc_ids or []
        contexts: list[list[str]] = (
            [[c] for c in contexts_raw] if contexts_raw else [["（无相关法律依据）"]]
        )

        # ground_truths: RAGAS 要求 List[List[str]]
        # user_feedback 非空时使用，否则占位
        if r.user_feedback is not None:
            gt: list[list[str]] = [[str(r.user_feedback)]]
        else:
            gt = [["暂无人工标注"]]

        rows.append({
            "user_input": r.query,
            "response": r.final_answer or "（无回答）",
            "retrieved_contexts": contexts,
            "ground_truth": gt,
        })

    return rows


def build_dataset(rows: list[dict[str, Any]]) -> Dataset:
    """
    将行数据转换为 RAGAS Dataset。

    RAGAS 期望的列名（默认）：
        user_input   - 用户问题
        response      - AI 回答
        retrieved_contexts - List[List[str]]，内层每个元素是一个 context chunk
        ground_truth  - List[List[str]]
    """
    from ragas.dataset_schema import Dataset
    import pandas as pd

    df = pd.DataFrame(rows)
    return Dataset.from_pandas(df)


def run_evaluation(dataset: Dataset, model_name: str = "qwen-plus") -> dict[str, Any]:
    """
    使用 Judge LLM 运行 RAGAS 评估。

    Args:
        dataset: 转换好的 RAGAS Dataset
        model_name: Judge LLM 模型名，默认 qwen-plus

    Returns:
        评估结果 dict，键为指标名（faithfulness / context_precision / context_recall）
    """
    judge_llm = ChatOpenAI(
        model=model_name,
        temperature=0.1,
        base_url=settings.dashscope_base_url,
        api_key=settings.dashscope_api_key,
    )

    metrics = [
        Faithfulness(llm=judge_llm),
        ContextPrecision(llm=judge_llm),
        ContextRecall(llm=judge_llm),
    ]

    print("[RAGAS] 开始评估（raise_exceptions=False）...")
    result = evaluate(dataset, metrics=metrics, raise_exceptions=False)
    return result


def format_report(
    result: dict[str, Any],
    total: int,
    days: int,
    output_path: Path | None,
) -> str:
    """生成终端格式化报告。"""
    score_map = {
        "faithfulness": ("忠实度", "Faithfulness"),
        "context_precision": ("精确度", "Context Precision"),
        "context_recall": ("召回率", "Context Recall"),
    }

    lines = []
    sep = "=" * 60

    lines.append(sep)
    lines.append(f"RAGAS 评估报告  |  数据范围: 近 {days} 天  |  样本数: {total}")
    lines.append(sep)

    for key, (cn, en) in score_map.items():
        val = result.get(key)
        if val is None:
            bar = "[  数据不可用  ]"
            lines.append(f"  {cn}（{en}）  : {bar}")
            continue

        # 0-1 → 百分比
        pct = float(val) * 100
        filled = int(pct / 5)
        bar = "█" * filled + "░" * (20 - filled)
        grade = (
            "A"
            if pct >= 80
            else "B"
            if pct >= 60
            else "C"
            if pct >= 40
            else "D"
        )
        lines.append(f"  {cn}（{en}）  : [{bar}] {pct:5.1f}%  等级 {grade}")

    lines.append(sep)

    # 整体评分
    scores = [result.get(k) for k in score_map if result.get(k) is not None]
    if scores:
        avg = sum(scores) / len(scores) * 100
        lines.append(f"  综合得分  : {avg:5.1f}%")
    lines.append(sep)

    if output_path:
        lines.append(f"  CSV 已导出: {output_path.resolve()}")
        lines.append(sep)

    return "\n".join(lines)


def export_csv(rows: list[dict[str, Any]], result: dict[str, Any], output_path: Path) -> None:
    """将评估结果导出为 CSV。"""
    import pandas as pd

    records = []
    for i, row in enumerate(rows):
        records.append({
            "user_input": row["user_input"],
            "final_answer": row["response"],
            "contexts": " | ".join(
                c[0] if isinstance(c, list) else c
                for c in row["retrieved_contexts"]
            ),
            "ground_truth": row["ground_truth"][0][0] if row["ground_truth"] else "",
            "faithfulness": result.get("faithfulness"),
            "context_precision": result.get("context_precision"),
            "context_recall": result.get("context_recall"),
        })

    df = pd.DataFrame(records)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[CSV] 导出完成: {output_path.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LawBot+ RAGAS 离线批量评估")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="回看天数，默认 30 天",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="CSV 导出路径，默认 data/ragas_report_YYYYMMDD.csv",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="qwen-plus",
        help="Judge LLM 模型名，默认 qwen-plus",
    )
    args = parser.parse_args()

    # 1. 加载数据
    print(f"[1/4] 加载最近 {args.days} 天的评估数据...")
    rows = load_eval_data(args.days)
    if not rows:
        print("[WARN] 未找到任何评估数据，请确认 RetrievalEvalLog 表有数据且在回看期内。")
        sys.exit(0)
    print(f"       加载到 {len(rows)} 条记录")

    # 2. 转换 Dataset
    print("[2/4] 构建 RAGAS Dataset...")
    dataset = build_dataset(rows)
    print(f"       Dataset 样本数: {len(dataset)}")

    # 3. 运行评估
    print(f"[3/4] 使用 Judge LLM（{args.model}）运行评估...")
    try:
        result = run_evaluation(dataset, model_name=args.model)
    except Exception as e:
        print(f"[ERROR] 评估过程异常: {e}")
        sys.exit(1)

    # 4. 输出报告
    print("[4/4] 生成报告...")

    if args.output:
        output_path = Path(args.output)
    else:
        today = datetime.now().strftime("%Y%m%d")
        output_path = Path("data") / f"ragas_report_{today}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    export_csv(rows, result, output_path)
    report = format_report(result, len(rows), args.days, output_path)
    print("\n" + report)


if __name__ == "__main__":
    main()
