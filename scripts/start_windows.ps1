$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
$ImageName = if ($env:FINALLY_IMAGE) { $env:FINALLY_IMAGE } else { "finally:latest" }
$ContainerName = if ($env:FINALLY_CONTAINER) { $env:FINALLY_CONTAINER } else { "finally-app" }
$Port = if ($env:FINALLY_PORT) { $env:FINALLY_PORT } else { "8000" }
$EnvFile = Join-Path $RootDir ".env"
$DbDir = Join-Path $RootDir "db"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required but was not found in PATH."
}

if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $RootDir ".env.example") $EnvFile
    Write-Host "Created .env from .env.example. Edit it to add API keys when needed."
}

New-Item -ItemType Directory -Force -Path $DbDir | Out-Null

docker build -t $ImageName $RootDir

$Existing = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $ContainerName }
if ($Existing) {
    docker rm -f $ContainerName | Out-Null
}

docker run -d `
    --name $ContainerName `
    --env-file $EnvFile `
    -e DB_PATH=/app/db/finally.db `
    -p "${Port}:8000" `
    -v "${DbDir}:/app/db" `
    $ImageName | Out-Null

Write-Host "FinAlly is running at http://localhost:$Port"
