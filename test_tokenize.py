import sys
sys.path.append(".")
from src.rag.bm25_search import BM25Search

bm25 = BM25Search()
test_cases = [
    "用人单位未支付加班费属于违法",
    "无过错责任原则在机动车交通事故中的应用",
    "劳动者主张加班费的举证责任倒置"
]
for t in test_cases:
    print(f"原文: {t}")
    print(f"分词: {bm25._tokenize(t)}\n")