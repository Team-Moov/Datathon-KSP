param (
    [switch]$Docker
)

if ($Docker) {
    Write-Host "Starting full stack via Docker Compose..." -ForegroundColor Green
    docker compose up --build
    exit
}

Write-Host "Starting Local Development Environment..." -ForegroundColor Cyan

# 1. Start Infrastructure (Postgres, Neo4j, Redis)
Write-Host "-> Launching Infrastructure (Docker)"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.ui.RawUI.WindowTitle = 'Infrastructure'; cd backend; docker compose up postgres neo4j redis"

# Wait for containers to be healthy
Write-Host "Waiting for database containers to start and pass health checks..." -ForegroundColor Yellow
$timeout = 90
$elapsed = 0
while ($elapsed -lt $timeout) {
    $postgres_status = (docker inspect --format '{{.State.Health.Status}}' karnataka-crime-platform-postgres-1 2>$null)
    $neo4j_status = (docker inspect --format '{{.State.Health.Status}}' karnataka-crime-platform-neo4j-1 2>$null)
    
    if ($postgres_status -eq "healthy" -and $neo4j_status -eq "healthy") {
        Write-Host "Database containers are healthy!" -ForegroundColor Green
        break
    }
    
    Write-Host "Waiting... (Postgres: $postgres_status, Neo4j: $neo4j_status)"
    Start-Sleep -Seconds 3
    $elapsed += 3
}

if ($elapsed -ge $timeout) {
    Write-Warning "Timed out waiting for database health checks. Proceeding to launch services anyway..."
}

# 2. Start Backend API
Write-Host "-> Launching Backend API (FastAPI)"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.ui.RawUI.WindowTitle = 'Backend API'; cd backend; if (Test-Path venv\Scripts\python.exe) { .\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8090 } else { uvicorn app.main:app --reload --port 8090 }"

# 3. Start Celery Worker
Write-Host "-> Launching Celery Worker"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.ui.RawUI.WindowTitle = 'Celery Worker'; cd backend; if (Test-Path venv\Scripts\celery.exe) { .\venv\Scripts\celery.exe -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo } else { celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo }"

# 4. Start Frontend
Write-Host "-> Launching Frontend (Vite)"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.ui.RawUI.WindowTitle = 'Frontend'; cd frontend; npm run dev"

Write-Host "`nAll components started in separate windows!" -ForegroundColor Green
Write-Host "Note: To start the entire stack fully containerized (including API and Frontend), run:" -ForegroundColor Yellow
Write-Host ".\start.ps1 -Docker" -ForegroundColor Yellow
