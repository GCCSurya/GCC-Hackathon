param(
    [ValidateSet("Deterministic", "ManagedIdentity", "ApiKey")]
    [string]$Authentication = "Deterministic",
    [switch]$ResetCredentials,
    [switch]$ConfigureOnly
)

$ErrorActionPreference = "Stop"

if ($env:POSTGRES_URL -or $env:DATABASE_URL) {
    throw "This launcher uses a saved PG* profile. Remove POSTGRES_URL and DATABASE_URL from this terminal first to avoid overriding it."
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Project Python environment is missing. Install backend dependencies in .venv first." }
$port = if ($env:PORT) { [int]$env:PORT } else { 5000 }
if (-not $ConfigureOnly -and (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)) {
    throw "Port $port is already occupied. Keep the existing dashboard running, or stop it with Ctrl+C before restarting. Use -ConfigureOnly to save credentials without starting another server."
}

$profilePath = Join-Path $env:LOCALAPPDATA "dbpulse\postgres.clixml"
$profile = $null
if (-not $ResetCredentials -and (Test-Path $profilePath)) {
    try { $profile = Import-Clixml -Path $profilePath } catch {
        throw "Cannot decrypt the saved database profile for this Windows user. Run .\start-dbpulse.ps1 -ResetCredentials to replace it."
    }
}
$defaults = @{
    PGHOST = "ilb-3790team39postgres.postgres.database.azure.com"
    PGPORT = "5432"
    PGUSER = "team39admin"
    PGSSLMODE = "require"
    INCIDENT_DATABASE = "test"
}
foreach ($name in $defaults.Keys) {
    if (-not [Environment]::GetEnvironmentVariable($name, "Process")) {
        $value = if ($profile -and $profile.$name) { $profile.$name } else { $defaults[$name] }
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}
if ($ResetCredentials) { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
if (-not $env:PGPASSWORD -and $profile -and $profile.PGHOST -eq $env:PGHOST -and $profile.PGPORT -eq $env:PGPORT -and $profile.PGUSER -eq $env:PGUSER) {
    $env:PGPASSWORD = $profile.Credential.GetNetworkCredential().Password
}
if (-not $env:PGPASSWORD) {
    $credential = Get-Credential -UserName $env:PGUSER -Message "Enter PostgreSQL credentials to save encrypted for this Windows user"
    if (-not $credential) { throw "Database setup cancelled; no demo server was started." }
    $env:PGPASSWORD = $credential.GetNetworkCredential().Password
}
if ([string]::IsNullOrWhiteSpace($env:PGPASSWORD)) { throw "A PostgreSQL password is required." }

Push-Location (Join-Path $PSScriptRoot "backend")
try {
    & $python -c 'from app import require_live_database; require_live_database()'
    if ($LASTEXITCODE -ne 0) { throw "Live database check failed. No profile was saved and no server was started. To replace saved credentials, use -ResetCredentials." }
} finally {
    Pop-Location
}

$savedProfile = @{}
foreach ($name in $defaults.Keys) { $savedProfile[$name] = [Environment]::GetEnvironmentVariable($name, "Process") }
$savedProfile.Credential = [pscredential]::new($env:PGUSER, (ConvertTo-SecureString $env:PGPASSWORD -AsPlainText -Force))
New-Item -ItemType Directory -Path (Split-Path $profilePath) -Force | Out-Null
$savedProfile | Export-Clixml -Path $profilePath
Write-Host "Live database profile verified and saved using Windows user-bound encryption."
if ($ConfigureOnly) { return }

# Remove inherited AI credentials before selecting an explicit provider mode.
Remove-Item Env:AZURE_FOUNDRY_KEY -ErrorAction SilentlyContinue
Remove-Item Env:AZURE_OPENAI_KEY -ErrorAction SilentlyContinue

if ($Authentication -eq "Deterministic") {
    $env:AGENT_PROVIDER = "deterministic"
    Remove-Item Env:AZURE_FOUNDRY_ENDPOINT -ErrorAction SilentlyContinue
    Remove-Item Env:AZURE_FOUNDRY_MODEL -ErrorAction SilentlyContinue
    Remove-Item Env:AZURE_FOUNDRY_USE_MANAGED_IDENTITY -ErrorAction SilentlyContinue
} else {
    $env:AGENT_PROVIDER = "azure"
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
}

try {
    & $python -u "$PSScriptRoot\backend\run_dashboard.py"
    if ($LASTEXITCODE -ne 0) { throw "Dashboard supervisor exited with code $LASTEXITCODE." }
} finally {
    Remove-Item Env:AZURE_FOUNDRY_KEY -ErrorAction SilentlyContinue
}