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


def load_sent_log(sent_log_path: str) -> set[str]:
    path = Path(sent_log_path)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
        return set(data.get("sent_renter_ids", []))
    except (json.JSONDecodeError, KeyError):
        logger.warning(f"Invalid sent log file: {sent_log_path}, starting fresh")
        return set()


def save_sent_log(sent_log_path: str, renter_ids: set[str]) -> None:
    path = Path(sent_log_path)
    data = {"sent_renter_ids": sorted(renter_ids)}
    path.write_text(json.dumps(data, indent=2))


def save_failed_batch(failed_log_path: str, campaign_id: str, batch: list[dict], error: str) -> None:
    path = Path(failed_log_path)
    failed_entry = {
        "campaign_id": campaign_id,
        "recipients": [r.get("renter_id") for r in batch],
        "error": error,
        "timestamp": time.time(),
    }
    existing = []
    if path.exists():
        try:
            existing = json.loads(path.read_text())
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
) -> tuple[list[dict], bool]:
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = esp_client.send_batch(campaign_id, batch)
            if response.status_code == 200:
                return [], True
            elif response.status_code == 429:
                last_error = "rate_limited"
                delay = retry_with_backoff(attempt)
                logger.warning(f"Rate limited, retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            else:
                last_error = f"http_{response.status_code}"
                return batch, False
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                delay = retry_with_backoff(attempt)
                logger.warning(f"Error: {e}, retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                return batch, False
    return batch, False


def execute_campaign_send(
    campaign_id: str,
    audience: list[dict],
    esp_client: Any,
    sent_log_path: str = "sent_renters.json",
) -> dict:
    start_time = time.time()
    failed_log_path = "failed_batches.json"

    sent_ids = load_sent_log(sent_log_path)
    skipped = [r for r in audience if r.get("renter_id") in sent_ids]
    to_send = [r for r in audience if r.get("renter_id") not in sent_ids]

    logger.info(f"Campaign {campaign_id}: {len(audience)} total, {len(skipped)} skipped (dedup), {len(to_send)} to send")

    batches = create_batches(to_send)
    total_sent = 0
    total_failed = 0

    for i, batch in enumerate(batches):
        logger.info(f"Sending batch {i + 1}/{len(batches)} ({len(batch)} recipients)")
        failed_batch, success = send_batch_with_retry(campaign_id, batch, esp_client)

        if success:
            total_sent += len(batch)
            for r in batch:
                sent_ids.add(r.get("renter_id"))
        else:
            total_failed += len(failed_batch)
            save_failed_batch(failed_log_path, campaign_id, failed_batch, last_error if 'last_error' in locals() else "unknown")
            logger.error(f"Batch {i + 1} failed: {len(failed_batch)} recipients could not be sent")

    save_sent_log(sent_log_path, sent_ids)

    elapsed = time.time() - start_time
    result = {
        "total_sent": total_sent,
        "total_failed": total_failed,
        "total_skipped": len(skipped),
        "elapsed_seconds": round(elapsed, 2),
    }
    logger.info(f"Campaign {campaign_id} complete: {result}")
    return result