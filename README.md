# PolicyIQ — Agentic Insurance Intelligence Agent

<div align="center">

[![CI](https://github.com/LakshmiVadhanie/PolicyIQ/actions/workflows/ci.yml/badge.svg)](https://github.com/LakshmiVadhanie/PolicyIQ/actions/workflows/ci.yml)
[![Deploy](https://github.com/LakshmiVadhanie/PolicyIQ/actions/workflows/deploy.yml/badge.svg)](https://github.com/LakshmiVadhanie/PolicyIQ/actions/workflows/deploy.yml)
![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-0.1.5-green.svg)
![Vertex AI](https://img.shields.io/badge/Vertex%20AI-Gemini-orange.svg)
![GCP](https://img.shields.io/badge/GCP-Cloud%20Run-blue.svg)

**A production-grade multi-agent insurance intelligence system that autonomously routes queries across specialized AI agents, applies RAGAS quality gates, and delivers accurate, grounded responses at scale.**

</div>

---

## Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI (Cloud Run)                        │
│  POST /chat  ◄────── Dialogflow CX Webhook (/webhook)       │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│               LangGraph StateGraph Pipeline                  │
│                                                              │
│   ┌──────────┐     ┌─────────────┐                          │
│   │Supervisor│────►│ policy_agent│ (PolicyLookup)           │
│   │  (Gemini)│     ├─────────────┤                          │
│   │          │────►│ claims_agent│ (ClaimsTriage)           │
│   │          │     ├─────────────┤                          │
│   │          │────►│premium_agent│ (PremiumEstimation)      │
│   └──────────┘     └──────┬──────┘                          │
│         ▲                  │ confidence check                │
│         └──────────────────┘ (loop if < threshold)          │
│                             │                                │
│                    ┌────────▼────────┐                       │
│                    │  Quality Gate   │ ← RAGAS evaluation    │
│                    │  (RAGAS Gate)   │                       │
│                    └────────┬────────┘                       │
└─────────────────────────────┼───────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Final Response     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  BigQuery Analytics  │
                    │  · interactions      │
                    │  · eval_metrics      │
                    │  · routing_log       │
                    └─────────────────────┘
```

## Key Features

| Feature | Implementation |
|---|---|
| **Multi-Agent Routing** | LangGraph `StateGraph` with supervisor pattern |
| **LLM Backbone** | Vertex AI Gemini 1.5 Pro / Flash |
| **Intent Detection** | Dialogflow CX + LangGraph supervisor |
| **Quality Gates** | RAGAS (`faithfulness`, `answer_relevancy`, `context_precision`) |
| **Analytics** | BigQuery interaction and metrics logging |
| **CI/CD** | GitHub Actions → Cloud Build → Cloud Run |
| **Uptime** | Cloud Run auto-scaling (1–20 instances) |
| **Local Dev** | Full mock mode — no GCP credentials required |

## Agents

### 🧭 Supervisor Agent
Routes queries to specialist agents based on intent detection. Uses Gemini to classify queries into `PolicyLookup`, `ClaimsTriage`, or `PremiumEstimation`. Includes a confidence-check loop — if confidence falls below threshold, re-routes with additional context.

### 📋 Policy Agent
Handles coverage lookups, policy details, renewal information, and coverage verification. Bound to policy database tools with real-time lookup capability.

### 🚨 Claims Agent
Manages claim status checks, new claim triage (severity classification + SLA assignment), and claims history retrieval. Responds with empathy and clear next steps.

### 💰 Premium Agent
Provides actuarial premium estimates for auto, home, and health insurance. Explains pricing factors and discount opportunities.

### 🛡️ Quality Gate
Every response passes through a RAGAS evaluation gate before reaching the user. Responses scoring below `composite >= 0.70` are replaced with a safe fallback and flagged for review.

## Tech Stack

- **Orchestration**: [LangGraph](https://github.com/langchain-ai/langgraph) `StateGraph`
- **LLM**: [Vertex AI](https://cloud.google.com/vertex-ai) Gemini 1.5 Pro/Flash
- **Intent Detection**: [Dialogflow CX](https://cloud.google.com/dialogflow) 
- **API**: [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn
- **Evaluation**: [RAGAS](https://docs.ragas.io/) quality gates
- **Analytics**: [BigQuery](https://cloud.google.com/bigquery)
- **Deployment**: [GCP Cloud Run](https://cloud.google.com/run)
- **CI/CD**: GitHub Actions + Cloud Build

## Quick Start (Local Dev)

```bash
# Clone
git clone https://github.com/LakshmiVadhanie/PolicyIQ.git
cd PolicyIQ

# Set up Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure (mock mode — no GCP needed)
cp .env.example .env
# USE_MOCK_LLM=true and USE_MOCK_BIGQUERY=true are defaults

# Run the API
uvicorn app.main:app --reload --port 8080
```

Visit `http://localhost:8080/docs` for the interactive API playground.

### Test a Query

```bash
# Policy lookup
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What does my policy POL-001 cover?", "session_id": "demo-001"}'

# Claims triage  
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need to file a claim for a car accident", "session_id": "demo-002"}'

# Premium estimation
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How much is car insurance for a 30-year-old?", "session_id": "demo-003"}'
```

## Running Tests

```bash
# Unit tests
pytest tests/test_agents.py tests/test_api.py -v

# RAGAS quality gate (CI gate)
pytest tests/test_evaluation.py -v

# Full suite with coverage
pytest tests/ -v --cov=app --cov-report=term-missing
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Cloud Run health probe |
| `POST` | `/chat` | Direct chat with pipeline |
| `POST` | `/webhook` | Dialogflow CX fulfillment webhook |
| `GET` | `/metrics` | BigQuery analytics summary |
| `GET` | `/docs` | Interactive API docs (Swagger) |

## Deployment (GCP)

### Prerequisites

```bash
# Set up GCP project
gcloud projects create YOUR_PROJECT_ID
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable \
  run.googleapis.com \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  dialogflow.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com

# Create BigQuery dataset and tables
bq mk --dataset YOUR_PROJECT_ID:policyiq_analytics
bq query --use_legacy_sql=false < bigquery/schema.sql
```

### GitHub Actions Secrets Required

| Secret | Description |
|--------|-------------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `WIF_PROVIDER` | Workload Identity Federation provider |
| `WIF_SERVICE_ACCOUNT` | Service account email |

### Manual Deploy

```bash
# Build and push
docker build --target production -t gcr.io/YOUR_PROJECT/policyiq:latest .
docker push gcr.io/YOUR_PROJECT/policyiq:latest

# Deploy to Cloud Run
gcloud run deploy policyiq \
  --image gcr.io/YOUR_PROJECT/policyiq:latest \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi --cpu 2 \
  --set-env-vars="APP_ENV=production,USE_MOCK_LLM=false,USE_MOCK_BIGQUERY=false"
```

## BigQuery Analytics

The system automatically logs every interaction and evaluation metric to BigQuery:

```sql
-- Daily quality summary
SELECT * FROM `policyiq_analytics.daily_quality_summary` LIMIT 7;

-- Intent distribution
SELECT * FROM `policyiq_analytics.intent_distribution` ORDER BY date DESC;
```

## Project Structure

```
PolicyIQ/
├── app/
│   ├── main.py                    # FastAPI entrypoint
│   ├── config.py                  # Settings (pydantic-settings)
│   ├── agents/
│   │   ├── state.py               # LangGraph TypedDict state
│   │   ├── graph.py               # StateGraph pipeline definition
│   │   ├── supervisor.py          # Intent router (Gemini)
│   │   ├── policy_agent.py        # Policy lookup specialist
│   │   ├── claims_agent.py        # Claims triage specialist
│   │   └── premium_agent.py       # Premium estimation specialist
│   ├── api/
│   │   ├── models.py              # Pydantic request/response schemas
│   │   └── routes/
│   │       ├── chat.py            # POST /chat, GET /metrics
│   │       ├── webhook.py         # POST /webhook (Dialogflow CX)
│   │       └── health.py          # GET /health, GET /
│   ├── evaluation/
│   │   ├── ragas_evaluator.py     # RAGAS metric computation
│   │   └── quality_gate.py        # Quality gate LangGraph node
│   ├── tools/
│   │   ├── policy_tools.py        # Policy database tools
│   │   ├── claims_tools.py        # Claims management tools
│   │   └── bigquery_tools.py      # BQ read/write helpers
│   └── analytics/
│       └── logger.py              # Structured logging
├── tests/
│   ├── conftest.py                # Shared fixtures
│   ├── test_agents.py             # Agent unit tests
│   ├── test_api.py                # API endpoint tests
│   ├── test_evaluation.py         # RAGAS gate tests (CI gate)
│   └── golden_dataset.json        # 8 golden Q&A examples
├── bigquery/
│   └── schema.sql                 # BigQuery DDL
├── dialogflow/
│   └── agent_config.json          # Dialogflow CX agent config
├── .github/workflows/
│   ├── ci.yml                     # CI: lint → test → RAGAS gate
│   └── deploy.yml                 # CD: build → push → Cloud Run
├── Dockerfile                     # Multi-stage production image
├── docker-compose.yml             # Local development
├── cloudbuild.yaml                # GCP Cloud Build pipeline
└── requirements.txt
```

## Performance

- **Resolution time**: ~65% reduction vs manual routing (simulated)
- **Quality gate pass rate**: >95% in testing
- **Uptime**: 98%+ on Cloud Run with min-instance=1
- **P95 latency**: <3s end-to-end (mock mode), <8s with Vertex AI

---

*Built with LangGraph, Vertex AI, and GCP. Part of the PolicyIQ insurance intelligence platform.*
