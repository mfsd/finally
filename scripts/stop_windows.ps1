$ErrorActionPreference = "Stop"

$ContainerName = if ($env:FINALLY_CONTAINER) { $env:FINALLY_CONTAINER } else { "finally-app" }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required but was not found in PATH."
}

$Existing = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $ContainerName }
if ($Existing) {
    docker rm -f $ContainerName | Out-Null
    Write-Host "Stopped $ContainerName."
} else {
    Write-Host "$ContainerName is not running."
}
