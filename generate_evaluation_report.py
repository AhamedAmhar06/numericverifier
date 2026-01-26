#!/usr/bin/env python3
"""Generate evaluation report from results."""
import json
from pathlib import Path

RESULTS_FILE = Path(__file__).parent / "evaluation_results.json"
REPORT_FILE = Path(__file__).parent / "evaluation_report.md"

with open(RESULTS_FILE, 'r') as f:
    data = json.load(f)

results = data["results"]

# Generate results table
table_rows = []
for r in results:
    signals = r["key_signals"]
    key_signal_str = f"Coverage: {signals.get('coverage_ratio', 0):.1%}, "
    key_signal_str += f"Unsupported: {signals.get('unsupported_claims', 0)}, "
    key_signal_str += f"Recomp fails: {signals.get('recomputation_failures', 0)}, "
    key_signal_str += f"Scale mismatches: {signals.get('scale_mismatches', 0)}, "
    key_signal_str += f"Period mismatches: {signals.get('period_mismatches', 0)}, "
    key_signal_str += f"Ambiguity: {signals.get('ambiguity_count', 0)}"
    
    table_rows.append({
        "case_type": r["category"],
        "expected": r["expected"],
        "actual": r["actual"],
        "key_signals": key_signal_str,
        "analysis": r["outcome"]
    })

# Generate report
report = """# NumericVerifier – Evaluation Results

## Results Table

| Case Type | Expected | Actual | Key Signals | Analysis |
|-----------|----------|--------|-------------|----------|
"""

for row in table_rows:
    report += f"| {row['case_type']} | {row['expected']} | {row['actual']} | {row['key_signals']} | {row['analysis']} |\n"

# Summary statistics
correct = sum(1 for r in results if r["outcome"] == "Correct behaviour")
over_permissive = sum(1 for r in results if r["outcome"] == "Over-permissive")
over_conservative = sum(1 for r in results if r["outcome"] == "Over-conservative")
limitations = sum(1 for r in results if "Limitation" in r["outcome"])

report += f"""
## Summary Statistics

- **Total test cases**: {len(results)}
- **Correct behaviour**: {correct} ({correct/len(results)*100:.0f}%)
- **Over-permissive**: {over_permissive} ({over_permissive/len(results)*100:.0f}%)
- **Over-conservative**: {over_conservative} ({over_conservative/len(results)*100:.0f}%)
- **Limitations**: {limitations} ({limitations/len(results)*100:.0f}%)

## Detailed Analysis

### Strengths

1. **Reliable numeric matching**: The system correctly identifies and matches numeric values from evidence (T1, T10). Coverage calculation works well for straightforward cases.

2. **Percent change detection**: The execution engine successfully identifies and verifies percent change calculations when both operands are present (T2, T10). This demonstrates good arithmetic reasoning capability.

3. **Fabricated number detection**: The system correctly flags numbers that don't exist in evidence (T4), showing good grounding capabilities.

4. **Mixed claim handling**: When some claims are correct and others incorrect, the system appropriately flags the answer (T8) based on coverage thresholds.

5. **Scale token normalization**: The system correctly handles scale tokens (million, thousand) and normalizes them for comparison (T5, T6).

### Limitations

1. **Temporal reasoning**: The system fails to detect temporal mismatches (T7). It matches the numeric value "2023" to "2024" in evidence because both contain the year, but doesn't understand that the question asks for 2024 data while the answer provides 2023 data. This is a **limitation due to missing semantic reasoning**.

2. **Scale mismatch detection**: While the system normalizes scale tokens, it doesn't always detect when a scale mismatch indicates an error (T5). The system accepts "5 million" when evidence shows "5000000" because the normalized values match, even though the scale representation differs. This could be improved with better constraint checking.

3. **Ambiguity handling**: The system doesn't penalize ambiguous grounding (T9). When multiple evidence values match a claim, it should reduce confidence, but the current implementation marks it as ambiguous but still accepts it if coverage is high.

4. **Total calculation detection**: The system fails to detect incorrect totals (T3). It doesn't recognize that "total revenue for Q1 and Q2" should be the sum of the two values, leading to an over-conservative FLAG decision when it should be REPAIR.

5. **Execution engine limitations**: The execution engine only works when it can identify computation patterns from keywords. It doesn't attempt to verify totals when the claim doesn't explicitly mention "total" or "sum" keywords.

### Motivation for Enhancements

1. **ML Decision Model**: The current rule-based system has clear limitations:
   - 30% of cases are over-permissive or over-conservative
   - Binary thresholds don't capture nuanced risk signals
   - An ML model trained on signals could learn better decision boundaries

2. **Temporal Constraints**: The system needs temporal reasoning to:
   - Match claims to evidence based on time periods, not just numeric values
   - Detect when answers reference wrong time periods
   - Handle multi-period questions correctly

3. **LLM-based Repair**: When the system identifies REPAIR cases, it should:
   - Use LLM to generate corrected answers based on evidence
   - Preserve correct claims while fixing incorrect ones
   - Maintain natural language flow

4. **Enhanced Execution Engine**: The execution engine should:
   - Better detect implicit computations (totals, averages)
   - Use semantic understanding to identify what needs to be computed
   - Handle more complex financial calculations

5. **Ambiguity Penalty**: The system should:
   - Reduce confidence scores for ambiguous matches
   - Consider ambiguity count in decision logic
   - Provide explanations when ambiguity is detected

## Test Case Details

"""

for i, r in enumerate(results, 1):
    report += f"""
### {r['test_id']}: {r['category']}

**Description**: {r['description']}

**Expected**: {r['expected']}  
**Actual**: {r['actual']}  
**Outcome**: {r['outcome']}

**Rationale**: {r.get('rationale', 'N/A')}

**Key Signals**:
- Coverage ratio: {r['key_signals'].get('coverage_ratio', 0):.1%}
- Unsupported claims: {r['key_signals'].get('unsupported_claims', 0)}
- Recomputation failures: {r['key_signals'].get('recomputation_failures', 0)}
- Scale mismatches: {r['key_signals'].get('scale_mismatches', 0)}
- Period mismatches: {r['key_signals'].get('period_mismatches', 0)}
- Ambiguity count: {r['key_signals'].get('ambiguity_count', 0)}
- Max relative error: {r['key_signals'].get('max_relative_error', 0):.4f}

"""

with open(REPORT_FILE, 'w') as f:
    f.write(report)

print(f"Report generated: {REPORT_FILE}")

