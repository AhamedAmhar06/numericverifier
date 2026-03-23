import json

RESULTS_FILE = "evaluation_results.json"
SUMMARY_FILE = "evaluation_summary.txt"


def load_results(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_get_signals(entry):
    resp = entry.get("response") if isinstance(entry.get("response"), dict) else None
    if not resp:
        return {}
    return resp.get("signals", {})


def main():
    results = load_results(RESULTS_FILE)

    total = len(results)
    accept = 0
    repair = 0
    flag = 0
    other = 0

    scale_mismatch = 0
    period_mismatch = 0
    recomputation_failures = 0
    ambiguous_groundings = 0
    recomputation_fail_cases = 0

    for entry in results:
        resp = entry.get("response") if isinstance(entry.get("response"), dict) else None
        decision = None
        if resp:
            decision = resp.get("decision")
        if not decision and resp and isinstance(resp.get("report"), dict):
            decision = resp.get("report", {}).get("decision")

        if decision:
            d = decision.upper()
            if d == "ACCEPT":
                accept += 1
            elif d == "REPAIR":
                repair += 1
            elif d == "FLAG":
                flag += 1
            else:
                other += 1
        else:
            other += 1

        signals = safe_get_signals(entry)
        scale_mismatch += int(signals.get("scale_mismatch_count", 0) or 0)
        period_mismatch += int(signals.get("period_mismatch_count", 0) or 0)
        # some older keys
        recomputation_failures += int(signals.get("recomputation_fail_count", 0) or 0)
        ambiguous_groundings += int(signals.get("ambiguity_count", 0) or 0)

    summary_lines = [
        f"Total cases: {total}",
        f"ACCEPT: {accept}",
        f"REPAIR: {repair}",
        f"FLAG: {flag}",
        f"OTHER/UNKNOWN decisions: {other}",
        "",
        f"Scale mismatch count (sum of signals): {scale_mismatch}",
        f"Period mismatch count (sum of signals): {period_mismatch}",
        f"Recomputation failures (sum of signals): {recomputation_failures}",
        f"Ambiguous groundings (sum of signals): {ambiguous_groundings}",
    ]

    summary = "\n".join(summary_lines)
    print(summary)

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(summary)

    print(f"Saved summary to {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
