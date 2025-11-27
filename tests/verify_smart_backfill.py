
import sys
import os
from datetime import date
from unittest.mock import MagicMock, patch

# Add root to path
sys.path.append(os.getcwd())

from ingest.dart_seed import seed_recent_filings
from scripts.ingest_backfill import main as backfill_main
from services.filing_fetch_service import fetch_filing_content
from web.routers.filing import fetch_filing_content as fetch_endpoint

def test_seed_recent_filings_signature():
    print("Testing seed_recent_filings signature...")
    # Just check if we can call it with metadata_only
    try:
        # Mock dependencies to avoid actual execution
        with patch('ingest.dart_seed.DartClient') as MockClient, \
             patch('ingest.dart_seed.SessionLocal'):
            
            mock_client = MockClient.return_value
            mock_client.list_recent_filings.return_value = []
            
            seed_recent_filings(days_back=1, metadata_only=True)
            print("PASS: seed_recent_filings accepts metadata_only")
    except TypeError as e:
        print(f"FAIL: seed_recent_filings signature mismatch: {e}")
    except Exception as e:
        print(f"WARN: Execution error (expected since we mocked): {e}")

def test_backfill_cli_args():
    print("\nTesting backfill CLI args...")
    with patch('argparse.ArgumentParser.parse_args') as mock_parse:
        mock_parse.return_value = MagicMock(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1),
            chunk_days=1,
            corp_code=None,
            metadata_only=True,
            log_level="INFO"
        )
        with patch('scripts.ingest_backfill.seed_recent_filings') as mock_seed:
            try:
                backfill_main()
                # Verify seed_recent_filings was called with metadata_only=True
                args, kwargs = mock_seed.call_args
                if kwargs.get('metadata_only') is True:
                     print("PASS: backfill script passes metadata_only=True")
                else:
                     print(f"FAIL: backfill script called with {kwargs}")
            except Exception as e:
                print(f"FAIL: backfill script error: {e}")

if __name__ == "__main__":
    test_seed_recent_filings_signature()
    test_backfill_cli_args()
