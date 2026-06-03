param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$ImageName = "finally"
$ContainerName = "finally"
$Port = 8000

Set-Location $ProjectRoot

# Build if needed
$imageExists = docker image inspect $ImageName 2>$null
if (-not $imageExists -or $Build) {
    Write-Host "Building FinAlly Docker image..."
    docker build -t $ImageName .
}

# Stop existing container
$running = docker ps -q -f "name=$ContainerName"
if ($running) {
    Write-Host "Stopping existing container..."
    docker stop $ContainerName | Out-Null
    docker rm $ContainerName | Out-Null
} else {
    $stopped = docker ps -aq -f "name=$ContainerName"
    if ($stopped) { docker rm $ContainerName | Out-Null }
}

# Ensure .env exists
if (-not (Test-Path "$ProjectRoot\.env")) {
    Write-Host "Warning: .env not found. Copying from .env.example..."
    Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env"
}

Write-Host "Starting FinAlly..."
docker run -d `
    --name $ContainerName `
    -p "${Port}:8000" `
    -v "finally-data:/app/db" `
    --env-file "$ProjectRoot\.env" `
    $ImageName

Write-Host ""
Write-Host "FinAlly is running at http://localhost:$Port"
Write-Host ""
Write-Host "To view logs: docker logs -f $ContainerName"
Write-Host "To stop:      .\scripts\stop_windows.ps1"

Start-Sleep 2
Start-Process "http://localhost:$Port"
