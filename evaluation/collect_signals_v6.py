"""
Collect V6 signals from all available cases through the /verify-only API.
Targets 10 features + unverifiable_claim_count for V6 training.
"""

import json
import csv
import requests
import time
import sys
import os
from collections import Counter

API_URL = "http://localhost:8877/verify-only"

FEATURES = [
    'unsupported_claims_count',
    'coverage_ratio',
    'max_relative_error',
    'mean_relative_error',
    'scale_mismatch_count',
    'ambiguity_count',
    'pnl_identity_fail_count',
    'pnl_period_strict_mismatch_count',
    'grounding_confidence_score',
    'unverifiable_claim_count',
]

def call_api(case_id, question, evidence, candidate_answer):
    payload = {
        'question': question,
        'evidence': evidence,
        'candidate_answer': candidate_answer,
        'options': {'log_run': False}
    }
    resp = requests.post(API_URL, json=payload, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    signals = data.get('signals', {})
    return signals


def collect_from_cases_v2():
    rows = []
    with open('evaluation/cases_v2.json') as f:
        cases = json.load(f)

    skipped = 0
    for case in cases:
        case_id = case['id']
        label = case.get('expected_decision', '')
        if label not in ('ACCEPT', 'FLAG', 'REPAIR'):
            print(f"  Skip {case_id}: unknown label '{label}'")
            skipped += 1
            continue

        try:
            signals = call_api(
                case_id,
                case['question'],
                case['evidence'],
                case['candidate_answer']
            )
            row = {'case_id': case_id, 'label': label, 'source': 'cases_v2'}
            for feat in FEATURES:
                row[feat] = signals.get(feat, 0)
            rows.append(row)
        except Exception as e:
            print(f"  ERROR {case_id}: {e}")
            skipped += 1

    print(f"cases_v2.json: collected {len(rows)}, skipped {skipped}")
    return rows


def collect_from_error_injected():
    rows = []
    with open('evaluation/error_injected_cases.json') as f:
        cases = json.load(f)

    skipped = 0
    for case in cases:
        case_id = case.get('id', case.get('original_id', 'unknown'))
        label = case.get('expected_decision', 'FLAG')
        if label not in ('ACCEPT', 'FLAG', 'REPAIR'):
            label = 'FLAG'

        try:
            signals = call_api(
                case_id,
                case['question'],
                case['evidence'],
                case['candidate_answer']
            )
            row = {'case_id': case_id, 'label': label, 'source': 'error_injected'}
            for feat in FEATURES:
                row[feat] = signals.get(feat, 0)
            rows.append(row)
        except Exception as e:
            print(f"  ERROR {case_id}: {e}")
            skipped += 1

    print(f"error_injected_cases.json: collected {len(rows)}, skipped {skipped}")
    return rows


def main():
    print("=== Collecting V6 Signals ===")
    print()

    all_rows = []

    print("--- cases_v2.json (84 cases) ---")
    rows_v2 = collect_from_cases_v2()
    all_rows.extend(rows_v2)
    print()

    print("--- error_injected_cases.json (270 cases) ---")
    rows_ei = collect_from_error_injected()
    all_rows.extend(rows_ei)
    print()

    # Deduplicate by case_id (keep first)
    seen = set()
    deduped = []
    for row in all_rows:
        cid = row['case_id']
        if cid not in seen:
            seen.add(cid)
            deduped.append(row)
        else:
            print(f"  Dedup: skipping duplicate {cid}")

    all_rows = deduped

    # Save
    output_path = 'evaluation/signals_v6_complete.csv'
    fieldnames = ['case_id', 'label', 'source'] + FEATURES

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n=== SAVED {len(all_rows)} rows to {output_path} ===")

    label_counts = Counter(r['label'] for r in all_rows)
    print(f"Label distribution: {dict(label_counts)}")

    unverif_nonzero = sum(1 for r in all_rows if r.get('unverifiable_claim_count', 0) > 0)
    print(f"Cases with unverifiable_claim_count > 0: {unverif_nonzero}")

    return all_rows


if __name__ == '__main__':
    main()
