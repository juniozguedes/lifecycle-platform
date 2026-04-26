import logging
from unittest.mock import MagicMock

from src.lifecycle_platform.pipeline import (
    create_batches,
    execute_campaign_send,
    load_sent_log,
    retry_with_backoff,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def test_create_batches():
    audience = [{"renter_id": f"renter_{i:03d}"} for i in range(250)]
    batches = create_batches(audience, batch_size=100)
    assert len(batches) == 3
    assert len(batches[0]) == 100
    assert len(batches[1]) == 100
    assert len(batches[2]) == 50
    print("✓ create_batches works")


def test_retry_with_backoff():
    for attempt in range(3):
        delay = retry_with_backoff(attempt)
        assert delay > 0
        print(f"  attempt {attempt}: delay = {delay:.2f}s")
    print("✓ retry_with_backoff works")


def test_deduplication(tmp_path):
    import json
    
    sent_log = tmp_path / "sent.json"
    sent_log.write_text('{"sent_renter_ids": ["renter_001", "renter_002"]}')
    
    audience = [
        {"renter_id": "renter_001"},  # already sent
        {"renter_id": "renter_002"},  # already sent
        {"renter_id": "renter_003"},  # new
    ]
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    class MockESP:
        def send_batch(self, campaign_id, recipients):
            return mock_response
    
    result = execute_campaign_send(
        campaign_id="test_campaign",
        audience=audience,
        esp_client=MockESP(),
        sent_log_path=str(sent_log),
    )
    
    assert result["total_skipped"] == 2
    assert result["total_sent"] == 1
    print("✓ deduplication works")


def test_all_successful(tmp_path):
    sent_log = tmp_path / "sent.json"
    
    audience = [{"renter_id": f"renter_{i:03d}"} for i in range(150)]
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    class MockESP:
        def send_batch(self, campaign_id, recipients):
            return mock_response
    
    result = execute_campaign_send(
        campaign_id="test_campaign",
        audience=audience,
        esp_client=MockESP(),
        sent_log_path=str(sent_log),
    )
    
    assert result["total_sent"] == 150
    assert result["total_failed"] == 0
    assert result["total_skipped"] == 0
    print("✓ all successful works")


if __name__ == "__main__":
    import tempfile
    test_create_batches()
    test_retry_with_backoff()
    with tempfile.TemporaryDirectory() as tmp:
        import os
        os.chdir(tmp)
        test_deduplication(tmp_path=tempfile.TemporaryDirectory())
        test_all_successful(tmp_path=tempfile.TemporaryDirectory())