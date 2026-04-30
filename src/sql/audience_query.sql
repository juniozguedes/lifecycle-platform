-- Builds the audience for an SMS reactivation campaign
--
-- Criteria:
--   1. Last login was more than 30 days ago
--   2. Subscription status is 'churned'
--   3. At least 3 searches in the past 90 days
--   4. Has a phone number on file
--   5. sms_consent = TRUE
--   6. NOT in suppression list
--   7. dnd_until is NULL or in the past
--   8. Idempotent within a day (anchors all date math to CURRENT_DATE())
--
-- Expected result from seed data: renter_001, renter_002 (2 records)
-- renter_008 otherwise qualifies, but is excluded by suppression_list.

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
    -- Criterion 1: Last login more than 30 days ago
    DATE(p.last_login) < DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    -- Criterion 2: Subscription status is churned
    AND p.subscription_status = 'churned'
    -- Criterion 3: At least 3 searches in past 90 days
    -- (COUNT in HAVING clause after GROUP BY)
    -- Criterion 4: Has phone number (NULL check)
    AND p.phone IS NOT NULL
    -- Criterion 5: SMS consent = TRUE
    AND p.sms_consent = TRUE
    -- Criterion 7: dnd_until is NULL or in the past
    AND (p.dnd_until IS NULL OR DATE(p.dnd_until) < CURRENT_DATE())
    -- Criterion 6: Exclude suppression list (LEFT JOIN + IS NULL pattern)
    AND NOT EXISTS (
        SELECT 1
        FROM suppression_list s
        WHERE s.renter_id = p.renter_id
    )
GROUP BY
    p.renter_id,
    p.email,
    p.phone,
    p.last_login,
    p.subscription_status,
    p.sms_consent,
    p.dnd_until
HAVING
    -- Criterion 3 (filtered after aggregation): At least 3 searches
    COUNT(a.renter_id) >= 3
ORDER BY
    days_since_login DESC;