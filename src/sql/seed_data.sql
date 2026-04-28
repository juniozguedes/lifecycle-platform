-- Seed data for Lifecycle Platform
-- Run after schema.sql

-- Insert renter profiles
INSERT INTO renter_profiles (renter_id, email, phone, last_login, subscription_status, sms_consent, email_consent, dnd_until, created_at)
VALUES
  -- In-scope: churned, >30 days ago, has phone, sms_consent, not suppressed, no DND
  ('renter_001', 'alice@example.com', '+1555123001', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 35 DAY), 'churned', TRUE, TRUE, NULL, TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)),
  ('renter_002', 'bob@example.com', '+1555123002', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 45 DAY), 'churned', TRUE, TRUE, NULL, TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 200 DAY)),
  ('renter_003', 'carol@example.com', '+1555123003', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY), 'churned', TRUE, TRUE, NULL, TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 150 DAY)),
  -- Edge: has phone but sms_consent = FALSE
  ('renter_004', 'dave@example.com', '+1555123004', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 40 DAY), 'churned', FALSE, TRUE, NULL, TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 100 DAY)),
  -- Edge: no phone
  ('renter_005', 'eve@example.com', NULL, TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 50 DAY), 'churned', TRUE, TRUE, NULL, TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)),
  -- Edge: active subscription (should be excluded)
  ('renter_006', 'frank@example.com', '+1555123006', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 35 DAY), 'active', TRUE, TRUE, NULL, TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 300 DAY)),
  -- Edge: dnd_until in the future
  ('renter_007', 'grace@example.com', '+1555123007', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 40 DAY), 'churned', TRUE, TRUE, TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 10 DAY), TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 120 DAY)),
  -- Edge: dnd_until in the past (should be included)
  ('renter_008', 'henry@example.com', '+1555123008', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 55 DAY), 'churned', TRUE, TRUE, TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 DAY), TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 80 DAY)),
  -- Edge: < 30 days ago (should be excluded)
  ('renter_009', 'iris@example.com', '+1555123009', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 15 DAY), 'churned', TRUE, TRUE, NULL, TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 200 DAY)),
  -- Edge: never_subscribed (should be excluded per criteria - only 'churned')
  ('renter_010', 'jack@example.com', '+1555123010', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY), 'never_subscribed', TRUE, TRUE, NULL, TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY));

-- Insert renter activity (searches in past 90 days)
INSERT INTO renter_activity (renter_id, event_type, event_timestamp, property_id, channel, utm_source)
VALUES
  -- renter_001: 5 searches (>= 3, in scope)
  ('renter_001', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 10 DAY), 'prop_101', 'web', 'google'),
  ('renter_001', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 20 DAY), 'prop_102', 'web', 'google'),
  ('renter_001', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY), 'prop_103', 'ios', NULL),
  ('renter_001', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 50 DAY), 'prop_104', 'android', NULL),
  ('renter_001', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 70 DAY), 'prop_105', 'web', 'bing'),
  -- renter_002: 3 searches (exactly 3, in scope)
  ('renter_002', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 DAY), 'prop_201', 'web', NULL),
  ('renter_002', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 25 DAY), 'prop_202', 'ios', NULL),
  ('renter_002', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 80 DAY), 'prop_203', 'web', NULL),
  -- renter_003: 2 searches (< 3, should be excluded)
  ('renter_003', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 15 DAY), 'prop_301', 'web', NULL),
  ('renter_003', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY), 'prop_302', 'android', NULL),
  -- renter_004: 5 searches but no sms_consent
  ('renter_004', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 10 DAY), 'prop_401', 'web', NULL),
  ('renter_004', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 20 DAY), 'prop_402', 'web', NULL),
  ('renter_004', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY), 'prop_403', 'ios', NULL),
  ('renter_004', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 40 DAY), 'prop_404', 'android', NULL),
  ('renter_004', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 50 DAY), 'prop_405', 'web', NULL),
  -- renter_005: 4 searches but no phone
  ('renter_005', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 DAY), 'prop_501', 'web', NULL),
  ('renter_005', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 15 DAY), 'prop_502', 'ios', NULL),
  ('renter_005', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY), 'prop_503', 'web', NULL),
  ('renter_005', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY), 'prop_504', 'android', NULL),
  -- renter_006: 5 searches but active (should be excluded)
  ('renter_006', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 10 DAY), 'prop_601', 'web', NULL),
  ('renter_006', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 20 DAY), 'prop_602', 'ios', NULL),
  ('renter_006', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY), 'prop_603', 'web', NULL),
  ('renter_006', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 40 DAY), 'prop_604', 'android', NULL),
  ('renter_006', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 50 DAY), 'prop_605', 'web', NULL),
  -- renter_007: 4 searches but dnd_until in future
  ('renter_007', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 10 DAY), 'prop_701', 'web', NULL),
  ('renter_007', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 20 DAY), 'prop_702', 'ios', NULL),
  ('renter_007', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 40 DAY), 'prop_703', 'android', NULL),
  ('renter_007', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 70 DAY), 'prop_704', 'web', NULL),
  -- renter_008: 4 searches, dnd in past (should be included)
  ('renter_008', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 DAY), 'prop_801', 'web', NULL),
  ('renter_008', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 15 DAY), 'prop_802', 'ios', NULL),
  ('renter_008', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 45 DAY), 'prop_803', 'web', NULL),
  ('renter_008', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 75 DAY), 'prop_804', 'android', NULL),
  -- renter_009: 3 searches but < 30 days ago login
  ('renter_009', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 DAY), 'prop_901', 'web', NULL),
  ('renter_009', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 10 DAY), 'prop_902', 'ios', NULL),
  ('renter_009', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 20 DAY), 'prop_903', 'web', NULL),
  -- renter_010: 4 searches but never_subscribed
  ('renter_010', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 DAY), 'prop_1001', 'web', NULL),
  ('renter_010', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 15 DAY), 'prop_1002', 'ios', NULL),
  ('renter_010', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY), 'prop_1003', 'web', NULL),
  ('renter_010', 'search', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY), 'prop_1004', 'android', NULL);

-- Insert suppression list entries
INSERT INTO suppression_list (renter_id, suppression_reason, suppressed_at)
VALUES
  ('renter_003', 'unsubscribed', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 DAY)),
  ('renter_008', 'bounced', TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 3 DAY));

-- Insert ML predictions (for Part 4)
INSERT INTO ml_predictions.renter_send_scores (renter_id, predicted_conversion_probability, model_version, scored_at)
VALUES
  ('renter_001', 0.45, 'v2.1', CURRENT_TIMESTAMP()),
  ('renter_002', 0.32, 'v2.1', CURRENT_TIMESTAMP()),
  ('renter_003', 0.78, 'v2.1', CURRENT_TIMESTAMP()),
  ('renter_004', 0.12, 'v2.1', CURRENT_TIMESTAMP()),
  ('renter_005', 0.55, 'v2.1', CURRENT_TIMESTAMP()),
  ('renter_006', 0.89, 'v2.1', CURRENT_TIMESTAMP()),
  ('renter_007', 0.21, 'v2.1', CURRENT_TIMESTAMP()),
  ('renter_008', 0.67, 'v2.1', CURRENT_TIMESTAMP()),
  ('renter_009', 0.35, 'v2.1', CURRENT_TIMESTAMP()),
  ('renter_010', 0.18, 'v2.1', CURRENT_TIMESTAMP());