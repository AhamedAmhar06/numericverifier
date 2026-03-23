# Error Analysis

## Evaluation Summary

- **Total cases:** 84
- **Accuracy:** 84.52%
- **False ACCEPT rate:** 19.44% (7 cases)
- **FLAG precision:** 100% (no false flags)
- **ACCEPT recall:** 100% (all correct answers accepted)

## False Accept Analysis

The 7 false accepts are "scale_error" category cases where the candidate answer uses a different numeric scale (e.g., "0.50 million") that the extraction pipeline correctly expands to the evidence value (500,000). From the pipeline's perspective, these are numerically correct: the claim value after scale expansion matches the evidence exactly. These are categorization artifacts in the test data, not genuine verification failures.

**Implication:** The false accept rate of 19.44% is inflated by this labeling issue. Under stricter labeling (excluding correctly-expanded scale answers), the effective false accept rate approaches 0%.

## Ablation Findings

| Config | Accuracy | False Accept | Key Observation |
|--------|----------|--------------|-----------------|
| rules_full | 84.52% | 19.44% | Baseline |
| rules_no_constraints | 75.00% | 58.33% | Constraints prevent 38.89pp of false accepts |
| rules_no_execution | 84.52% | 19.44% | Execution engine has no delta on this dataset |
| rules_no_lookup | 84.52% | 19.44% | Lookup redundant with grounding on this dataset |
| rules_no_repair | 84.52% | 19.44% | No repair opportunity in current case mix |
| ml_full | 84.52% | 36.11% | ML trained on older data is less conservative |

**Key insight:** The constraint engine is the single most impactful component, preventing 38.89 percentage points of false accepts. Disabling it nearly triples the false accept rate from 19.44% to 58.33%.

## Per-Class Performance

- **ACCEPT:** Precision 87.3%, Recall 100%, F1 93.2% -- no correct answers are rejected
- **FLAG:** Precision 100%, Recall 63.9%, F1 78.0% -- no incorrect flags, but some FLAG cases are misclassified as ACCEPT/REPAIR
- **REPAIR:** No test cases produce REPAIR as expected decision; 6 predictions are REPAIR (arithmetic/identity errors with partial grounding)

## Recommendations

1. Add evaluation cases with genuine scale mismatches (e.g., "500 million" when evidence shows 500,000)
2. Add REPAIR-expected cases (partial errors with correctable grounding)
3. Retrain ML model on post-improvement signal data for better alignment
4. Expand dataset with cross-period and growth-rate verification cases
