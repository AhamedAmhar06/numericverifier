# NumericVerifier – Systematic Evaluation Plan

## Purpose
Systematically evaluate the NumericVerifier baseline to:
- understand its correct behaviours
- identify limitations
- motivate future enhancements (ML decision model, temporal constraints, LLM repair)

This evaluation must NOT modify code.

---

## Evaluation Scope

Test the following categories:

1. Correct numeric answers
2. Arithmetic errors (percent change, totals)
3. Fabricated / unsupported numbers
4. Scale mismatches (e.g. million vs absolute)
5. Temporal mismatches (year / period reasoning)
6. Mixed correct + incorrect claims
7. Ambiguous grounding cases

---

## Evaluation Procedure

For each test case:

1. Provide the exact JSON input for POST /verify-only
2. State the expected decision:
   - ACCEPT
   - REPAIR
   - FLAG
3. Execute the test using the current system
4. Record:
   - actual decision
   - key verifier signals
5. Categorize outcome as:
   - Correct behaviour
   - Over-permissive
   - Over-conservative
   - Limitation due to missing semantic reasoning

---

## Results Table

| Case Type | Expected | Actual | Key Signals | Analysis |
|----------|----------|--------|-------------|----------|
| Correct numeric answers | ACCEPT | ACCEPT | Coverage: 100.0%, Unsupported: 0, Recomp fails: 0, Scale mismatches: 0, Period mismatches: 0, Ambiguity: 0 | Correct behaviour |
| Arithmetic errors - percent change | REPAIR | REPAIR | Coverage: 100.0%, Unsupported: 0, Recomp fails: 1, Scale mismatches: 0, Period mismatches: 0, Ambiguity: 0 | Correct behaviour |
| Arithmetic errors - totals | REPAIR | FLAG | Coverage: 0.0%, Unsupported: 1, Recomp fails: 0, Scale mismatches: 0, Period mismatches: 0, Ambiguity: 0 | Over-conservative |
| Fabricated / unsupported numbers | FLAG | FLAG | Coverage: 0.0%, Unsupported: 1, Recomp fails: 0, Scale mismatches: 0, Period mismatches: 0, Ambiguity: 0 | Correct behaviour |
| Scale mismatches | REPAIR | ACCEPT | Coverage: 100.0%, Unsupported: 0, Recomp fails: 0, Scale mismatches: 0, Period mismatches: 0, Ambiguity: 0 | Over-permissive |
| Scale mismatches | REPAIR | REPAIR | Coverage: 100.0%, Unsupported: 0, Recomp fails: 0, Scale mismatches: 1, Period mismatches: 0, Ambiguity: 0 | Correct behaviour |
| Temporal mismatches | FLAG | ACCEPT | Coverage: 100.0%, Unsupported: 0, Recomp fails: 0, Scale mismatches: 0, Period mismatches: 0, Ambiguity: 1 | Over-permissive |
| Mixed correct + incorrect claims | FLAG | FLAG | Coverage: 66.7%, Unsupported: 1, Recomp fails: 0, Scale mismatches: 0, Period mismatches: 0, Ambiguity: 0 | Correct behaviour |
| Ambiguous grounding cases | FLAG | ACCEPT | Coverage: 100.0%, Unsupported: 0, Recomp fails: 0, Scale mismatches: 0, Period mismatches: 0, Ambiguity: 1 | Over-permissive |
| Correct numeric answers | ACCEPT | ACCEPT | Coverage: 100.0%, Unsupported: 0, Recomp fails: 0, Scale mismatches: 0, Period mismatches: 0, Ambiguity: 0 | Correct behaviour |

---

## Summary Statistics

- **Total test cases**: 10
- **Correct behaviour**: 6 (60%)
- **Over-permissive**: 3 (30%)
- **Over-conservative**: 1 (10%)
- **Limitations**: 0 (0%)

## Analysis

### Strengths

1. **Reliable numeric matching**: The system correctly identifies and matches numeric values from evidence. Coverage calculation works well for straightforward cases where numbers match exactly.

2. **Percent change detection**: The execution engine successfully identifies and verifies percent change calculations when both operands are present. This demonstrates good arithmetic reasoning capability for explicit computations.

3. **Fabricated number detection**: The system correctly flags numbers that don't exist in evidence, showing good grounding capabilities for detecting unsupported claims.

4. **Mixed claim handling**: When some claims are correct and others incorrect, the system appropriately flags the answer based on coverage thresholds, demonstrating reasonable risk assessment.

5. **Scale token normalization**: The system correctly handles scale tokens (million, thousand) and normalizes them for comparison, enabling proper matching across different representations.

### Limitations

1. **Temporal reasoning**: The system fails to detect temporal mismatches. It matches numeric values (like years) without understanding semantic context. For example, it matches "2023" to "2024" in evidence because both contain the year, but doesn't understand that the question asks for 2024 data while the answer provides 2023 data. This is a **limitation due to missing semantic reasoning**.

2. **Scale mismatch detection**: While the system normalizes scale tokens, it doesn't always detect when a scale mismatch indicates an error. The system accepts "5 million" when evidence shows "5000000" because the normalized values match, even though the scale representation differs. This could be improved with better constraint checking that considers representation consistency.

3. **Ambiguity handling**: The system doesn't penalize ambiguous grounding sufficiently. When multiple evidence values match a claim, it should reduce confidence, but the current implementation marks it as ambiguous but still accepts it if coverage is high. The ambiguity count is tracked but doesn't strongly influence the decision.

4. **Total calculation detection**: The system fails to detect incorrect totals when the computation isn't explicitly mentioned. It doesn't recognize that "total revenue for Q1 and Q2" should be the sum of the two values, leading to an over-conservative FLAG decision when it should be REPAIR. The execution engine only works when it can identify computation patterns from keywords.

5. **Execution engine limitations**: The execution engine only works when it can identify computation patterns from keywords. It doesn't attempt to verify totals when the claim doesn't explicitly mention "total" or "sum" keywords, limiting its ability to catch arithmetic errors.

### Motivation for Enhancements

1. **ML Decision Model**: The current rule-based system has clear limitations:
   - 30% of cases are over-permissive or over-conservative
   - Binary thresholds don't capture nuanced risk signals
   - An ML model trained on signals could learn better decision boundaries that consider multiple factors simultaneously
   - The signals.csv dataset provides a foundation for training such a model

2. **Temporal Constraints**: The system needs temporal reasoning to:
   - Match claims to evidence based on time periods, not just numeric values
   - Detect when answers reference wrong time periods
   - Handle multi-period questions correctly
   - This requires semantic understanding beyond numeric matching

3. **LLM-based Repair**: When the system identifies REPAIR cases, it should:
   - Use LLM to generate corrected answers based on evidence
   - Preserve correct claims while fixing incorrect ones
   - Maintain natural language flow
   - This would transform the system from detection-only to correction-capable

4. **Enhanced Execution Engine**: The execution engine should:
   - Better detect implicit computations (totals, averages)
   - Use semantic understanding to identify what needs to be computed
   - Handle more complex financial calculations
   - Consider question context when determining what to verify

5. **Ambiguity Penalty**: The system should:
   - Reduce confidence scores for ambiguous matches
   - Consider ambiguity count more strongly in decision logic
   - Provide explanations when ambiguity is detected
   - This would make the system more conservative when evidence is unclear

---

## Constraints

- Do NOT modify the code
- Do NOT add new logic
- Do NOT change thresholds
- Focus only on evaluation and analysis
