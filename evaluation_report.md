# NumericVerifier – Evaluation Results

## Results Table

| Case Type | Expected | Actual | Key Signals | Analysis |
|-----------|----------|--------|-------------|----------|
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

## Summary Statistics

- **Total test cases**: 10
- **Correct behaviour**: 6 (60%)
- **Over-permissive**: 3 (30%)
- **Over-conservative**: 1 (10%)
- **Limitations**: 0 (0%)

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


### T1: Correct numeric answers

**Description**: Simple correct answer matching evidence exactly

**Expected**: ACCEPT  
**Actual**: ACCEPT  
**Outcome**: Correct behaviour

**Rationale**: All claims are grounded and verified. No scale or period mismatches. All recomputations successful. Coverage meets threshold.

**Key Signals**:
- Coverage ratio: 100.0%
- Unsupported claims: 0
- Recomputation failures: 0
- Scale mismatches: 0
- Period mismatches: 0
- Ambiguity count: 0
- Max relative error: 0.0000


### T2: Arithmetic errors - percent change

**Description**: Incorrect percent change calculation

**Expected**: REPAIR  
**Actual**: REPAIR  
**Outcome**: Correct behaviour

**Rationale**: Good evidence coverage (100.0%), but issues detected: recomputation failures. Errors appear correctable.

**Key Signals**:
- Coverage ratio: 100.0%
- Unsupported claims: 0
- Recomputation failures: 1
- Scale mismatches: 0
- Period mismatches: 0
- Ambiguity count: 0
- Max relative error: 0.0000


### T3: Arithmetic errors - totals

**Description**: Incorrect total calculation

**Expected**: REPAIR  
**Actual**: FLAG  
**Outcome**: Over-conservative

**Rationale**: Issues detected: low coverage (0.0%), many unsupported claims (1). Requires review.

**Key Signals**:
- Coverage ratio: 0.0%
- Unsupported claims: 1
- Recomputation failures: 0
- Scale mismatches: 0
- Period mismatches: 0
- Ambiguity count: 0
- Max relative error: 0.0000


### T4: Fabricated / unsupported numbers

**Description**: Number not present in evidence

**Expected**: FLAG  
**Actual**: FLAG  
**Outcome**: Correct behaviour

**Rationale**: Issues detected: low coverage (0.0%), many unsupported claims (1). Requires review.

**Key Signals**:
- Coverage ratio: 0.0%
- Unsupported claims: 1
- Recomputation failures: 0
- Scale mismatches: 0
- Period mismatches: 0
- Ambiguity count: 0
- Max relative error: 0.0000


### T5: Scale mismatches

**Description**: Million vs absolute value mismatch

**Expected**: REPAIR  
**Actual**: ACCEPT  
**Outcome**: Over-permissive

**Rationale**: All claims are grounded and verified. No scale or period mismatches. All recomputations successful. Coverage meets threshold.

**Key Signals**:
- Coverage ratio: 100.0%
- Unsupported claims: 0
- Recomputation failures: 0
- Scale mismatches: 0
- Period mismatches: 0
- Ambiguity count: 0
- Max relative error: 0.0000


### T6: Scale mismatches

**Description**: Incorrect scale (million vs thousand)

**Expected**: REPAIR  
**Actual**: REPAIR  
**Outcome**: Correct behaviour

**Rationale**: Good evidence coverage (100.0%), but issues detected: scale mismatches. Errors appear correctable.

**Key Signals**:
- Coverage ratio: 100.0%
- Unsupported claims: 0
- Recomputation failures: 0
- Scale mismatches: 1
- Period mismatches: 0
- Ambiguity count: 0
- Max relative error: 0.0000


### T7: Temporal mismatches

**Description**: Wrong year in answer

**Expected**: FLAG  
**Actual**: ACCEPT  
**Outcome**: Over-permissive

**Rationale**: All claims are grounded and verified. No scale or period mismatches. All recomputations successful. Coverage meets threshold.

**Key Signals**:
- Coverage ratio: 100.0%
- Unsupported claims: 0
- Recomputation failures: 0
- Scale mismatches: 0
- Period mismatches: 0
- Ambiguity count: 1
- Max relative error: 0.0000


### T8: Mixed correct + incorrect claims

**Description**: Some correct, some incorrect numbers

**Expected**: FLAG  
**Actual**: FLAG  
**Outcome**: Correct behaviour

**Rationale**: Issues detected: low coverage (66.7%), many unsupported claims (1). Requires review.

**Key Signals**:
- Coverage ratio: 66.7%
- Unsupported claims: 1
- Recomputation failures: 0
- Scale mismatches: 0
- Period mismatches: 0
- Ambiguity count: 0
- Max relative error: 0.0000


### T9: Ambiguous grounding cases

**Description**: Multiple matching evidence values

**Expected**: FLAG  
**Actual**: ACCEPT  
**Outcome**: Over-permissive

**Rationale**: All claims are grounded and verified. No scale or period mismatches. All recomputations successful. Coverage meets threshold.

**Key Signals**:
- Coverage ratio: 100.0%
- Unsupported claims: 0
- Recomputation failures: 0
- Scale mismatches: 0
- Period mismatches: 0
- Ambiguity count: 1
- Max relative error: 0.0000


### T10: Correct numeric answers

**Description**: Percent change correctly calculated

**Expected**: ACCEPT  
**Actual**: ACCEPT  
**Outcome**: Correct behaviour

**Rationale**: All claims are grounded and verified. No scale or period mismatches. All recomputations successful. Coverage meets threshold.

**Key Signals**:
- Coverage ratio: 100.0%
- Unsupported claims: 0
- Recomputation failures: 0
- Scale mismatches: 0
- Period mismatches: 0
- Ambiguity count: 0
- Max relative error: 0.0000

