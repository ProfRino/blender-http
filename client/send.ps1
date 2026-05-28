<#
.SYNOPSIS
    Send a Python script to Blender HTTP.

.EXAMPLE
    .\send.ps1 -Script ..\examples\01_simple_cube.py
    .\send.ps1 -Script ..\examples\02_generator_pavilion.py -Stream
#>
param(
    [Parameter(Mandatory = $true)][string]$Script,
    [string]$Url = "http://127.0.0.1:9876",
    [switch]$Stream
)

if (-not (Test-Path $Script)) { throw "Script not found: $Script" }
$body = Get-Content $Script -Raw

if (-not $Stream) {
    try {
        $r = Invoke-WebRequest -Uri $Url -Method POST -Body $body -ContentType "text/plain" -TimeoutSec 600 -UseBasicParsing
        $r.Content
    } catch {
        if ($_.Exception.Response) {
            $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
            $reader.ReadToEnd()
        } else { throw }
    }
    return
}

# Async + SSE stream
$resp = Invoke-RestMethod -Uri "$Url/jobs" -Method POST -Body $body -ContentType "text/plain" -TimeoutSec 30
$jid = $resp.job_id
Write-Host "job_id=$jid" -ForegroundColor DarkGray

Add-Type -AssemblyName System.Net.Http
$client = [System.Net.Http.HttpClient]::new()
$client.Timeout = [System.TimeSpan]::FromHours(1)
$req = [System.Net.Http.HttpRequestMessage]::new("GET", "$Url/jobs/$jid/stream")
$response = $client.SendAsync($req, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
$stream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
$reader = [System.IO.StreamReader]::new($stream)
$evt = ""
try {
    while (-not $reader.EndOfStream) {
        $line = $reader.ReadLine()
        if ($null -eq $line) { continue }
        if ($line.StartsWith("event:")) { $evt = $line.Substring(6).Trim() }
        elseif ($line.StartsWith("data:")) {
            $data = $line.Substring(5).Trim()
            Write-Host "[$evt] $data"
            if ($evt -in @("completed", "failed", "cancelled")) { break }
        }
    }
} finally {
    $reader.Dispose()
    $client.Dispose()
}
