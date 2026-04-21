import time
from statistics import mean
from typing import Any, Dict, List


class PerformanceTracker:
    """
    Utility module cho phần việc của Thuận:
    - tổng hợp token usage / cost
    - đánh giá throughput và mục tiêu runtime
    - tạo summary phụ để Tuấn có thể import khi tích hợp
    """

    def __init__(self, *, runtime_target_sec: float = 120.0, target_cases: int = 50):
        self.runtime_target_sec = runtime_target_sec
        self.target_cases = target_cases

    def build_eval_summary(self, results: List[Dict[str, Any]], agent_version: str) -> Dict[str, Any]:
        total = len(results)
        passed = sum(1 for item in results if item.get("status") == "pass")
        failed = total - passed
        total_latency = sum(item.get("latency", 0.0) for item in results)
        total_wall_time = sum(item.get("wall_time", item.get("latency", 0.0)) for item in results)
        total_tokens = sum(item.get("token_usage", {}).get("total_tokens", 0) for item in results)
        total_cost = round(sum(item.get("cost_usd", 0.0) for item in results), 6)

        return {
            "metadata": {
                "version": agent_version,
                "total": total,
                "passed": passed,
                "failed": failed,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "metrics": {
                "avg_score": self._avg([item.get("judge", {}).get("final_score", 0.0) for item in results]),
                "hit_rate": self._avg([item.get("ragas", {}).get("retrieval", {}).get("hit_rate", 0.0) for item in results]),
                "mrr": self._avg([item.get("ragas", {}).get("retrieval", {}).get("mrr", 0.0) for item in results]),
                "agreement_rate": self._avg([item.get("judge", {}).get("agreement_rate", 0.0) for item in results]),
                "avg_latency_sec": self._avg([item.get("latency", 0.0) for item in results]),
                "avg_wall_time_sec": self._avg([item.get("wall_time", item.get("latency", 0.0)) for item in results]),
                "total_tokens": total_tokens,
                "avg_tokens_per_case": (total_tokens / total) if total else 0.0,
                "total_cost_usd": total_cost,
                "avg_cost_usd": round(total_cost / total, 6) if total else 0.0,
            },
            "performance": {
                "target_cases": self.target_cases,
                "target_runtime_sec": self.runtime_target_sec,
                "estimated_serial_runtime_sec": round(total_latency, 3),
                "aggregate_wall_time_sec": round(total_wall_time, 3),
                "throughput_cases_per_sec": round(total / total_wall_time, 3) if total_wall_time else 0.0,
                "met_runtime_target": total_wall_time <= self.runtime_target_sec if total else False,
            },
            "distribution": {
                "by_question_type": self._count_by_key(results, "question_type"),
                "by_complexity": self._count_by_key(results, "complexity"),
                "by_status": self._count_by_key(results, "status"),
            },
            "cost_optimization_note": (
                "Dùng model nhỏ cho case dễ hoặc case có retrieval/judge đồng thuận cao; "
                "chỉ escalate sang model lớn khi hit rate thấp, câu hỏi dài, hoặc judge bất đồng mạnh."
            ),
        }

    def _count_by_key(self, items: List[Dict[str, Any]], key: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for item in items:
            value = item.get(key, "unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts

    def _avg(self, values: List[float]) -> float:
        return mean(values) if values else 0.0
