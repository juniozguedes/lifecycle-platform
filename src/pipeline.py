import json
import logging
import random
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BATCH_SIZE = 100
MAX_RETRIES = 5
BASE_DELAY = 1.0
MAX_JITTER = 0.5
FAILED_LOG_PATH = "failed_batches.json"


class MockResponse:
    """Minimal response object returned by ESPClient in local/dev mode."""

    def __init__(self, status_code: int = 200, body: dict | None = None) -> None:
        self.status_code = status_code
        self._body = body or {}

    def json(self) -> dict:
        return self._body


class ESPClient:
    """Stub ESP client — returns mock 200 responses for local development.
    Replace send_batch with a real HTTP call (e.g. via requests) for production."""

    def send_batch(self, campaign_id: str, recipients: list[dict]) -> MockResponse:
        logger.info("ESPClient stub: would send %d recipients for campaign %s", len(recipients), campaign_id)
        return MockResponse(status_code=200, body={"accepted": len(recipients)})


def load_sent_log(sent_log_path: str) -> set[str]:
    path = Path(sent_log_path)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
        return set(data.get("sent_renter_ids", []))
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Invalid sent log file: %s, starting fresh", sent_log_path)
        return set()


def save_sent_log(sent_log_path: str, renter_ids: set[str]) -> None:
    path = Path(sent_log_path)
    data = {"sent_renter_ids": sorted(r for r in renter_ids if r is not None)}
    path.write_text(json.dumps(data, indent=2))


def save_failed_batch(failed_log_path: str, campaign_id: str, batch: list[dict], error: str) -> None:
    path = Path(failed_log_path)
    failed_entry = {
        "campaign_id": campaign_id,
        "recipients": [r.get("renter_id") for r in batch],
        "error": error,
        "timestamp": time.time(),
    }
    existing: list = []
    if path.exists():
        try:
            parsed = json.loads(path.read_text())
            existing = parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            existing = []
    existing.append(failed_entry)
    path.write_text(json.dumps(existing, indent=2))


def create_batches(audience: list[dict], batch_size: int = BATCH_SIZE) -> list[list[dict]]:
    return [audience[i : i + batch_size] for i in range(0, len(audience), batch_size)]


def retry_with_backoff(attempt: int, base_delay: float = BASE_DELAY, max_jitter: float = MAX_JITTER) -> float:
    delay = base_delay * (2**attempt)
    jitter = random.uniform(0, max_jitter)
    return delay + jitter


def send_batch_with_retry(
    campaign_id: str,
    batch: list[dict],
    esp_client: Any,
    max_retries: int = MAX_RETRIES,
) -> tuple[list[dict], bool, str | None]:
    last_error: str | None = None
    for attempt in range(max_retries + 1):
        try:
            response = esp_client.send_batch(campaign_id, batch)
            if response.status_code == 200:
                return [], True, None
            elif response.status_code == 429:
                last_error = "rate_limited"
                delay = retry_with_backoff(attempt)
                logger.warning("Rate limited, retrying in %.2fs (attempt %d/%d)", delay, attempt + 1, max_retries)
                time.sleep(delay)
                continue
            else:
                last_error = f"http_{response.status_code}"
                return batch, False, last_error
        except (ConnectionError, TimeoutError, OSError) as e:
            last_error = str(e)
            if attempt < max_retries:
                delay = retry_with_backoff(attempt)
                logger.warning("Network error: %s, retrying in %.2fs (attempt %d/%d)", e, delay, attempt + 1, max_retries)
                time.sleep(delay)
            else:
                return batch, False, last_error
        except Exception as e:
            # Any other unexpected exception (e.g. serialization, auth) is non-retryable;
            # log and fail the batch so the rest of the campaign can continue.
            last_error = str(e)
            logger.error("Unexpected error sending batch for campaign %s: %s", campaign_id, e)
            return batch, False, last_error
    return batch, False, last_error


def execute_campaign_send(
    campaign_id: str,
    audience: list[dict],
    esp_client: Any,
    sent_log_path: str = "sent_renters.json",
    failed_log_path: str = FAILED_LOG_PATH,
) -> dict[str, Any]:
    start_time = time.time()

    sent_ids = load_sent_log(sent_log_path)
    skipped = [r for r in audience if r.get("renter_id") in sent_ids]
    to_send = [r for r in audience if r.get("renter_id") not in sent_ids]

    logger.info("Campaign %s: %d total, %d skipped (dedup), %d to send", campaign_id, len(audience), len(skipped), len(to_send))

    batches = create_batches(to_send)
    total_sent = 0
    total_failed = 0

    for i, batch in enumerate(batches):
        logger.info("Sending batch %d/%d (%d recipients)", i + 1, len(batches), len(batch))
        failed_batch, success, error_msg = send_batch_with_retry(campaign_id, batch, esp_client)

        if success:
            total_sent += len(batch)
            for r in batch:
                renter_id = r.get("renter_id")
                if renter_id is not None:
                    sent_ids.add(renter_id)
        else:
            total_failed += len(failed_batch)
            save_failed_batch(failed_log_path, campaign_id, failed_batch, error_msg or "unknown_error")
            logger.error("Batch %d failed: %d recipients could not be sent", i + 1, len(failed_batch))

    save_sent_log(sent_log_path, sent_ids)

    elapsed = time.time() - start_time
    result = {
        "total_sent": total_sent,
        "total_failed": total_failed,
        "total_skipped": len(skipped),
        "elapsed_seconds": round(elapsed, 2),
    }
    logger.info("Campaign %s complete: %s", campaign_id, result)
    return result
