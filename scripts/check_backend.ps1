<#
.SYNOPSIS
  Checks that the deployed VoltPlan backend works. Prints PASS / WARN / FAIL (or SKIP) for each check.

.DESCRIPTION
  1. Alive      - /api/health answers (waits for a sleeping free-tier server to wake up)
  2. Locked     - requests without a key, or with a wrong key, are refused (401)
  3. Key works  - requests with your key are accepted
  4. AI         - the AI provider accepts its key and the configured model exists (no plan is analysed)
  5. Full test  - only with -Full: draws a small floor plan, uploads it, runs a REAL analysis (one AI call),
                  checks the rooms that came back, then deletes the test project

  The API key is read from -ApiKey, else $env:VOLTPLAN_API_KEY, else the file ~\voltplan_api_key.txt.
  It is never printed.

.EXAMPLE
  .\scripts\check_backend.ps1
  .\scripts\check_backend.ps1 -Full
  .\scripts\check_backend.ps1 -ApiUrl http://127.0.0.1:8000/api      # a local backend

.NOTES
  Exit code 0 = no FAIL (warnings are allowed), 1 = at least one FAIL.
#>
[CmdletBinding()]
param(
    [string]$ApiUrl = $(if ($env:VOLTPLAN_API_URL) { $env:VOLTPLAN_API_URL } else { "https://voltplan-api.onrender.com/api" }),
    [string]$ApiKey = $env:VOLTPLAN_API_KEY,
    [string]$KeyFile = (Join-Path $HOME "voltplan_api_key.txt"),
    [switch]$Full
)

$ErrorActionPreference = "Stop"
$Base = $ApiUrl.TrimEnd("/")
$IsLocal = $Base -match "^https?://(localhost|127\.0\.0\.1|\[::1\])"

if (-not $ApiKey -and (Test-Path $KeyFile)) { $ApiKey = (Get-Content $KeyFile -Raw).Trim() }

$script:Results = New-Object System.Collections.ArrayList

function Add-Result([string]$Name, [string]$Status, [string]$Detail) {
    [void]$script:Results.Add([pscustomobject]@{ Name = $Name; Status = $Status; Detail = $Detail })
    $color = switch ($Status) { "PASS" { "Green" } "WARN" { "Yellow" } "SKIP" { "DarkGray" } default { "Red" } }
    Write-Host ("[{0}] {1}" -f $Status, $Name) -ForegroundColor $color -NoNewline
    if ($Detail) { Write-Host ("  {0}" -f $Detail) } else { Write-Host "" }
}

function Hide-Secret([string]$Text) {
    if ($ApiKey -and $Text) { return $Text.Replace($ApiKey, "***") }
    return $Text
}

function Invoke-Api {
    param([string]$Path, [string]$Method = "GET", [hashtable]$Headers = @{}, [int]$TimeoutSec = 30)
    try {
        $r = Invoke-WebRequest -Uri "$Base$Path" -Method $Method -Headers $Headers -TimeoutSec $TimeoutSec -UseBasicParsing
        return [pscustomobject]@{ Status = [int]$r.StatusCode; Body = $r.Content; Error = $null }
    } catch {
        $status = 0
        $body = ""
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
            if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
                $body = $_.ErrorDetails.Message
            } else {
                try {
                    $reader = New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())
                    $body = $reader.ReadToEnd()
                } catch { }
            }
        }
        return [pscustomobject]@{ Status = $status; Body = (Hide-Secret $body); Error = (Hide-Secret $_.Exception.Message) }
    }
}

function Read-Json([string]$Text) {
    try { return ($Text | ConvertFrom-Json) } catch { return $null }
}

Write-Host ""
Write-Host "VoltPlan backend check" -ForegroundColor Cyan
Write-Host "  server: $Base"
Write-Host ("  api key: {0}" -f $(if ($ApiKey) { "found (not shown)" } else { "NOT FOUND" }))
Write-Host ""

# ---------------------------------------------------------------- 1. alive
$health = $null
$attempts = 6
for ($i = 1; $i -le $attempts; $i++) {
    $r = Invoke-Api "/health" -TimeoutSec 20
    if ($r.Status -eq 200) { $health = Read-Json $r.Body; break }
    if ($i -lt $attempts) {
        Write-Host ("  ... no answer yet (attempt {0}/{1}); a free server needs up to a minute to wake up" -f $i, $attempts) -ForegroundColor DarkGray
        Start-Sleep -Seconds 10
    }
}
if (-not $health) {
    Add-Result "1. Alive" "FAIL" "The server did not answer /health. Check the Render dashboard (Logs) or the URL."
    Write-Host ""
    Write-Host "Cannot continue without a running server." -ForegroundColor Red
    exit 1
}
if ($health.status -ne "ok") {
    Add-Result "1. Alive" "FAIL" ("/health answered but status is '{0}'" -f $health.status)
} else {
    $detail = "environment=$($health.environment), ai_provider=$($health.ai_provider)"
    if (-not $IsLocal -and $health.environment -ne "production") {
        Add-Result "1. Alive" "WARN" "$detail (a deployed server should run with APP_ENV=production)"
    } else {
        Add-Result "1. Alive" "PASS" $detail
    }
}

# ---------------------------------------------------------------- 2. locked
$noKey = Invoke-Api "/projects"
$wrongKey = Invoke-Api "/projects" -Headers @{ "X-API-Key" = "definitely-not-the-key" }
if ($noKey.Status -eq 401 -and $wrongKey.Status -eq 401) {
    Add-Result "2. Locked" "PASS" "no key -> 401, wrong key -> 401"
} elseif ($noKey.Status -eq 200 -and $IsLocal) {
    Add-Result "2. Locked" "WARN" "open (no API_KEY set). Fine for local development, never for a deployed server."
} elseif ($noKey.Status -eq 200) {
    Add-Result "2. Locked" "FAIL" "The API answered WITHOUT a key: anyone can use it. Set API_KEY on the server."
} else {
    Add-Result "2. Locked" "FAIL" ("expected 401, got no-key={0}, wrong-key={1}" -f $noKey.Status, $wrongKey.Status)
}

# ---------------------------------------------------------------- 3. key works
if (-not $ApiKey) {
    if ($IsLocal -and $noKey.Status -eq 200) {
        $headers = @{}
        Add-Result "3. Key works" "WARN" "no key needed on this server"
    } else {
        $headers = $null
        Add-Result "3. Key works" "FAIL" "No API key. Set `$env:VOLTPLAN_API_KEY or put it in $KeyFile."
    }
} else {
    $headers = @{ "X-API-Key" = $ApiKey }
}
if ($null -ne $headers) {
    $projects = Invoke-Api "/projects" -Headers $headers
    $equipment = Invoke-Api "/equipment" -Headers $headers
    if ($projects.Status -eq 200 -and $equipment.Status -eq 200) {
        $count = @(Read-Json $equipment.Body).Count
        if ($ApiKey) { Add-Result "3. Key works" "PASS" ("accepted; {0} equipment types in the catalog" -f $count) }
    } elseif ($projects.Status -eq 401) {
        Add-Result "3. Key works" "FAIL" "The server rejected your key (401). It does not match the API_KEY set on the server."
        $headers = $null    # the remaining checks need a working key
    } else {
        Add-Result "3. Key works" "FAIL" ("/projects answered {0}, /equipment answered {1}" -f $projects.Status, $equipment.Status)
        $headers = $null
    }
}

# ---------------------------------------------------------------- 4. AI
if ($null -eq $headers) {
    Add-Result "4. AI provider" "SKIP" "needs a working API key (see check 3)"
} else {
    $ai = Invoke-Api "/ai/check" -Headers $headers -TimeoutSec 60
    $aiBody = Read-Json $ai.Body
    if ($ai.Status -ne 200 -or -not $aiBody) {
        Add-Result "4. AI provider" "FAIL" ("/ai/check answered {0}. Is the newest backend version deployed?" -f $ai.Status)
    } elseif ($aiBody.provider -eq "mock") {
        Add-Result "4. AI provider" "WARN" "mock provider: every plan gets the same demo rooms. Set AI_PROVIDER=gemini on the server."
    } elseif ($aiBody.ok -and $aiBody.model_available) {
        Add-Result "4. AI provider" "PASS" ("{0} / {1}: key accepted, model available" -f $aiBody.provider, $aiBody.model)
    } elseif ($aiBody.ok) {
        $some = ($aiBody.available_models | Select-Object -First 5) -join ", "
        Add-Result "4. AI provider" "FAIL" ("key accepted but model '{0}' is not available. Try GEMINI_MODEL = one of: {1}" -f $aiBody.model, $some)
    } else {
        Add-Result "4. AI provider" "FAIL" (Hide-Secret $aiBody.message)
    }
}

# ---------------------------------------------------------------- 5. full analysis (optional)
function New-TestPlan([string]$Path) {
    Add-Type -AssemblyName System.Drawing
    $bmp = New-Object System.Drawing.Bitmap 1000, 700
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.Clear([System.Drawing.Color]::White)
    $wall = New-Object System.Drawing.Pen ([System.Drawing.Color]::Black), 8
    $thin = New-Object System.Drawing.Pen ([System.Drawing.Color]::Black), 2
    $white = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
    $font = New-Object System.Drawing.Font "Arial", 20
    $small = New-Object System.Drawing.Font "Arial", 13
    $g.DrawRectangle($wall, 60, 60, 880, 580)
    $g.DrawLine($wall, 520, 60, 520, 330)
    $g.DrawLine($wall, 60, 330, 940, 330)
    $g.DrawLine($wall, 620, 330, 620, 640)
    # three doors: a gap in the wall, a leaf and a swing arc
    $g.FillRectangle($white, 180, 322, 80, 16);  $g.DrawArc($thin, 100, 250, 160, 160, 0, 90);  $g.DrawLine($wall, 180, 330, 180, 410)
    $g.FillRectangle($white, 740, 322, 80, 16);  $g.DrawArc($thin, 660, 250, 160, 160, 0, 90);  $g.DrawLine($wall, 740, 330, 740, 410)
    $g.FillRectangle($white, 612, 460, 16, 80);  $g.DrawArc($thin, 540, 380, 160, 160, 0, 90);  $g.DrawLine($wall, 620, 460, 700, 460)
    $g.DrawString("LIVING ROOM", $font, [System.Drawing.Brushes]::Black, 200, 170)
    $g.DrawString("KITCHEN", $font, [System.Drawing.Brushes]::Black, 640, 170)
    $g.DrawString("BEDROOM", $font, [System.Drawing.Brushes]::Black, 200, 470)
    $g.DrawString("BATHROOM", $font, [System.Drawing.Brushes]::Black, 660, 470)
    $g.DrawRectangle($thin, 800, 540, 120, 80);  $g.DrawString("SHOWER", $small, [System.Drawing.Brushes]::Black, 815, 570)
    $g.DrawRectangle($thin, 780, 90, 120, 50);   $g.DrawString("COOKER", $small, [System.Drawing.Brushes]::Black, 800, 105)
    $g.Dispose()
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

if ($Full) {
    if ($null -eq $headers) {
        Add-Result "5. Full test" "SKIP" "needs a working API key (see check 3)"
    } else {
        $projectId = $null
        $png = Join-Path ([IO.Path]::GetTempPath()) ("voltplan_check_" + [guid]::NewGuid().ToString("N") + ".png")
        try {
            Write-Host "  ... running a real analysis (one AI call, usually 5-20 seconds)" -ForegroundColor DarkGray
            New-TestPlan $png
            $created = Invoke-WebRequest -Uri "$Base/projects" -Method POST -Headers $headers -UseBasicParsing -TimeoutSec 60 `
                -ContentType "application/json" -Body '{"name":"CHECK SCRIPT TEST (auto-deleted)","client":"Check","location":"Kigali"}'
            $projectId = (Read-Json $created.Content).id

            Add-Type -AssemblyName System.Net.Http
            $http = New-Object System.Net.Http.HttpClient
            $http.Timeout = [TimeSpan]::FromSeconds(60)
            $http.DefaultRequestHeaders.Add("X-API-Key", $ApiKey)
            $form = New-Object System.Net.Http.MultipartFormDataContent
            $file = New-Object System.Net.Http.ByteArrayContent (, [IO.File]::ReadAllBytes($png))
            $file.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("image/png")
            $form.Add($file, "file", "plan.png")
            $upload = $http.PostAsync("$Base/projects/$projectId/plan", $form).Result
            if (-not $upload.IsSuccessStatusCode) { throw "upload failed: HTTP $([int]$upload.StatusCode)" }

            $watch = [Diagnostics.Stopwatch]::StartNew()
            $run = Invoke-Api "/projects/$projectId/analyze" -Method POST -Headers $headers -TimeoutSec 180
            $watch.Stop()
            $body = Read-Json $run.Body
            if ($run.Status -eq 200 -and $body.status -eq "completed") {
                $names = ($body.rooms | ForEach-Object { $_.name }) -join ", "
                $demo = @($body.warnings | Where-Object { $_ -match "DEMO DATA" }).Count -gt 0
                $detail = ("{0} rooms ({1}), {2} points, {3} circuits in {4:N1}s" -f @($body.rooms).Count, $names, @($body.electrical_points).Count, @($body.circuits).Count, $watch.Elapsed.TotalSeconds)
                if ($demo) { Add-Result "5. Full test" "WARN" "$detail - but this is DEMO data (mock provider)" }
                elseif (@($body.rooms).Count -lt 3) { Add-Result "5. Full test" "WARN" "$detail - fewer rooms than the 4 that were drawn" }
                else { Add-Result "5. Full test" "PASS" $detail }
            } elseif ($run.Status -eq 422) {
                $msg = (Read-Json $run.Body).detail.message
                Add-Result "5. Full test" "WARN" ("AI answered, but the geometry checks stopped it (that is the checks working): {0}" -f $msg)
            } else {
                $msg = (Read-Json $run.Body).detail
                Add-Result "5. Full test" "FAIL" ("HTTP {0}: {1}" -f $run.Status, (Hide-Secret ([string]$msg)))
            }
        } catch {
            Add-Result "5. Full test" "FAIL" (Hide-Secret $_.Exception.Message)
        } finally {
            if ($projectId) {
                $del = Invoke-Api "/projects/$projectId" -Method DELETE -Headers $headers -TimeoutSec 60
                if ($del.Status -ne 204) { Write-Host ("  note: could not delete test project {0} (HTTP {1}); delete it in the app" -f $projectId, $del.Status) -ForegroundColor Yellow }
            }
            Remove-Item $png -ErrorAction SilentlyContinue
        }
    }
} else {
    Write-Host "  (add -Full to also run a real plan analysis; it makes one AI call)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------- summary
$fail = @($script:Results | Where-Object { $_.Status -eq "FAIL" }).Count
$warn = @($script:Results | Where-Object { $_.Status -eq "WARN" }).Count
Write-Host ""
if ($fail -gt 0) {
    Write-Host ("RESULT: {0} check(s) FAILED, {1} warning(s)." -f $fail, $warn) -ForegroundColor Red
    exit 1
} elseif ($warn -gt 0) {
    Write-Host ("RESULT: working, with {0} warning(s)." -f $warn) -ForegroundColor Yellow
} else {
    Write-Host "RESULT: everything works." -ForegroundColor Green
}
exit 0
