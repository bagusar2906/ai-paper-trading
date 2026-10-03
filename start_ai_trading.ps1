<#
Starts the paper-trading API with the AI Agent strategy available.

Usage:
  .\start_ai_trading.ps1
  .\start_ai_trading.ps1 -Model "your-model-or-combo"

The API key is kept only in this PowerShell process and is never written to
disk. Before starting, create and activate an "AI Agent (OpenAI)" strategy at
http://localhost:8000/ui/strategy.html.
#>
[CmdletBinding()]
param(
    # OmniRoute defaults. Override Model if your OmniRoute dashboard uses a
    # different model alias or routing combo.
   # [string]$Model = "gpt-5.5",
    [string]$Model = "my-combo",
    [int]$TimeoutSeconds = 20,
    [string]$ApiBaseUrl = "http://localhost:20128/v1"
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($env:AI_API_KEY) -and
    [string]::IsNullOrWhiteSpace($env:OMNIROUTE_API_KEY) -and
    [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    $secureKey = Read-Host "AI gateway API key" -AsSecureString
    $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        # Keep the OmniRoute-compatible name so the same key can be used by
        # the launcher and other local OmniRoute clients.
        $env:OMNIROUTE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }
}

if ([string]::IsNullOrWhiteSpace($env:AI_API_KEY) -and
    [string]::IsNullOrWhiteSpace($env:OMNIROUTE_API_KEY) -and
    [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    throw "An AI gateway API key is required to run the AI Agent strategy."
}

$env:OPENAI_TRADING_MODEL = $Model
$env:OPENAI_TRADING_TIMEOUT_SECONDS = $TimeoutSeconds.ToString()
$env:AI_API_BASE_URL = $ApiBaseUrl.TrimEnd("/")

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $python = $venvPython
}
else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw "Python was not found. Create .venv or install Python, then run this script again."
    }
    $python = $pythonCommand.Source
}

Set-Location $projectRoot
Write-Host "Starting AI paper trading at http://localhost:8000/ui/"
Write-Host "Gateway: $env:AI_API_BASE_URL | model: $env:OPENAI_TRADING_MODEL | timeout: $env:OPENAI_TRADING_TIMEOUT_SECONDS seconds"
& $python run_api.py
