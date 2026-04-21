from typing import List, Dict

class RetrievalEvaluator:
    def __init__(self, top_k: int = 3):
        self.top_k = top_k

    def calculate_hit_rate(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 3) -> float:
        """
        TODO: Tính toán xem ít nhất 1 trong expected_ids có nằm trong top_k của retrieved_ids không.
        """
        top_retrieved = retrieved_ids[:top_k]
        hit = any(doc_id in top_retrieved for doc_id in expected_ids)
        return 1.0 if hit else 0.0

    def calculate_mrr(self, expected_ids: List[str], retrieved_ids: List[str]) -> float:
        """
        TODO: Tính Mean Reciprocal Rank.
        Tìm vị trí đầu tiên của một expected_id trong retrieved_ids.
        MRR = 1 / position (vị trí 1-indexed). Nếu không thấy thì là 0.
        """
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in expected_ids:
                return 1.0 / (i + 1)
        return 0.0

    def evaluate_case(self, expected_ids: List[str], retrieved_ids: List[str]) -> Dict:
        """
        Evaluate one case.
        If expected_ids is empty (out-of-context), mark excluded_from_avg=True.
        """
        expected_ids = expected_ids or []
        retrieved_ids = retrieved_ids or []

        if not expected_ids:
            return {
                "hit_rate": 0.0,
                "mrr": 0.0,
                "excluded_from_avg": True
            }

        return {
            "hit_rate": self.calculate_hit_rate(expected_ids, retrieved_ids, top_k=self.top_k),
            "mrr": self.calculate_mrr(expected_ids, retrieved_ids),
            "excluded_from_avg": False
        }

    async def evaluate_batch(self, dataset: List[Dict], responses: List[Dict]) -> Dict:
        """
        Evaluate full dataset from ground-truth chunk ids and retrieved ids.
        Dataset item requires: ground_truth_chunk_ids
        Response item requires: retrieved_ids
        """
        case_metrics = []
        included = 0
        hit_sum = 0.0
        mrr_sum = 0.0
        out_of_context_count = 0

        for case, resp in zip(dataset, responses):
            expected_ids = case.get("ground_truth_chunk_ids", [])
            retrieved_ids = resp.get("retrieved_ids", [])
            metrics = self.evaluate_case(expected_ids, retrieved_ids)
            case_metrics.append(metrics)

            if metrics["excluded_from_avg"]:
                out_of_context_count += 1
                continue

            included += 1
            hit_sum += metrics["hit_rate"]
            mrr_sum += metrics["mrr"]

        if included == 0:
            avg_hit_rate = 0.0
            avg_mrr = 0.0
        else:
            avg_hit_rate = hit_sum / included
            avg_mrr = mrr_sum / included

        return {
            "avg_hit_rate": avg_hit_rate,
            "avg_mrr": avg_mrr,
            "included_cases": included,
            "out_of_context_cases": out_of_context_count,
            "case_metrics": case_metrics
        }
