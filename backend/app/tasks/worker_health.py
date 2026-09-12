"""
Trivial sidecar HTTP app for the Cloud Run worker service. Cloud Run requires
every service to listen on $PORT for its startup probe, but a Celery worker
process (app.tasks.celery_app, run alongside this via the container's start
command) never opens an HTTP port on its own — this just gives Cloud Run
something to probe while the real work happens in the Celery process.
"""

from fastapi import FastAPI

app = FastAPI(include_in_schema=False)


@app.get("/")
async def health() -> dict:
    return {"status": "ok"}
