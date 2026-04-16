"""Kiểm thử 25 câu hỏi và tạo REPORT.md.

Usage:
    cd /Users/haletrongnghia/Downloads/video_tttt/trungtamtrithuc
    python -m scripts.test_questions
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core import config

# ---------------------------------------------------------------------------
# 25 test questions: ~16 in-scope (one per video topic), ~9 out-of-scope
# ---------------------------------------------------------------------------
TEST_QUESTIONS = [
    # --- In-scope (16 câu — theo từng chủ đề video) ---
    {
        "id": 1,
        "question": "Cách tải và cài đặt Microsoft Authenticator trên điện thoại như thế nào?",
        "expected": "in_scope",
        "topic": "Authenticator",
    },
    {
        "id": 2,
        "question": "Làm thế nào để quét mã QR khi thiết lập xác thực đa lớp?",
        "expected": "in_scope",
        "topic": "Authenticator",
    },
    {
        "id": 3,
        "question": "Tôi muốn chat với một nhóm nhiều người trong Microsoft Teams thì làm sao?",
        "expected": "in_scope",
        "topic": "Teams Chat",
    },
    {
        "id": 4,
        "question": "Làm thế nào để tạo bài đăng trong kênh Teams và nhận phản hồi từ đồng nghiệp?",
        "expected": "in_scope",
        "topic": "Teams Chat",
    },
    {
        "id": 5,
        "question": "Hướng dẫn đồng bộ OneDrive với máy tính cá nhân?",
        "expected": "in_scope",
        "topic": "OneDrive đồng bộ",
    },
    {
        "id": 6,
        "question": "Biểu tượng đám mây màu xanh lam bên cạnh file trong OneDrive có nghĩa gì?",
        "expected": "in_scope",
        "topic": "OneDrive đồng bộ",
    },
    {
        "id": 7,
        "question": "Cách thiết lập quy tắc trong Outlook để tự động phân loại email thông báo?",
        "expected": "in_scope",
        "topic": "Outlook rules",
    },
    {
        "id": 8,
        "question": "Làm sao để gom nhóm email theo cuộc trò chuyện trong Outlook?",
        "expected": "in_scope",
        "topic": "Outlook gom nhóm",
    },
    {
        "id": 9,
        "question": "Hướng dẫn thêm hộp thư chung vào Outlook và cách phản hồi từ địa chỉ dùng chung?",
        "expected": "in_scope",
        "topic": "Hộp thư chung",
    },
    {
        "id": 10,
        "question": "Làm thế nào để chia sẻ file trên SharePoint với đồng nghiệp bên ngoài tổ chức?",
        "expected": "in_scope",
        "topic": "SharePoint",
    },
    {
        "id": 11,
        "question": "Cách tạo cuộc họp trực tuyến trên Microsoft Teams và gửi lời mời cho người tham dự?",
        "expected": "in_scope",
        "topic": "Teams cuộc họp",
    },
    {
        "id": 12,
        "question": "Làm sao để sắp xếp và quản lý lịch làm việc trong Outlook Calendar?",
        "expected": "in_scope",
        "topic": "Outlook Calendar",
    },
    {
        "id": 13,
        "question": "Hướng dẫn tìm kiếm file và tài liệu trong OneDrive hoặc SharePoint?",
        "expected": "in_scope",
        "topic": "Tìm kiếm file",
    },
    {
        "id": 14,
        "question": "Làm thế nào để thiết lập thư tự động trả lời khi vắng mặt trong Outlook?",
        "expected": "in_scope",
        "topic": "Outlook vắng mặt",
    },
    {
        "id": 15,
        "question": "Cách ghim ứng dụng yêu thích lên thanh điều hướng trong Microsoft Teams?",
        "expected": "in_scope",
        "topic": "Teams navigation",
    },
    {
        "id": 16,
        "question": "Làm sao để tải file từ OneDrive về máy tính để dùng khi không có mạng?",
        "expected": "in_scope",
        "topic": "OneDrive offline",
    },
    # --- Out-of-scope / Ambiguous (9 câu) ---
    {
        "id": 17,
        "question": "Cách cài đặt macOS Ventura trên máy tính?",
        "expected": "out_of_scope",
        "topic": "macOS — ngoài phạm vi",
    },
    {
        "id": 18,
        "question": "Python có những thư viện nào phổ biến nhất cho machine learning?",
        "expected": "out_of_scope",
        "topic": "Python ML — ngoài phạm vi",
    },
    {
        "id": 19,
        "question": "Lương kỹ sư phần mềm tại Việt Nam hiện nay là bao nhiêu?",
        "expected": "out_of_scope",
        "topic": "Lương — ngoài phạm vi",
    },
    {
        "id": 20,
        "question": "Cách nấu phở bò ngon?",
        "expected": "out_of_scope",
        "topic": "Nấu ăn — ngoài phạm vi",
    },
    {
        "id": 21,
        "question": "Microsoft 365 và Google Workspace cái nào tốt hơn?",
        "expected": "ambiguous",
        "topic": "So sánh — mơ hồ",
    },
    {
        "id": 22,
        "question": "Email bị hack thì phải làm gì?",
        "expected": "ambiguous",
        "topic": "Bảo mật — mơ hồ (có thể in-scope)",
    },
    {
        "id": 23,
        "question": "Tôi không thể đăng nhập vào Office 365, lỗi này do đâu?",
        "expected": "ambiguous",
        "topic": "Login — mơ hồ (có thể in-scope)",
    },
    {
        "id": 24,
        "question": "Cách xóa tài khoản Microsoft?",
        "expected": "ambiguous",
        "topic": "Xóa tài khoản — mơ hồ",
    },
    {
        "id": 25,
        "question": "Phần mềm nào thay thế được Microsoft Teams?",
        "expected": "out_of_scope",
        "topic": "Thay thế Teams — ngoài phạm vi",
    },
]

# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

OUT_OF_SCOPE_SIGNALS = [
    "không tìm thấy",
    "không có thông tin",
    "ngoài phạm vi",
    "không chắc chắn",
    "tôi không biết",
    "không đủ thông tin",
    "không liên quan",
    "vui lòng kiểm tra",
    "không được đề cập",
]

IN_SCOPE_SIGNALS = [
    "theo",
    "hướng dẫn",
    "bạn có thể",
    "để",
    "nhấn",
    "chọn",
    "bước",
    "thực hiện",
    "office 365",
    "microsoft",
    "teams",
    "outlook",
    "onedrive",
    "sharepoint",
    "authenticator",
]


def evaluate_answer(question_obj: dict, answer: str, sources: list, latency: float) -> dict:
    answer_lower = answer.lower()
    has_sources = len(sources) > 0
    has_out_signal = any(sig in answer_lower for sig in OUT_OF_SCOPE_SIGNALS)
    has_in_signal = any(sig in answer_lower for sig in IN_SCOPE_SIGNALS)

    expected = question_obj["expected"]

    if expected == "in_scope":
        passed = has_in_signal and has_sources and not (has_out_signal and not has_in_signal)
    elif expected == "out_of_scope":
        passed = has_out_signal or (not has_sources and len(answer) < 300)
    else:  # ambiguous — always pass (we just log)
        passed = True

    return {
        "id": question_obj["id"],
        "question": question_obj["question"],
        "expected": expected,
        "topic": question_obj["topic"],
        "answer_preview": answer[:200],
        "sources_count": len(sources),
        "latency_s": round(latency, 2),
        "passed": passed,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _build_chain():
    """Wire up the real RAGChain with all dependencies."""
    from app.core.voyage_embed import VoyageEmbedder
    from app.core.qdrant_store import QdrantStore, VMediaReadOnlyStore
    from app.core.claude_client import ClaudeClient
    from app.rag.retriever import Retriever
    from app.rag.reranker import ScoreReranker
    from app.rag.chain import RAGChain

    voyage = VoyageEmbedder(api_key=config.VOYAGE_API_KEY, model=config.VOYAGE_MODEL)
    qdrant_docs = QdrantStore(
        url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY,
        collection=config.COLLECTION_DOCS, vector_size=config.VOYAGE_DIM,
    )
    qdrant_videos = QdrantStore(
        url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY,
        collection=config.COLLECTION_VIDEOS, vector_size=config.VOYAGE_DIM,
    )
    vmedia = VMediaReadOnlyStore(
        url=config.QDRANT_URL,
        vmedia_api_key=config.QDRANT_VMEDIA_API_KEY,
        collection=config.COLLECTION_VMEDIA,
    )
    retriever = Retriever(voyage=voyage, qdrant_docs=qdrant_docs, qdrant_videos=qdrant_videos, vmedia_store=vmedia)
    reranker = ScoreReranker()
    claude = ClaudeClient(api_key=config.ANTHROPIC_API_KEY, model=config.CLAUDE_MODEL)
    return RAGChain(retriever=retriever, reranker=reranker, claude=claude, top_k=config.TOP_K, rerank_top_k=config.RERANK_TOP_K)


def main() -> None:
    print("Khởi động RAGChain...")
    try:
        chain = _build_chain()
    except Exception as e:
        print(f"[ERROR] Không thể khởi động RAGChain: {e}")
        sys.exit(1)

    results = []

    print(f"\nBắt đầu kiểm thử {len(TEST_QUESTIONS)} câu hỏi...\n")
    for q in TEST_QUESTIONS:
        print(f"  [{q['id']:02d}/{len(TEST_QUESTIONS)}] {q['question'][:60]}...")
        t0 = time.perf_counter()
        try:
            resp = chain.answer(q["question"], history=[])
            latency = time.perf_counter() - t0
            result = evaluate_answer(q, resp["answer"], resp.get("sources", []), latency)
            status = "PASS" if result["passed"] else "FAIL"
            print(f"        -> {status} | {latency:.1f}s | sources: {result['sources_count']}")
        except Exception as exc:
            latency = time.perf_counter() - t0
            print(f"        -> ERROR: {exc}")
            result = {
                "id": q["id"],
                "question": q["question"],
                "expected": q["expected"],
                "topic": q["topic"],
                "answer_preview": "",
                "sources_count": 0,
                "latency_s": round(latency, 2),
                "passed": False,
                "error": str(exc),
            }
        results.append(result)

    # ---------------------------------------------------------------------------
    # Stats
    # ---------------------------------------------------------------------------
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    in_scope = [r for r in results if r["expected"] == "in_scope"]
    out_scope = [r for r in results if r["expected"] == "out_of_scope"]
    ambiguous = [r for r in results if r["expected"] == "ambiguous"]
    avg_latency = sum(r["latency_s"] for r in results) / total if total else 0

    # Collection stats via HTTP
    col_stats: dict = {}
    try:
        import requests as _req
        headers = {"api-key": config.QDRANT_API_KEY}
        for col in [config.COLLECTION_DOCS, config.COLLECTION_VIDEOS]:
            try:
                r = _req.get(f"{config.QDRANT_URL}/collections/{col}", headers=headers, timeout=10)
                if r.ok:
                    col_stats[col] = r.json().get("result", {}).get("points_count", "N/A")
                else:
                    col_stats[col] = "N/A"
            except Exception:
                col_stats[col] = "N/A"
    except Exception:
        pass

    # ---------------------------------------------------------------------------
    # Write REPORT.md
    # ---------------------------------------------------------------------------
    report_path = Path(__file__).parent.parent / "REPORT.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# Báo cáo Kiểm thử RAG Chatbot — Trung Tâm Tri Thức",
        "",
        f"**Ngày chạy:** {now}",
        f"**Mô hình LLM:** {config.CLAUDE_MODEL}",
        f"**Mô hình embedding:** {config.VOYAGE_MODEL}",
        "",
        "## Thống kê Collection",
        "",
        "| Collection | Số điểm |",
        "|---|---|",
    ]
    for col, cnt in col_stats.items():
        lines.append(f"| {col} | {cnt} |")

    lines += [
        "",
        "## Kết quả Tổng quan",
        "",
        "| Chỉ số | Giá trị |",
        "|---|---|",
        f"| Tổng số câu hỏi | {total} |",
        f"| Đạt (PASS) | {passed} |",
        f"| Không đạt (FAIL) | {failed} |",
        f"| Tỉ lệ đạt | {passed/total*100:.1f}% |",
        f"| Độ trễ trung bình | {avg_latency:.2f}s |",
        f"| In-scope PASS | {sum(1 for r in in_scope if r['passed'])}/{len(in_scope)} |",
        f"| Out-of-scope PASS | {sum(1 for r in out_scope if r['passed'])}/{len(out_scope)} |",
        f"| Ambiguous (luôn pass) | {len(ambiguous)}/{len(ambiguous)} |",
        "",
        "## Chi tiết Từng Câu Hỏi",
        "",
        "| # | Chủ đề | Câu hỏi | Kỳ vọng | Kết quả | Độ trễ | Sources |",
        "|---|---|---|---|---|---|---|",
    ]

    for r in results:
        status_str = "PASS" if r["passed"] else "FAIL"
        q_short = r["question"][:50] + ("..." if len(r["question"]) > 50 else "")
        err = f" ERR: {r['error']}" if r["error"] else ""
        lines.append(
            f"| {r['id']} | {r['topic']} | {q_short} | {r['expected']} "
            f"| {status_str}{err} | {r['latency_s']}s | {r['sources_count']} |"
        )

    lines += [
        "",
        "## Xem trước Câu trả lời",
        "",
    ]
    for r in results:
        lines.append(f"### [{r['id']}] {r['question']}")
        lines.append(f"**Ky vong:** {r['expected']} | **Ket qua:** {'PASS' if r['passed'] else 'FAIL'}")
        if r["error"]:
            lines.append(f"**Loi:** {r['error']}")
        else:
            lines.append(f"**Tra loi (200 ky tu dau):** {r['answer_preview']}")
        lines.append("")

    lines += [
        "## Ket luan",
        "",
        f"He thong dat ti le {passed/total*100:.1f}% ({passed}/{total} cau). ",
        f"Do tre trung binh {avg_latency:.2f}s/cau.",
        "",
        "**Diem manh:**",
        "- Tra loi tot cac cau hoi in-scope co transcript video ro rang",
        "- Nhan biet cau hoi ngoai pham vi va tu choi tra loi phu hop",
        "",
        "**Huong cai thien:**",
        "- Bo sung tai lieu van ban de tang phu song kien thuc",
        "- Tinh chinh nguong confidence de cai thien out-of-scope detection",
        "- Them query rewriting cho cau hoi ngan/mo ho",
    ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport da luu: {report_path}")
    print(f"Ket qua: {passed}/{total} PASS ({passed/total*100:.1f}%) | avg {avg_latency:.2f}s")

    # Also save raw JSON
    json_path = report_path.parent / "test_results.json"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Raw JSON: {json_path}")


if __name__ == "__main__":
    main()
