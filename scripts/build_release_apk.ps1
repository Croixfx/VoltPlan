<#
.SYNOPSIS
  Builds the VoltPlan release APK pointed at a deployed backend.

.DESCRIPTION
  The backend URL and API key are compiled into the app (flutter --dart-define), so they are taken from
  environment variables and never written to a file or to the repository.

  $env:VOLTPLAN_API_URL = "https://voltplan-api.onrender.com/api"
  $env:VOLTPLAN_API_KEY = "<the API_KEY you set on the backend>"
  .\scripts\build_release_apk.ps1

  Output: build\app\outputs\flutter-apk\app-release.apk
  Signed with android\key.properties when it exists (see docs\DEPLOY.md), otherwise with the debug key.
#>
$ErrorActionPreference = "Stop"

$url = $env:VOLTPLAN_API_URL
$key = $env:VOLTPLAN_API_KEY

if (-not $url) { throw "Set `$env:VOLTPLAN_API_URL to the backend API URL, e.g. https://your-host/api" }
$url = $url.TrimEnd("/")
if (-not $url.EndsWith("/api")) { throw "VOLTPLAN_API_URL must end with /api (got: $url)" }
if ($url -notmatch "^https://") {
    throw "VOLTPLAN_API_URL must use https://. Android blocks plain http to remote servers, and the API key would travel in clear text."
}
if (-not $key) { throw "Set `$env:VOLTPLAN_API_KEY to the API_KEY configured on the backend." }

# The backend must be reachable and healthy before an APK that depends on it is built.
Write-Host "Checking $url/health ..."
try {
    $health = Invoke-RestMethod -Uri "$url/health" -TimeoutSec 30
} catch {
    throw "Backend health check failed: $($_.Exception.Message)"
}
Write-Host ("  backend ok, AI provider: {0}" -f $health.ai_provider)
if ($health.ai_provider -eq "mock") {
    Write-Warning "The backend runs the MOCK AI provider: every uploaded plan gets the same demo rooms."
}

# ...and the key must be accepted (health is public, so test a protected route).
try {
    Invoke-RestMethod -Uri "$url/equipment" -Headers @{ "X-API-Key" = $key } -TimeoutSec 30 | Out-Null
} catch {
    throw "The backend rejected the API key (or the protected route failed): $($_.Exception.Message)"
}
Write-Host "  API key accepted"

Push-Location (Join-Path $PSScriptRoot "..")
try {
    flutter build apk --release "--dart-define=API_BASE_URL=$url" "--dart-define=API_KEY=$key"
    if ($LASTEXITCODE -ne 0) { throw "flutter build failed" }
} finally {
    Pop-Location
}

$apk = Join-Path $PSScriptRoot "..\build\app\outputs\flutter-apk\app-release.apk"
$hash = (Get-FileHash $apk -Algorithm SHA256).Hash
Write-Host ""
Write-Host "APK: $((Resolve-Path $apk).Path)"
Write-Host ("Size: {0:N1} MB" -f ((Get-Item $apk).Length / 1MB))
Write-Host "SHA-256: $hash"
Write-Host "Note: the API key is embedded in this APK. Share it only with people who should have access."
