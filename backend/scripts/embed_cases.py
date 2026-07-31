"""
CLI fallback for EmbeddingService.backfill_case_embeddings() — the normal path
is the admin-triggered "Backfill Embeddings" action (System Jobs page /
POST /admin/jobs/backfill-embeddings), which runs the same method as a Celery
task. This script exists only for out-of-band runs without API access.

Run:  docker compose exec api python -m scripts.embed_cases
"""

import asyncio

from app.services.embedding_service import EmbeddingService


async def run() -> None:
    result = await EmbeddingService.backfill_case_embeddings()
    print(result)


if __name__ == "__main__":
    asyncio.run(run())
