"""Tests for pipeline module."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.lifecycle_platform.pipeline import (
    create_batches,
    execute_campaign_send,
    load_sent_log,
    retry_with_backoff,
    save_failed_batch,
    save_sent_log,
)


class TestCreateBatches:
    """Tests for create_batches function."""

    def test_splits_audience_into_batches(self) -> None:
        audience = [{"renter_id": f"renter_{i:03d}"} for i in range(250)]
        batches = create_batches(audience, batch_size=100)
        assert len(batches) == 3
        assert len(batches[0]) == 100
        assert len(batches[1]) == 100
        assert len(batches[2]) == 50

    def test_empty_audience_returns_empty_list(self) -> None:
        batches = create_batches([], batch_size=100)
        assert batches == []

    def test_single_batch(self) -> None:
        audience = [{"renter_id": f"renter_{i:03d}"} for i in range(50)]
        batches = create_batches(audience, batch_size=100)
        assert len(batches) == 1
        assert len(batches[0]) == 50


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    def test_delay_increases_exponentially(self) -> None:
        delays = [retry_with_backoff(i) for i in range(3)]
        assert delays[1] > delays[0]
        assert delays[2] > delays[1]

    def test_delay_is_positive(self) -> None:
        for attempt in range(5):
            delay = retry_with_backoff(attempt)
            assert delay > 0


class TestLoadSentLog:
    """Tests for load_sent_log function."""

    def test_returns_empty_set_when_file_not_exists(self, tmp_path: Path) -> None:
        result = load_sent_log(str(tmp_path / "nonexistent.json"))
        assert result == set()

    def test_returns_sent_ids_from_file(self, tmp_path: Path) -> None:
        sent_log = tmp_path / "sent.json"
        sent_log.write_text(json.dumps({"sent_renter_ids": ["renter_001", "renter_002"]}))
        result = load_sent_log(str(sent_log))
        assert result == {"renter_001", "renter_002"}

    def test_returns_empty_set_on_invalid_json(self, tmp_path: Path) -> None:
        sent_log = tmp_path / "invalid.json"
        sent_log.write_text("not valid json")
        result = load_sent_log(str(sent_log))
        assert result == set()


class TestExecuteCampaignSend:
    """Tests for execute_campaign_send function."""

    def test_skips_already_sent_renters(self, tmp_path: Path) -> None:
        sent_log = tmp_path / "sent.json"
        sent_log.write_text(json.dumps({"sent_renter_ids": ["renter_001", "renter_002"]}))

        audience = [
            {"renter_id": "renter_001"},
            {"renter_id": "renter_002"},
            {"renter_id": "renter_003"},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200

        class MockESP:
            def send_batch(self, campaign_id: str, recipients: list) -> MagicMock:
                return mock_response

        result = execute_campaign_send(
            campaign_id="test_campaign",
            audience=audience,
            esp_client=MockESP(),
            sent_log_path=str(sent_log),
        )

        assert result["total_skipped"] == 2
        assert result["total_sent"] == 1

    def test_sends_all_when_none_previously_sent(self, tmp_path: Path) -> None:
        sent_log = tmp_path / "sent.json"
        audience = [{"renter_id": f"renter_{i:03d}"} for i in range(150)]

        mock_response = MagicMock()
        mock_response.status_code = 200

        class MockESP:
            def send_batch(self, campaign_id: str, recipients: list) -> MagicMock:
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

    def test_handles_rate_limiting_with_retry(self, tmp_path: Path) -> None:
        sent_log = tmp_path / "sent.json"
        audience = [{"renter_id": "renter_001"}]

        call_count = 0

        class MockESP:
            def send_batch(self, campaign_id: str, recipients: list) -> MagicMock:
                nonlocal call_count
                call_count += 1
                response = MagicMock()
                if call_count == 1:
                    response.status_code = 429
                else:
                    response.status_code = 200
                return response

        result = execute_campaign_send(
            campaign_id="test_campaign",
            audience=audience,
            esp_client=MockESP(),
            sent_log_path=str(sent_log),
        )

        assert result["total_sent"] == 1
        assert call_count == 2

    def test_records_failed_batches_on_error(self, tmp_path: Path) -> None:
        sent_log = tmp_path / "sent.json"
        audience = [{"renter_id": "renter_001"}]

        class MockESP:
            def send_batch(self, campaign_id: str, recipients: list) -> MagicMock:
                response = MagicMock()
                response.status_code = 500
                response.json = lambda: {"error": "server_error"}
                return response

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = execute_campaign_send(
                campaign_id="test_campaign",
                audience=audience,
                esp_client=MockESP(),
                sent_log_path=str(sent_log),
            )
        finally:
            os.chdir(original_cwd)

        assert result["total_failed"] == 1
        failed_log = tmp_path / "failed_batches.json"
        assert failed_log.exists()