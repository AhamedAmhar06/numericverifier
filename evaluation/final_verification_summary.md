# NumericVerifier — Research-Grade Verification Benchmark

## Combined Summary

| Candidate Type | Total | ACCEPT | REPAIR | FLAG | Accept% | Detect% |
|---|---|---|---|---|---|---|
| Correct (gold) | 54 | 23 | 1 | 30 | 42.6% | -- |
| arithmetic_error | 54 | 9 | 0 | 45 | 16.7% | 83.3% |
| percentage_error | 54 | 16 | 0 | 38 | 29.6% | 70.4% |
| scale_error | 54 | 2 | 0 | 52 | 3.7% | 96.3% |
| period_error | 54 | 22 | 0 | 32 | 40.7% | 59.3% |
| near_miss_error | 54 | 20 | 0 | 34 | 37.0% | 63.0% |
| **All errors** | 270 | 69 | 0 | 201 | 25.6% | 74.4% |

## Key Verification Quality Metrics

| Metric | Value |
|---|---|
| Correct Accept Rate (gold) | 42.59% |
| False Accept Rate (errors) | 25.56% |
| Error Detection Rate | 74.44% |
| Repair Success Rate | 0.00% |
| Grounding Coverage (gold) | 33.33% |
| Execution Coverage (gold) | 24.07% |
| Avg Latency (gold) | 933.52ms |
| Avg Latency (errors) | 881.18ms |
