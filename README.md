# Karnataka Crime Analytics Platform

**IBM Hackathon — Team Moov**

Intelligent Conversational AI & Crime Analytics Platform for Karnataka Police.

---

## Overview

A full-stack crime intelligence platform built on:
- **FastAPI** backend with async SQLAlchemy (PostgreSQL + pgvector)
- **Neo4j** graph database for criminal network analysis
- **Google Vertex AI / Gemini 1.5 Pro** for conversational AI
- **Google Cloud Speech-to-Text** for Kannada voice queries
- **LangGraph** agentic orchestration with deterministic tool dispatch
- **Celery + Redis** for background analytics jobs

## Architecture Principle

> **The LLM plans and narrates. Deterministic tools compute.**

All analytical capabilities (graph algorithms, Hawkes/ETAS forecasting, risk scoring, financial crime detection) are fixed, versioned, deterministic tools. The LLM selects and narrates — it never fabricates a number.

## Quick Start

```bash
cd backend
cp .env.example .env        # fill in GCP_PROJECT, secrets
docker-compose up -d        # starts Postgres, Neo4j, Redis
alembic upgrade head        # run DB migrations
uvicorn app.main:app --reload
```

API docs: `http://localhost:8000/api/v1/docs`

## GCP Setup

See [`backend/gcp_auth_setup.md`](backend/gcp_auth_setup.md) for the complete authentication and Vertex AI setup guide.

## Design Document

See [`karnataka_crime_platform_design.md`](karnataka_crime_platform_design.md) for the full architecture and feature design.
