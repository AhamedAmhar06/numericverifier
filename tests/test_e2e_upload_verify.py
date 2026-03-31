"""E2E tests: upload CSV → verify → check decision. Uses live server on port 8000."""
import pytest
import requests
import json

BASE = "http://localhost:8000"

@pytest.fixture(scope="module")
def apple_table():
    """Upload Apple FY2023 CSV and return parsed table content."""
    import io
    csv_content = """Line Item,FY2023 (in millions),FY2022 (in millions)
Net Sales,383285,394328
Cost of Sales,214137,223546
Gross Profit,169148,170782
Research and Development,29915,26251
Selling General and Administrative,24932,25094
Operating Expenses,54847,51345
Operating Income,114301,119437
Other Income Net,565,2825
Income Before Provision,114866,122263
Provision for Income Taxes,29749,19300
Net Income,96995,99803"""
    f = io.BytesIO(csv_content.encode())
    r = requests.post(f"{BASE}/upload-table", files={"file": ("apple_fy2023.csv", f, "text/csv")})
    r.raise_for_status()
    data = r.json()
    # Backend returns {"type": "table", "content": {...}}
    # Return the full object so it can be used directly as evidence
    if 'content' in data: return data['content']
    if 'table' in data: return data['table']
    return data

@pytest.fixture(scope="module")
def msft_table():
    """Upload Microsoft FY2023 CSV and return parsed table content."""
    import io
    csv_content = """Line Item,FY2023 (in millions),FY2022 (in millions)
Revenue,211915,198270
Cost of Revenue,65863,62650
Gross Profit,146052,135620
Research and Development,27195,24512
Sales and Marketing,22759,21825
General and Administrative,7575,5900
Operating Expenses,57529,52237
Operating Income,88523,83383
Other Income Net,1649,333
Income Before Tax,90172,83716
Provision for Income Taxes,16950,10978
Net Income,72361,72738"""
    f = io.BytesIO(csv_content.encode())
    r = requests.post(f"{BASE}/upload-table", files={"file": ("msft_fy2023.csv", f, "text/csv")})
    r.raise_for_status()
    data = r.json()
    if 'content' in data: return data['content']
    if 'table' in data: return data['table']
    return data

def verify_only(question, table_content, candidate_answer):
    payload = {
        "question": question,
        "evidence": {"type": "table", "content": table_content},
        "candidate_answer": candidate_answer,
        "options": {}
    }
    r = requests.post(f"{BASE}/verify-only", json=payload)
    r.raise_for_status()
    return r.json()

def test_e2e_apple_correct_millions(apple_table):
    """TC-E2E-1: Apple upload + correct millions answer → ACCEPT."""
    r = verify_only(
        "What were Apple's net sales in FY2023?",
        apple_table,
        "Apple's net sales in FY2023 were $383,285 million."
    )
    assert r['decision'] == 'ACCEPT', f"Expected ACCEPT, got {r['decision']}"

def test_e2e_apple_correct_billions(apple_table):
    """TC-E2E-2: Apple upload + correct billions phrasing → ACCEPT (constraint fix)."""
    r = verify_only(
        "What were Apple's net sales in FY2023?",
        apple_table,
        "Apple's net sales in FY2023 were $383.285 billion."
    )
    assert r['decision'] == 'ACCEPT', f"Expected ACCEPT, got {r['decision']}"

def test_e2e_apple_hallucinated_value(apple_table):
    """TC-E2E-3: Apple upload + hallucinated net income → FLAG."""
    r = verify_only(
        "What was Apple's net income in FY2023?",
        apple_table,
        "Apple's net income in FY2023 was $150,000 million."
    )
    assert r['decision'] in ('FLAG', 'REPAIR'), f"Expected FLAG/REPAIR, got {r['decision']}"

def test_e2e_apple_arithmetic_error(apple_table):
    """TC-E2E-4: Apple upload + wrong gross profit → FLAG."""
    r = verify_only(
        "What was Apple's gross profit in FY2023?",
        apple_table,
        "Apple's gross profit in FY2023 was $175,000 million."
    )
    assert r['decision'] in ('FLAG', 'REPAIR'), f"Expected FLAG/REPAIR, got {r['decision']}"

def test_e2e_msft_correct_revenue(msft_table):
    """TC-E2E-5: Microsoft upload + correct revenue → ACCEPT."""
    r = verify_only(
        "What was Microsoft's revenue in FY2023?",
        msft_table,
        "Microsoft's revenue in FY2023 was $211,915 million."
    )
    assert r['decision'] == 'ACCEPT', f"Expected ACCEPT, got {r['decision']}"

def test_e2e_msft_wrong_net_income(msft_table):
    """TC-E2E-6: Microsoft upload + wrong net income → FLAG."""
    r = verify_only(
        "What was Microsoft's net income in FY2023?",
        msft_table,
        "Microsoft's net income in FY2023 was $50,000 million."
    )
    assert r['decision'] in ('FLAG', 'REPAIR'), f"Expected FLAG/REPAIR, got {r['decision']}"

def test_e2e_upload_table_returns_parseable_structure():
    """TC-E2E-7: /upload-table returns valid JSON with table data."""
    import io
    csv_content = "A,B\n1,2\n3,4\n"
    f = io.BytesIO(csv_content.encode())
    r = requests.post(f"{BASE}/upload-table", files={"file": ("test.csv", f, "text/csv")})
    assert r.status_code == 200
    data = r.json()
    # Should have some key with table data
    assert isinstance(data, dict), "Response should be a dict"
    # Backend returns {"type": "table", "content": {...}}
    assert "type" in data or "content" in data or "table" in data, \
        f"Expected 'type', 'content', or 'table' key in response, got: {list(data.keys())}"
