import os

class ReleaseGate:
    def __init__(self, thresholds: dict = None):
        """
        Thresholds cho phép xác định các ngưỡng để duyệt bản nâng cấp.
        """
        self.thresholds = thresholds or {
            "min_score_delta": 0.0,       # Không được thấp điểm hơn bản cũ
            "min_hit_rate_delta": 0.0,   # Hit rate không được giảm
            "max_cost_increase": 0.2,    # Chi phí không tăng quá 20%
            "min_agreement": 0.6         # Độ tin cậy của Judge > 60%
        }

    def check(self, v1_summary: dict, v2_summary: dict) -> dict:
        """
        So sánh V1 và V2 dựa trên summary objects đầy đủ.
        """
        reasons = []
        is_approved = True
        
        v1_metrics = v1_summary.get("metrics", {})
        v2_metrics = v2_summary.get("metrics", {})
        v2_pf = v2_summary.get("pass_fail", {})
        v1_pf = v1_summary.get("pass_fail", {})
        v2_perf = v2_summary.get("performance", {})
        v1_perf = v1_summary.get("performance", {})
        v2_jr = v2_summary.get("judge_reliability", {})

        # 1. So sánh điểm (Quality)
        score_delta = v2_metrics.get("avg_score", 0) - v1_metrics.get("avg_score", 0)
        if score_delta < self.thresholds.get("min_score_delta", 0.0):
            is_approved = False
            reasons.append(f"Quality regression: Score decreased by {abs(score_delta):.2f}")

        # 2. So sánh Pass Rate 
        pass_rate_v1 = v1_pf.get("pass_rate", 0)
        pass_rate_v2 = v2_pf.get("pass_rate", 0)
        if pass_rate_v2 < pass_rate_v1:
            is_approved = False
            reasons.append(f"Pass Rate regression: {pass_rate_v2}% < {pass_rate_v1}%")

        # 3. So sánh Retrieval (Hit Rate)
        hit_rate_delta = v2_metrics.get("hit_rate", 0) - v1_metrics.get("hit_rate", 0)
        if hit_rate_delta < self.thresholds.get("min_hit_rate_delta", 0.0):
            is_approved = False
            reasons.append(f"Retrieval regression: Hit Rate dropped by {abs(hit_rate_delta)*100:.1f}%")

        # 4. Kiểm tra độ đồng thuận (Agreement/Kappa)
        kappa = v2_jr.get("cohens_kappa", 1.0)
        min_kappa = self.thresholds.get("min_kappa", 0.2)
        if kappa < min_kappa:
            is_approved = False
            reasons.append(f"Low Judge Reliability: Cohen's Kappa {kappa} < {min_kappa}")

        # 5. So sánh chi phí (Cost)
        cost_v1 = v1_perf.get("total_cost_usd", 0.0001)
        cost_v2 = v2_perf.get("total_cost_usd", 0)
        cost_increase = (cost_v2 - cost_v1) / cost_v1
        max_increase = self.thresholds.get("max_cost_increase", 0.2)
        if cost_increase > max_increase:
            is_approved = False
            reasons.append(f"Cost increase too high: {cost_increase*100:.1f}% (Limit: {max_increase*100}%)")

        return {
            "approved": is_approved,
            "score_delta": score_delta,
            "reasons": reasons,
            "metrics_comparison": {
                "score": (v1_metrics.get("avg_score"), v2_metrics.get("avg_score")),
                "pass_rate": (pass_rate_v1, pass_rate_v2),
                "cost": (cost_v1, cost_v2),
                "kappa": kappa
            }
        }

    def report(self, result: dict):
        """
        In báo cáo màu sắc ra terminal.
        """
        GREEN = "\033[92m"
        RED = "\033[91m"
        YELLOW = "\033[93m"
        RESET = "\033[0m"
        BOLD = "\033[1m"

        print("\n" + "="*50)
        print(f"{BOLD}REGRESSION ANALYSIS REPORT{RESET}")
        print("="*50)

        delta = result["score_delta"]
        color = GREEN if delta >= 0 else RED
        print(f"Overall Quality Delta: {color}{'+' if delta >= 0 else ''}{delta:.2f}{RESET}")

        if result["approved"]:
            print(f"\n{GREEN}{BOLD}[OK] PASSED RELEASE GATE (APPROVE){RESET}")
            if delta > 0:
                print(f"Ready for production with improvements.")
            else:
                print(f"Maintenance release: Quality is stable.")
        else:
            print(f"\n{RED}{BOLD}[FAIL] ROLLBACK REQUIRED (BLOCKED){RESET}")
            print(f"{BOLD}Reason(s):{RESET}")
            for reason in result["reasons"]:
                print(f"  - {reason}")
        
        print("="*50 + "\n")
