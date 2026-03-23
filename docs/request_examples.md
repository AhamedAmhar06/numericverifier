# NumericVerifier Request Examples

## Endpoint: POST /verify-only

All examples use `evidence.type = "table"` with a P&L-compatible table.

---

### Example 1: Correct answer (expects ACCEPT)

```json
{
  "question": "What was revenue in 2023?",
  "evidence": {
    "type": "table",
    "content": {
      "columns": ["Line Item", "2022", "2023"],
      "rows": [
        ["Revenue", "500000", "620000"],
        ["COGS", "200000", "250000"],
        ["Gross Profit", "300000", "370000"],
        ["Operating Expenses", "100000", "120000"],
        ["Operating Income", "200000", "250000"],
        ["Net Income", "150000", "190000"]
      ],
      "units": {}
    }
  },
  "candidate_answer": "Revenue in 2023 was 620000.",
  "options": {
    "tolerance": 0.01,
    "log_run": false
  }
}
```

---

### Example 2: Arithmetic error in answer (expects REPAIR or FLAG)

```json
{
  "question": "What was gross profit in 2022?",
  "evidence": {
    "type": "table",
    "content": {
      "columns": ["Line Item", "2022", "2023"],
      "rows": [
        ["Revenue", "500000", "620000"],
        ["Cost of Sales", "200000", "250000"],
        ["Gross Profit", "300000", "370000"],
        ["Operating Expenses", "100000", "120000"],
        ["Operating Income", "200000", "250000"],
        ["Net Income", "150000", "190000"]
      ],
      "units": {}
    }
  },
  "candidate_answer": "Gross profit in 2022 was 350000.",
  "options": {
    "tolerance": 0.01,
    "log_run": false
  }
}
```

---

### Example 3: Period not in evidence (expects FLAG)

```json
{
  "question": "What was net income in 2021?",
  "evidence": {
    "type": "table",
    "content": {
      "columns": ["Line Item", "2022", "2023"],
      "rows": [
        ["Revenue", "500000", "620000"],
        ["COGS", "200000", "250000"],
        ["Gross Profit", "300000", "370000"],
        ["Net Income", "150000", "190000"]
      ],
      "units": {}
    }
  },
  "candidate_answer": "Net income in 2021 was 130000.",
  "options": {
    "tolerance": 0.01,
    "log_run": false
  }
}
```
