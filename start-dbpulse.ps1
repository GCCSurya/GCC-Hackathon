param(
    [ValidateSet("ManagedIdentity", "ApiKey")]
    [string]$Authentication = "ManagedIdentity"
)

$ErrorActionPreference = "Stop"

# Remove inherited AI credentials before selecting an explicit authentication mode.
Remove-Item Env:AZURE_FOUNDRY_KEY -ErrorAction SilentlyContinue
Remove-Item Env:AZURE_OPENAI_KEY -ErrorAction SilentlyContinue
$env:AZURE_FOUNDRY_ENDPOINT = "https://ilb-3790-team39aifoundry.services.ai.azure.com/openai/v1/responses"
$env:AZURE_FOUNDRY_MODEL = "gpt-5.6-sol"

if ($Authentication -eq "ManagedIdentity") {
    $env:AZURE_FOUNDRY_USE_MANAGED_IDENTITY = "true"
} else {
    $env:AZURE_FOUNDRY_USE_MANAGED_IDENTITY = "false"
    $secureKey = Read-Host "Enter a newly rotated Azure AI Foundry API key" -AsSecureString
    $env:AZURE_FOUNDRY_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
    if ([string]::IsNullOrWhiteSpace($env:AZURE_FOUNDRY_KEY)) {
        throw "An Azure AI Foundry API key is required for ApiKey authentication."
    }
}

if (-not $env:PGHOST) { $env:PGHOST = "ilb-3790team39postgres.postgres.database.azure.com" }
if (-not $env:PGPORT) { $env:PGPORT = "5432" }
if (-not $env:PGUSER) { $env:PGUSER = "team39admin" }
if (-not $env:PGSSLMODE) { $env:PGSSLMODE = "require" }

if (-not $env:PGPASSWORD) {
    $credential = Get-Credential -UserName $env:PGUSER -Message "Enter the PostgreSQL password"
    $env:PGPASSWORD = $credential.GetNetworkCredential().Password
}

try {
    & "$PSScriptRoot\.venv\Scripts\python.exe" "$PSScriptRoot\backend\app.py"
} finally {
    Remove-Item Env:AZURE_FOUNDRY_KEY -ErrorAction SilentlyContinue
}