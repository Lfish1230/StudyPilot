param(
    [string]$OutputPath = (Join-Path $PSScriptRoot "sources\xv6-chinese.pdf")
)

$ErrorActionPreference = "Stop"
$sourceUrl = "https://lihaoran.work/wp-content/uploads/2023/08/xv6-chinese.pdf"
$expectedSha256 = "51D28581A043C438CF91F21B66DC3EBA914404CC48CDD8F763AB15C10DD36BF7"
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $resolvedOutput
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

Invoke-WebRequest -Uri $sourceUrl -OutFile $resolvedOutput
$actualSha256 = (Get-FileHash -LiteralPath $resolvedOutput -Algorithm SHA256).Hash
if ($actualSha256 -ne $expectedSha256) {
    Remove-Item -LiteralPath $resolvedOutput -Force
    throw "SHA-256 mismatch. Expected $expectedSha256, got $actualSha256. The downloaded file was removed."
}

Write-Host "Verified source PDF: $resolvedOutput"
Write-Host "SHA-256: $actualSha256"
