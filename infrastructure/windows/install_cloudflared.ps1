$ErrorActionPreference = "Stop"

$toolDirectory = Join-Path $PSScriptRoot "cloudflared"
$executable = Join-Path $toolDirectory "cloudflared.exe"
$architecture = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") {
    "arm64"
} else {
    "amd64"
}
$downloadUrl = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/" +
    "cloudflared-windows-$architecture.exe"
)

New-Item -ItemType Directory -Path $toolDirectory -Force | Out-Null
if (Test-Path -LiteralPath $executable) {
    $existingSignature = Get-AuthenticodeSignature -LiteralPath $executable
    if (
        $existingSignature.Status -eq "Valid" -and
        $existingSignature.SignerCertificate.Subject -like '*O="Cloudflare, Inc."*'
    ) {
        Write-Host "Verified Cloudflare Tunnel client is already available."
        & $executable --version
        exit 0
    }
    Remove-Item -LiteralPath $executable -Force
}
Write-Host "Downloading official Cloudflare Tunnel client..."
Invoke-WebRequest -Uri $downloadUrl -OutFile $executable
$signature = Get-AuthenticodeSignature -LiteralPath $executable
if (
    $signature.Status -ne "Valid" -or
    $signature.SignerCertificate.Subject -notlike '*O="Cloudflare, Inc."*'
) {
    Remove-Item -LiteralPath $executable -Force
    throw "Downloaded cloudflared binary did not have a valid Cloudflare signature."
}
& $executable --version
Write-Host "Verified cloudflared is ready at $executable"
