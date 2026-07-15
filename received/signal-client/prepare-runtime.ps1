$ErrorActionPreference = 'Stop'

$SignalVersion = '0.14.6'
$JavaArchive = 'zulu25.34.17-ca-jre25.0.3-win_x64.zip'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runtime = Join-Path $Root 'runtime'
$Downloads = Join-Path $Runtime 'downloads'
$SignalArchive = Join-Path $Downloads "signal-cli-$SignalVersion.tar.gz"
$JavaZip = Join-Path $Downloads $JavaArchive

New-Item -ItemType Directory -Path $Downloads -Force | Out-Null

if (-not (Test-Path $SignalArchive)) {
    Invoke-WebRequest -Uri "https://github.com/AsamK/signal-cli/releases/download/v$SignalVersion/signal-cli-$SignalVersion.tar.gz" -OutFile $SignalArchive
}
if (-not (Test-Path $JavaZip)) {
    Invoke-WebRequest -Uri "https://cdn.azul.com/zulu/bin/$JavaArchive" -OutFile $JavaZip
}

$SignalDestination = Join-Path $Root 'signal-cli'
if (-not (Test-Path $SignalDestination)) {
    tar -xzf $SignalArchive -C $Root
    $ExtractedSignal = Join-Path $Root "signal-cli-$SignalVersion"
    if (-not (Test-Path $ExtractedSignal)) { throw 'Unexpected signal-cli archive layout.' }
    Move-Item -LiteralPath $ExtractedSignal -Destination $SignalDestination
}

$JavaDestination = Join-Path $Runtime 'java'
if (-not (Test-Path $JavaDestination)) {
    New-Item -ItemType Directory -Path $JavaDestination | Out-Null
    Expand-Archive -LiteralPath $JavaZip -DestinationPath $JavaDestination
}

& (Join-Path $Root 'signal-cli-wrapper.bat') --version
if ($LASTEXITCODE -ne 0) { throw 'signal-cli runtime verification failed.' }
Write-Host 'Signal runtime is ready.'
