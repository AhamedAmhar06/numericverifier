"""Test the example cases."""
import json
import sys
from pathlib import Path
from app.api.verify import VerifyRequest, EvidenceRequest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_example(file_path: str):
    """Test an example file."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    request = VerifyRequest(**data)
    
    # Import and call the verify function
    from app.api.verify import verify_only
    import asyncio
    
    result = asyncio.run(verify_only(request))
    
    print(f"\n=== Testing {Path(file_path).name} ===")
    print(f"Decision: {result['decision']}")
    print(f"Rationale: {result['rationale'][:100]}...")
    print(f"Claims found: {len(result['claims'])}")
    print(f"Signals: coverage={result['signals']['coverage_ratio']:.2%}, unsupported={result['signals']['unsupported_claims_count']}")
    return result

if __name__ == "__main__":
    examples_dir = Path(__file__).parent.parent / "examples"
    
    for example_file in ["accept_case.json", "repair_case.json", "flag_case.json"]:
        file_path = examples_dir / example_file
        if file_path.exists():
            try:
                test_example(str(file_path))
            except Exception as e:
                print(f"Error testing {example_file}: {e}")
                import traceback
                traceback.print_exc()

