$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$environmentPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
try {
    if (-not (Test-Path -LiteralPath $environmentPython)) {
        $interpreter = $null
        foreach ($version in @('-3.12', '-3.13', '-3.11', '-3.10', '-3.14')) {
            $resolved = & py $version -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved) {
                $interpreter = $resolved.Trim()
                break
            }
        }
        if (-not $interpreter) { throw 'Install Python 3.10+ / Zainstaluj Python 3.10+.' }
        & $interpreter -m venv (Join-Path $PSScriptRoot '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the application environment.' }
    }
    & $environmentPython -c 'import wx,numpy,sounddevice,mido,rtmidi,scipy,accessible_output2' 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Installing application dependencies / Instalowanie bibliotek...'
        & $environmentPython -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed / Blad instalacji bibliotek.' }
    }
    & $environmentPython -B (Join-Path $PSScriptRoot 'run.py')
    exit $LASTEXITCODE
} catch {
    Write-Host $_.Exception.Message
    exit 1
}
