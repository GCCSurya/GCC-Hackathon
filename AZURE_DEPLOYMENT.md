# Deploy dbpulse to an Existing Azure Web App

This guide deploys the current application to an **existing Linux App Service Web App (Code publishing, Python runtime)** and connects it to your **existing Azure PostgreSQL server and databases**. It does not create Azure resources, databases, tables, or seed data. Windows-hosted and custom-container Web Apps require a different deployment workflow.

React is built locally into `dist`. Azure installs the Python dependencies, and Gunicorn serves the dashboard and API from the same HTTPS origin. No Vite server, separate frontend hosting, or API URL configuration is needed.

## 1. Confirm Prerequisites and Select the Target

Use Windows PowerShell 5.1 from the repository root, with Azure CLI, Node.js 20.19+ or 22.12+ (or a newer Vite-compatible release), and npm installed. Keep the same terminal open for all steps. Stop on any error.

```powershell
$ErrorActionPreference = "Stop"
if (-not (Test-Path .\startup.sh)) { throw "Open a terminal in the repository root first." }
az version
node --version
npm.cmd --version
az login
if ($LASTEXITCODE -ne 0) { throw "Azure login failed." }
az account list --query "[].{Subscription:name,Id:id}" --output table
$subscriptionId = Read-Host "Subscription ID containing the existing Web App"
az account set --subscription $subscriptionId
if ($LASTEXITCODE -ne 0) { throw "Subscription selection failed." }
az webapp list --query "[].{WebApp:name,ResourceGroup:resourceGroup,Kind:kind}" --output table
$resourceGroup = Read-Host "Existing Web App resource group"
$appName = Read-Host "Existing Web App name"
az webapp show --resource-group $resourceGroup --name $appName --query "{name:name,host:defaultHostName,state:state,kind:kind}" --output table
if ($LASTEXITCODE -ne 0) { throw "Web App lookup failed." }
az webapp config show --resource-group $resourceGroup --name $appName --query "{runtime:linuxFxVersion,startup:appCommandLine,alwaysOn:alwaysOn}" --output table
if ($LASTEXITCODE -ne 0) { throw "Runtime lookup failed." }
```

Confirm the selected target before proceeding: deployment replaces its application and restarts it. Retain the previous known-good deployment package and configuration for rollback. These commands target the main site, not a deployment slot; use your existing slot/release process if required.

In the Azure portal, confirm **Settings > Configuration > Stack settings** uses a supported Python runtime, such as Python 3.12, on Linux. This application does not use the Node.js server stack.

The application has **no built-in authentication**. Preserve or configure approved App Service Authentication, HTTPS-only access, and network restrictions before exposing real data. Your deployment machine must also be allowed to reach the SCM/deployment endpoint. Do not disable these protections to make deployment or smoke tests pass.

## 2. Check Existing Database Access

The current backend expects the following on the same PostgreSQL server:

| Purpose | Required existing database/object |
| --- | --- |
| Fleet monitoring | `gcc_banking_core`, `gcc_reconciliation`, `gcc_audit_service` |
| Incident persistence | `public.incidents` in `INCIDENT_DATABASE` (default: `test`) |

The three fleet names are defined in [backend/multi_db_monitor.py](backend/multi_db_monitor.py); setting `PGDATABASE` or changing the database name in a connection URL does not rename this fleet. Incident connections use `INCIDENT_DATABASE` even when a connection URL is supplied.

Confirm with the database owner:

- The app login can connect to all three fleet databases and read the PostgreSQL monitoring views needed for telemetry. Use an approved monitoring role with sufficient visibility, not a superuser solely for convenience.
- Table browsing requires access to the relevant public tables. Monitoring access alone does not grant permission to preview business data.
- Incident storage has compatible columns, types, required defaults, schema access, `INSERT` privileges for inserted columns, `SELECT` for incident-ID lookup, and any required sequence privileges. See [backend/incident_store.py](backend/incident_store.py) and [mock_data/seed_incident_store.sql](mock_data/seed_incident_store.sql) as schema references only. Do not rerun seed scripts against the existing database.
- The **Web App itself** can reach the database over TCP 5432. A working pgAdmin connection on your laptop does not prove this.

For a private PostgreSQL endpoint, verify existing Web App VNet integration, routing, and private DNS resolution. For public access, verify approved database firewall rules include the app's applicable outbound IP addresses. Inspect them with:

```powershell
az webapp show --resource-group $resourceGroup --name $appName --query "{current:outboundIpAddresses,possible:possibleOutboundIpAddresses}" --output json
if ($LASTEXITCODE -ne 0) { throw "Outbound address lookup failed." }
```

Do not open PostgreSQL to all IP addresses as a workaround. Resolve missing databases, schema, permissions, or network access with the existing resource owners; this deployment does not provision them.

## 3. Configure the Web App

### Startup and Non-Secret Settings

The current [startup.sh](startup.sh) checks for `dist/index.html` and runs:

```bash
gunicorn --chdir backend --bind "0.0.0.0:${PORT:-8000}" --workers 1 --timeout 120 --access-logfile - --error-logfile - app:app
```

Use **`bash startup.sh`** as the Startup Command. Do not use `npm start`, the Windows credential launcher, or Flask's development server on Azure.

Enter your actual existing database host and approved login below. Use the server's fully qualified hostname from Azure, not a hostname copied from an old deployment guide. Values in [start-dbpulse.ps1](start-dbpulse.ps1) are local defaults and are not transferred to Azure.

Before applying this configuration, inspect App settings in the portal for `POSTGRES_URL` or `DATABASE_URL`. The backend chooses `POSTGRES_URL` first, then `DATABASE_URL`, ahead of the `PG*` settings. For the `PG*` workflow below, remove only stale URL settings after confirming that switch is intended. If retaining an approved URL configuration, omit the `PGHOST`, `PGPORT`, `PGUSER`, and `PGSSLMODE` entries below and manage the URL privately, including its TLS options.

```powershell
$pgHost = Read-Host "Existing PostgreSQL server FQDN"
$pgUser = Read-Host "Approved PostgreSQL app login"
$incidentDatabase = Read-Host "Existing incident database name (usually test)"
if ([string]::IsNullOrWhiteSpace($pgHost) -or [string]::IsNullOrWhiteSpace($pgUser) -or [string]::IsNullOrWhiteSpace($incidentDatabase)) {
    throw "Host, login, and incident database are required."
}
az webapp config set --resource-group $resourceGroup --name $appName --startup-file "bash startup.sh" --output none
if ($LASTEXITCODE -ne 0) { throw "Startup configuration failed." }
$settings = @(
    "SCM_DO_BUILD_DURING_DEPLOYMENT=true"
    "AGENT_PROVIDER=deterministic"
    "DBPULSE_ALLOW_DEMO=0"
    "PGHOST=$pgHost"
    "PGPORT=5432"
    "PGUSER=$pgUser"
    "PGSSLMODE=require"
    "INCIDENT_DATABASE=$incidentDatabase"
)
az webapp config appsettings set --resource-group $resourceGroup --name $appName --settings $settings --output none
if ($LASTEXITCODE -ne 0) { throw "Application settings update failed." }
az webapp log config --resource-group $resourceGroup --name $appName --docker-container-logging filesystem --output none
if ($LASTEXITCODE -ne 0) { throw "Log configuration failed." }
```

These commands overwrite settings of the same name. The baseline intentionally selects deterministic guidance and disables simulation. If you need an existing Foundry integration, apply the optional provider settings below afterward. Preserve stricter approved TLS configuration if your environment already uses it.

### Secrets and Platform Settings

In **Settings > Environment variables > App settings** (portal labels may vary):

- Add `PGPASSWORD` privately for the selected login, or retain an existing resolved Key Vault reference. Never put passwords, API keys, publish profiles, or secret connection URLs in source files, ZIPs, command arguments, or chat.
- Use **App settings**, not the separate Connection strings section. The code reads these exact environment variable names and does not automatically load an environment file.
- The encrypted Windows profile used by [start-dbpulse.ps1](start-dbpulse.ps1) cannot be used on Azure Linux. Do not upload it or the local virtual environment.
- Remove `WEBSITE_RUN_FROM_PACKAGE` if present when using this remote-build ZIP workflow. Review conflicting custom build commands with the app owner. Azure must install Python dependencies from the root [requirements.txt](requirements.txt), which includes [backend/requirements.txt](backend/requirements.txt).
- Leave `PORT` unset unless your platform configuration explicitly requires it; the script defaults to port 8000. `WEBSITES_PORT` is not needed for the built-in Python stack.

Save/apply settings. Configuration changes restart the application.

### Worker, Scaling, and Monitoring Limits

[startup.sh](startup.sh) **hard-codes one Gunicorn worker**; `WEB_CONCURRENCY` does not change it. Use one Web App instance for consistent in-memory timeline and scenario state. Coordinate any scale-out changes with the app owner; do not change a shared App Service plan blindly. Restarts clear in-memory state, but persisted PostgreSQL incidents remain.

Enable **Always On** if supported by the existing tier. It keeps the web process available but **does not start the background monitor**. Unlike the Windows launcher, Azure's current startup script does not run [backend/monitor_worker.py](backend/monitor_worker.py) or [backend/run_dashboard.py](backend/run_dashboard.py). Dashboard/API requests drive telemetry polling. Continuous monitoring without browser/API traffic requires a separately managed worker deployment, outside this web-only procedure.

For App Service **Health check**, `/healthz` is a cheap liveness endpoint. Use `/api/readiness` as the deployment acceptance check for actual database readiness. Choosing readiness as the platform health-check path also couples instance health to database outages and runs database queries on each probe; coordinate that choice and authentication behavior with the app owner.

### Optional Azure AI Foundry

The default `AGENT_PROVIDER=deterministic` uses fixed rule-based runbook guidance. It needs **no AI endpoint, API key, or managed identity**, and is not an LLM or retrieval-generated answer.

To use an existing, approved Azure AI Foundry model deployment, configure:

| App setting | Value |
| --- | --- |
| `AGENT_PROVIDER` | `azure` (required to leave deterministic mode) |
| `AZURE_FOUNDRY_ENDPOINT` | Your existing model endpoint, for example `https://<resource>.services.ai.azure.com/openai/v1/responses` |
| `AZURE_FOUNDRY_MODEL` | Your actual model deployment name |
| `AZURE_FOUNDRY_KEY` | API key entered privately or an existing resolved Key Vault reference |
| `AZURE_FOUNDRY_USE_MANAGED_IDENTITY` | `false` for this App Service workflow |

The current identity code in [backend/agent.py](backend/agent.py) calls the Azure VM metadata endpoint, not App Service's identity endpoint. Do not select managed-identity inference on App Service without updating that implementation. App Service Key Vault references are separate and can still use the Web App identity.

Confirm endpoint networking and authorization, and approve sending diagnosis context to the model. Inference failures fall back to deterministic guidance. `/api/agent-status` reports configuration and the last provider error, not proof of a successful model call. Verify an actual diagnosis and its returned model label when cloud inference is required.

## 4. Build and Package Locally

Run from the repository root. If a lockfile exists, use it; otherwise install dependencies to generate one before building:

```powershell
if (Test-Path .\package-lock.json) {
    npm.cmd ci
} else {
    npm.cmd install
}
if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
```

Create the deployment archive as `dbpulse-deploy.zip` in the repository root. The temporary staging directory contains only the built UI, Python runtime files, and dependency/startup files. The command normalizes the **staged copy** of the shell script to LF, leaving the source unchanged, and writes Linux-compatible ZIP entry separators.

```powershell
$stage = Join-Path $env:TEMP ("dbpulse-stage-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path (Join-Path $stage "backend") -Force | Out-Null
$stage = (Get-Item $stage).FullName
$zipPath = Join-Path (Get-Location).Path "dbpulse-deploy.zip"
Copy-Item -Path .\dist -Destination $stage -Recurse
Copy-Item -Path .\requirements.txt -Destination $stage
Get-ChildItem .\backend -File |
    Where-Object { ($_.Extension -eq ".py" -and $_.Name -notlike "test_*") -or $_.Name -eq "requirements.txt" } |
    Copy-Item -Destination (Join-Path $stage "backend")
$startupSource = (Resolve-Path .\startup.sh).Path
$startupText = [System.IO.File]::ReadAllText($startupSource).Replace("`r`n", "`n")
[System.IO.File]::WriteAllText((Join-Path $stage "startup.sh"), $startupText, [System.Text.UTF8Encoding]::new($false))
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    Get-ChildItem $stage -File -Recurse | ForEach-Object {
        $entryName = $_.FullName.Substring($stage.Length + 1).Replace('\', '/')
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $_.FullName, $entryName) | Out-Null
    }
} finally {
    $archive.Dispose()
}
$archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    $entries = @($archive.Entries | ForEach-Object { $_.FullName })
    if (@($entries | Where-Object { $_.Contains('\') }).Count) { throw "ZIP contains Windows separators." }
    foreach ($required in @("requirements.txt", "startup.sh", "backend/requirements.txt", "backend/app.py", "backend/agent.py", "backend/incident_store.py", "backend/multi_db_monitor.py", "backend/rag_engine.py", "dist/index.html")) {
        if ($required -notin $entries) { throw "Missing ZIP entry: $required" }
    }
    $entries
} finally {
    $archive.Dispose()
}
Write-Output "Deployment ZIP: $zipPath"
```

The archive must have `requirements.txt`, `startup.sh`, `backend/`, and `dist/` directly at its root, **without an enclosing project folder**. Do not ZIP the whole repository. The Node manifest is deliberately omitted so remote build detects Python; the frontend is already compiled. Local credentials, `.venv`, `node_modules`, `.git`, mock data, and environment files must not be included.

## 5. Deploy to the Selected Web App

This publishes to the target selected in step 1. Do not reassign those variables to names copied from an earlier guide.

```powershell
az webapp deploy --resource-group $resourceGroup --name $appName --src-path $zipPath --type zip --output none
if ($LASTEXITCODE -ne 0) { throw "Deployment failed. Check Deployment Center logs." }
$appHost = az webapp show --resource-group $resourceGroup --name $appName --query defaultHostName --output tsv
if ($LASTEXITCODE -ne 0) { throw "Web App hostname lookup failed." }
$baseUrl = "https://$appHost"
Write-Output "Open $baseUrl"
```

Use the returned hostname rather than constructing it. In the portal, check **Deployment Center > Logs** for successful remote Python dependency installation, then **Monitoring > Log stream** for Gunicorn startup. An uploaded ZIP alone does not prove a healthy deployment.

If SCM access fails, verify network restrictions and your signed-in identity's deployment permissions. Use a current Azure CLI and the approved Microsoft Entra deployment flow; do not broadly enable publishing passwords or expose SCM as a workaround.

## 6. Verify Before Accepting the Deployment

Open `$baseUrl` and sign in through the approved authentication mechanism. Check the following in that authenticated browser session:

| Route/action | Expected result |
| --- | --- |
| `/` | Dashboard, styles, and assets load; Agent and DBA views work |
| `/healthz` | HTTP 200, `{"status":"ok"}`; proves only web-process liveness |
| `/api/readiness` | HTTP 200, `success: true`, `connection.state: connected`, and `incident_storage.state: connected` |
| `/api/db-health` | HTTP 200 with connected fleet telemetry; 503 on unavailable fleet reads |
| `/api/fleet` | Three databases with live telemetry; HTTP 200 alone is not a readiness guarantee |
| `/api/agent-status` | Default provider is `deterministic rules`, or the explicitly configured cloud provider |
| `/api/next-incident-id` | An ID formatted as `INC-` plus eight hexadecimal characters; does not insert an incident |
| Table explorer | Inventory and approved table previews load for the selected fleet database |

**Require `/api/readiness` to pass.** Gunicorn imports `app:app`, so it does not execute the live startup guard inside `if __name__ == "__main__"` in [backend/app.py](backend/app.py). The web process can start successfully while database configuration is missing or broken. Live-mode failures show unavailable telemetry, not invented healthy data or automatic demo fallback.

Readiness performs read-only checks; it does not insert an incident. Row-security policies, constraints, and triggers can still reject a real write. If explicitly approved, submit a clearly labeled test incident through the UI and verify it in the selected incident database. This creates a real row. Successful UI rendering, table browsing, or ID allocation is not proof of incident persistence.

Demo controls are disabled by `DBPULSE_ALLOW_DEMO=0`; do not expect simulated anomaly buttons as part of normal verification. For an explicitly approved demo environment only, set `DBPULSE_ALLOW_DEMO=1` and restart. Failed real database reads still remain unavailable, and demo mode never substitutes for persisted incident receipts.

For environments that explicitly permit unauthenticated probes, these checks are available; otherwise use an authenticated browser or approved API authentication flow:

```powershell
Invoke-RestMethod -Uri "$baseUrl/healthz"
Invoke-RestMethod -Uri "$baseUrl/api/readiness"
```

A 401/403 or sign-in page may be the authentication boundary, not an application failure. Do not disable authentication to test.

## 7. Troubleshoot and Redeploy

Stream runtime logs as needed, then press Ctrl+C:

```powershell
az webapp log tail --resource-group $resourceGroup --name $appName
```

| Symptom | Check |
| --- | --- |
| Startup 503 or Gunicorn missing | Python/Linux Code stack, remote build logs, `SCM_DO_BUILD_DURING_DEPLOYMENT=true`, both requirements files, and incompatible package/run-from-package settings |
| `Missing dist/index.html` | Frontend build succeeded; ZIP has no enclosing directory; `dist` was included |
| Bash errors containing `\r` or `bad interpreter` | Recreate and redeploy using the packaging block, which normalizes staged shell line endings |
| `/healthz` passes but readiness is 503 | Inspect `connection` versus `incident_storage` in readiness; check effective settings, secrets/Key Vault resolution, URL overrides, network/DNS, database names, schema, and privileges |
| Fleet works but incident submission is 503 | Separate incident database configuration, schema/defaults, insert/sequence permissions, row-security policies, and triggers |
| Rules appear instead of cloud output | `AGENT_PROVIDER`, endpoint/model/key, `AZURE_FOUNDRY_USE_MANAGED_IDENTITY=false`, provider errors, and inference network access |
| No monitoring after closing browser | Expected for this web-only startup; Always On does not launch the standalone monitoring worker |
| Inconsistent/reset timeline or simulation | Multiple instances/workers or process restart; state is in memory |

For redeployment, repeat build, package, deploy, and readiness verification. To roll back, deploy your retained known-good ZIP to the same target and restore any associated configuration changes through the approved process. Do not restore or reseed databases as part of an application rollback. Share only sanitized errors when requesting help, never secret-bearing settings exports or connection strings.