# TAT-QA P&L Filter

## Filter Rules

- answer_from in {table, table-text}
- answer_type in {span, arithmetic}
- gold answer parseable as numeric
- Period columns: >= 2 headers match 20XX, FYXX, Q1-Q4
- Row labels: >= 3 distinct P&L keywords (revenue, cogs, gross profit, etc.)
- Numeric density: >= 60% of period-column cells parse as numbers

## Counts

- Total questions processed: 594
- Kept (P&L): 354
- Dropped: 240

- Train: 247, Dev: 53, Test: 54
