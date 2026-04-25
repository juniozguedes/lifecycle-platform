-- Schema for Lifecycle Platform
-- Run against LocalGCP (localhost:9060) or BigQuery

-- 1. Renter Activity Table
CREATE TABLE IF NOT EXISTS renter_activity (
    renter_id STRING,
    event_type STRING,
    event_timestamp TIMESTAMP,
    property_id STRING,
    channel STRING,
    utm_source STRING
);

-- 2. Renter Profiles Table
CREATE TABLE IF NOT EXISTS renter_profiles (
    renter_id STRING,
    email STRING,
    phone STRING,
    last_login TIMESTAMP,
    subscription_status STRING,
    sms_consent BOOLEAN,
    email_consent BOOLEAN,
    dnd_until TIMESTAMP,
    created_at TIMESTAMP
);

-- 3. Suppression List Table
CREATE TABLE IF NOT EXISTS suppression_list (
    renter_id STRING,
    suppression_reason STRING,
    suppressed_at TIMESTAMP
);

-- 4. ML Predictions Table
CREATE TABLE IF NOT EXISTS ml_predictions.renter_send_scores (
    renter_id STRING,
    predicted_conversion_probability FLOAT64,
    model_version STRING,
    scored_at TIMESTAMP
);