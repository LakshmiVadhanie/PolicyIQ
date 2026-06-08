# ============================================================
# PolicyIQ — BigQuery Table Schema
# Run these commands to set up the analytics layer:
#
#   bq mk --dataset <PROJECT_ID>:policyiq_analytics
#   bq query --use_legacy_sql=false < bigquery/schema.sql
# ============================================================

--  Interactions Table 
CREATE TABLE IF NOT EXISTS `policyiq_analytics.interactions`
(
    request_id        STRING    NOT NULL,
    session_id        STRING    NOT NULL,
    timestamp         TIMESTAMP NOT NULL,
    user_query        STRING,
    intent            STRING,
    agent_response    STRING,
    retrieved_context STRING,
    confidence        FLOAT64,
    latency_ms        INT64
)
PARTITION BY DATE(timestamp)
CLUSTER BY intent, session_id
OPTIONS (
    description = 'PolicyIQ agent interaction logs',
    partition_expiration_days = 365
);

--  Evaluation Metrics Table 
CREATE TABLE IF NOT EXISTS `policyiq_analytics.evaluation_metrics`
(
    request_id        STRING    NOT NULL,
    session_id        STRING    NOT NULL,
    timestamp         TIMESTAMP NOT NULL,
    faithfulness      FLOAT64,
    answer_relevancy  FLOAT64,
    context_precision FLOAT64,
    composite_score   FLOAT64,
    passed_gate       BOOL
)
PARTITION BY DATE(timestamp)
CLUSTER BY passed_gate
OPTIONS (
    description = 'RAGAS evaluation metric scores per request'
);

--  Agent Routing Log Table 
CREATE TABLE IF NOT EXISTS `policyiq_analytics.agent_routing_log`
(
    request_id   STRING    NOT NULL,
    session_id   STRING    NOT NULL,
    timestamp    TIMESTAMP NOT NULL,
    intent       STRING,
    routed_agent STRING,
    confidence   FLOAT64,
    iteration    INT64
)
PARTITION BY DATE(timestamp)
CLUSTER BY intent, routed_agent
OPTIONS (
    description = 'LangGraph agent routing decisions audit log'
);

--  Useful Analytics Views 
CREATE OR REPLACE VIEW `policyiq_analytics.daily_quality_summary` AS
SELECT
    DATE(timestamp)                                     AS date,
    COUNT(*)                                            AS total_requests,
    AVG(composite_score)                                AS avg_composite,
    AVG(faithfulness)                                   AS avg_faithfulness,
    AVG(answer_relevancy)                               AS avg_relevancy,
    COUNTIF(passed_gate) / COUNT(*)                     AS gate_pass_rate
FROM `policyiq_analytics.evaluation_metrics`
GROUP BY 1
ORDER BY 1 DESC;

CREATE OR REPLACE VIEW `policyiq_analytics.intent_distribution` AS
SELECT
    DATE(timestamp)  AS date,
    intent,
    COUNT(*)         AS query_count,
    AVG(confidence)  AS avg_confidence,
    AVG(latency_ms)  AS avg_latency_ms
FROM `policyiq_analytics.interactions`
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC;
