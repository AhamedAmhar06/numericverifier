#!/usr/bin/env python3
"""Run systematic evaluation of NumericVerifier."""
import json
import httpx
import time
import sys
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8877"
TEST_CASES_FILE = Path(__file__).parent / "evaluation_test_cases.json"
RESULTS_FILE = Path(__file__).parent / "evaluation_results.json"

def check_server():
    """Check if server is running."""
    try:
        with httpx.Client(timeout=2.0) as client:
            response = client.get(f"{BASE_URL}/health")
            return response.status_code == 200
    except:
        return False

def run_test_case(test_case):
    """Run a single test case and return results."""
    test_id = test_case["id"]
    category = test_case["category"]
    expected = test_case["expected"]
    input_data = test_case["input"]
    
    print(f"\n[{test_id}] {category}")
    print(f"  Expected: {expected}")
    print(f"  Description: {test_case['description']}")
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{BASE_URL}/verify-only",
                json=input_data
            )
            response.raise_for_status()
            result = response.json()
        
        actual = result["decision"]
        signals = result["signals"]
        
        # Extract key signals
        key_signals = {
            "coverage_ratio": signals["coverage_ratio"],
            "unsupported_claims": signals["unsupported_claims_count"],
            "recomputation_failures": signals["recomputation_fail_count"],
            "scale_mismatches": signals["scale_mismatch_count"],
            "period_mismatches": signals["period_mismatch_count"],
            "ambiguity_count": signals["ambiguity_count"],
            "max_relative_error": signals["max_relative_error"]
        }
        
        # Determine outcome category
        if actual == expected:
            outcome = "Correct behaviour"
        elif actual == "ACCEPT" and expected in ["REPAIR", "FLAG"]:
            outcome = "Over-permissive"
        elif actual in ["REPAIR", "FLAG"] and expected == "ACCEPT":
            outcome = "Over-conservative"
        else:
            # Wrong decision type but not clearly permissive/conservative
            if actual == "FLAG" and expected == "REPAIR":
                outcome = "Over-conservative"
            elif actual == "REPAIR" and expected == "FLAG":
                outcome = "Over-permissive"
            else:
                outcome = "Limitation due to missing semantic reasoning"
        
        print(f"  Actual: {actual}")
        print(f"  Outcome: {outcome}")
        print(f"  Coverage: {key_signals['coverage_ratio']:.1%}, Unsupported: {key_signals['unsupported_claims']}")
        
        return {
            "test_id": test_id,
            "category": category,
            "description": test_case["description"],
            "expected": expected,
            "actual": actual,
            "key_signals": key_signals,
            "outcome": outcome,
            "rationale": result["rationale"],
            "claims_count": len(result["claims"])
        }
        
    except Exception as e:
        print(f"  ERROR: {e}")
        return {
            "test_id": test_id,
            "category": category,
            "description": test_case["description"],
            "expected": expected,
            "actual": "ERROR",
            "key_signals": {},
            "outcome": "Error",
            "error": str(e)
        }

def main():
    """Main evaluation runner."""
    print("=" * 60)
    print("NumericVerifier Systematic Evaluation")
    print("=" * 60)
    
    # Check server
    print("\nChecking server...")
    if not check_server():
        print(f"ERROR: Server not running at {BASE_URL}")
        print("Please start the server with:")
        print("  cd backend && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8877")
        sys.exit(1)
    print("Server is running ✓")
    
    # Load test cases
    print(f"\nLoading test cases from {TEST_CASES_FILE}...")
    with open(TEST_CASES_FILE, 'r') as f:
        data = json.load(f)
    test_cases = data["test_cases"]
    print(f"Loaded {len(test_cases)} test cases")
    
    # Run all test cases
    results = []
    for test_case in test_cases:
        result = run_test_case(test_case)
        results.append(result)
        time.sleep(0.5)  # Small delay between requests
    
    # Save results
    print(f"\n\nSaving results to {RESULTS_FILE}...")
    with open(RESULTS_FILE, 'w') as f:
        json.dump({"results": results}, f, indent=2)
    
    # Summary
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    
    correct = sum(1 for r in results if r["outcome"] == "Correct behaviour")
    over_permissive = sum(1 for r in results if r["outcome"] == "Over-permissive")
    over_conservative = sum(1 for r in results if r["outcome"] == "Over-conservative")
    limitations = sum(1 for r in results if "Limitation" in r["outcome"])
    errors = sum(1 for r in results if r["outcome"] == "Error")
    
    print(f"\nTotal test cases: {len(results)}")
    print(f"  Correct behaviour: {correct}")
    print(f"  Over-permissive: {over_permissive}")
    print(f"  Over-conservative: {over_conservative}")
    print(f"  Limitations: {limitations}")
    print(f"  Errors: {errors}")
    
    print(f"\nResults saved to: {RESULTS_FILE}")
    print("\nNext step: Generate results table and analysis")

if __name__ == "__main__":
    main()
