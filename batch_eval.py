import json
import requests
import time

CASES_FILE = "evaluation_cases.json"
RESULTS_FILE = "evaluation_results.json"
URL = "http://localhost:8000/verify-only"


def load_cases(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    cases = load_cases(CASES_FILE)
    results = []

    total = len(cases)
    for i, case in enumerate(cases, start=1):
        print(f"Running case {i}/{total}...")
        # Convert evidence to API expected shape: evidence.content should be a dict
        evidence = case.get("evidence", {}) or {}
        ev_type = evidence.get("type")
        ev_content = evidence.get("data") if evidence.get("data") is not None else evidence.get("content")

        if ev_type == "table" and isinstance(ev_content, list):
            # build columns and rows
            columns = ["Line Item", "2023", "2024"]
            rows = []
            for r in ev_content:
                # ensure numeric values become strings as in API examples
                rows.append([r.get("line_item"), str(r.get("2023")), str(r.get("2024"))])
            content = {"columns": columns, "rows": rows, "units": {}}
        else:
            content = ev_content

        payload = {
            "question": case.get("question"),
            "evidence": {"type": ev_type, "content": content},
            "candidate_answer": case.get("candidate_answer"),
        }

        try:
            resp = requests.post(URL, json=payload, timeout=30)
            try:
                data = resp.json()
            except ValueError:
                data = {"error": "invalid_json_response", "status_code": resp.status_code, "text": resp.text}
            results.append({"case_id": case.get("id"), "status_code": resp.status_code, "response": data})
        except Exception as e:
            results.append({"case_id": case.get("id"), "error": str(e)})

        # brief pause to avoid overwhelming local server
        time.sleep(0.1)

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Saved results to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
