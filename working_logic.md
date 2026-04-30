# Working Logic - Audience Segmentation

This document explains why only 2 renters (renter_001, renter_002) qualified for the SMS reactivation campaign based on the 8 criteria defined in the challenge.

---

## Query Results

| renter_id | email | phone | last_login | search_count | days_since_login |
|----------|-------|-------|-----------|-------------|------------------|
| renter_002 | bob@example.com | +1555123002 | 2026-03-15 | 3 | 46 days |
| renter_001 | alice@example.com | +1555123001 | 2026-03-25 | 5 | 36 days |

**Total eligible: 2 renters**

---

## Why These Renters Qualified

### renter_001 (alice@example.com)

| Criterion | Requirement | Status | Reason |
|-----------|-------------|--------|--------|
| 1 | Last login > 30 days ago | ✓ | Last login: 36 days ago |
| 2 | subscription_status = 'churned' | ✓ | status: 'churned' |
| 3 | At least 3 searches (90 days) | ✓ | 5 searches |
| 4 | Has phone number | ✓ | phone: +1555123001 |
| 5 | sms_consent = TRUE | ✓ | sms_consent: TRUE |
| 6 | NOT in suppression list | ✓ | Not suppressed |
| 7 | dnd_until NULL or in past | ✓ | dnd_until: NULL |
| 8 | Idempotent query | ✓ | Anchors date math to CURRENT_DATE() |

### renter_002 (bob@example.com)

| Criterion | Requirement | Status | Reason |
|-----------|-------------|--------|--------|
| 1 | Last login > 30 days ago | ✓ | Last login: 46 days ago |
| 2 | subscription_status = 'churned' | ✓ | status: 'churned' |
| 3 | At least 3 searches (90 days) | ✓ | 3 searches (exactly threshold) |
| 4 | Has phone number | ✓ | phone: +1555123002 |
| 5 | sms_consent = TRUE | ✓ | sms_consent: TRUE |
| 6 | NOT in suppression list | ✓ | Not suppressed |
| 7 | dnd_until NULL or in past | ✓ | dnd_until: NULL |
| 8 | Idempotent query | ✓ | Anchors date math to CURRENT_DATE() |

---

## Why Other Renters Did NOT Qualify

### renter_003 (carol@example.com)
- **Excluded by**: Criterion #3 (search count) AND Criterion #6 (suppression)
- **Reason**: Only 2 searches (< 3 required), AND suppressed (reason: unsubscribed)

### renter_004 (dave@example.com)
- **Excluded by**: Criterion #5 (sms_consent)
- **Reason**: sms_consent = FALSE (opted out of SMS)

### renter_005 (eve@example.com)
- **Excluded by**: Criterion #4 (phone number)
- **Reason**: phone = NULL (no phone number on file)

### renter_006 (frank@example.com)
- **Excluded by**: Criterion #2 (subscription_status)
- **Reason**: subscription_status = 'active' (not churned)

### renter_007 (grace@example.com)
- **Excluded by**: Criterion #7 (DND)
- **Reason**: dnd_until is in the future (10 days from now)

### renter_008 (henry@example.com)
- **Excluded by**: Criterion #6 (suppression)
- **Reason**: Suppressed (reason: bounced)

### renter_009 (iris@example.com)
- **Excluded by**: Criterion #1 (last login)
- **Reason**: Last login only 15 days ago (< 30 days threshold)

### renter_010 (jack@example.com)
- **Excluded by**: Criterion #2 (subscription_status)
- **Reason**: subscription_status = 'never_subscribed' (not churned)

---

## Seed Data Design (Edge Cases)

The seed data was designed to cover all 8 criteria edge cases:

| renter_id | Edge Case | Searches | In Audience? |
|----------|-----------|----------|---------------|
| renter_001 | Ideal candidate (all criteria met) | 5 | ✓ Yes |
| renter_002 | Exactly 3 searches (threshold) | 3 | ✓ Yes |
| renter_003 | Suppressed + < 3 searches | 2 | ✗ No |
| renter_004 | sms_consent = FALSE | 5 | ✗ No |
| renter_005 | No phone number | 4 | ✗ No |
| renter_006 | Active subscription | 5 | ✗ No |
| renter_007 | DND in future | 4 | ✗ No |
| renter_008 | Suppressed + DND in past | 4 | ✗ No |
| renter_009 | < 30 days login | 3 | ✗ No |
| renter_010 | never_subscribed | 4 | ✗ No |

---

## DAG Execution Summary

```
Step 0: database_provisioning - Skipped (tables already exist)
Step 1: run_audience_query   - Exported 2 recipients to staging table, then read them back
Step 2: validate_audience   - Passed (count=2, within limits)
Step 3: execute_campaign_send - Sent 2, Failed 0, Skipped 0
Step 4: log_results_and_notify - Success (reported to BigQuery + Slack)
```

---

## Query Code

```sql
SELECT
    p.renter_id,
    p.email,
    p.phone,
    p.last_login,
    COUNT(a.renter_id) AS search_count,
    (EPOCH(CURRENT_DATE()) - EPOCH(DATE(p.last_login))) / 86400 AS days_since_login
FROM renter_profiles p
LEFT JOIN renter_activity a
    ON p.renter_id = a.renter_id
    AND a.event_type = 'search'
    AND a.event_timestamp >= TIMESTAMP_SUB(TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), DAY), INTERVAL 90 DAY)
WHERE
    DATE(p.last_login) < DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    AND p.subscription_status = 'churned'
    AND p.phone IS NOT NULL
    AND p.sms_consent = TRUE
    AND (p.dnd_until IS NULL OR DATE(p.dnd_until) < CURRENT_DATE())
    AND NOT EXISTS (SELECT 1 FROM suppression_list s WHERE s.renter_id = p.renter_id)
GROUP BY p.renter_id, p.email, p.phone, p.last_login, p.subscription_status, p.sms_consent, p.dnd_until
HAVING COUNT(a.renter_id) >= 3
ORDER BY days_since_login DESC;
```