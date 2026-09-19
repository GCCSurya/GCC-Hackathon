# Deploy This dbpulse Application to Azure

**Scope:** Your Linux Azure Web App and Azure PostgreSQL server already exist. This guide only configures and deploys this application to those resources. It does not create Azure resources, create databases, seed data, or change application code.

React is built locally and uploaded with the Flask backend. Azure installs the Python dependencies, and Gunicorn serves the UI and API from the same HTTPS address.

Use **Windows PowerShell 5.1 and Azure CLI**. Run the steps in order, stop if a command fails, and use the same terminal session so variables remain available.

### Configuration taken from this application

These non-secret values come from [start-dbpulse.ps1](start-dbpulse.ps1), [backend/multi_db_monitor.py](backend/multi_db_monitor.py), and [backend/incident_store.py](backend/incident_store.py). They are repository defaults, not a live verification of your Azure resources. Confirm they are still the intended targets before applying them.

| Component | This application's value |
| --- | --- |
| PostgreSQL server | `ilb-3790team39postgres.postgres.database.azure.com` |
| Current database login | `team39admin` |
| Fleet databases | `gcc_banking_core`, `gcc_reconciliation`, `gcc_audit_service` |
| Incident storage | `test.public.incidents` |
| Foundry endpoint | `https://ilb-3790-team39aifoundry.services.ai.azure.com/openai/v1/responses` |
| Foundry model deployment | `gpt-5.6-sol` |
| Flask entry point | `app:app`, run from the backend directory |
| Frontend build | `npm.cmd run build`, producing the `dist` directory |
| Azure startup | `bash startup.sh` |
| Application health route | `/healthz` |

The subscription ID, Web App name, and Web App resource group are not recorded in this repository. Step 1 asks for only those identifiers; passwords and API keys are entered separately and privately in the Azure portal. This procedure does not create or seed anything in the existing PostgreSQL server.

## 1. Select the existing Web App

You need a recent [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows), Node.js 22.12+ on the 22.x line (or another Vite-compatible version), npm, and permission to deploy to the existing Web App.

```powershell
Set-Location (Join-Path $env:USERPROFILE "Documents\Main code\GCC-Hackathon")
az version
node --version
npm.cmd --version
az login
az account list --query "[].{Subscription:name,Id:id}" --output table
$subscriptionId = Read-Host "Subscription ID containing your existing dbpulse Web App"
az account set --subscription $subscriptionId
if ($LASTEXITCODE -ne 0) { throw "Subscription selection failed." }
az webapp list --query "[].{WebApp:name,ResourceGroup:resourceGroup,Kind:kind}" --output table
$resourceGroup = Read-Host "Existing Web App resource group from the list above"
$appName = Read-Host "Existing Web App name from the list above"
az webapp show --resource-group $resourceGroup --name $appName --query "{name:name,host:defaultHostName,state:state,kind:kind}" --output table
if ($LASTEXITCODE -ne 0) { throw "Web App lookup failed. Check the selected subscription and names." }
```

Confirm that the returned Web App is the intended deployment target. Deployment replaces the application on that target and restarts it; retain the previous deployment package if rollback is needed. Do not paste passwords, keys, or publish profiles into chat, source files, or command arguments.

In the portal, verify that the existing Web App uses **Code publishing with a Python runtime on Linux**. Linux alone is not sufficient: a custom-container Web App needs a different deployment workflow. Under **Settings > Configuration / Stack settings**, select a supported Python version, such as **Python 3.12**, if not already configured. This package does not use Node.js as the server runtime.

Keep the existing approved authentication, HTTPS, and network restrictions. The app has no built-in authentication and exposes database previews and incident APIs, so access must be restricted before connecting real data. Your deployment machine must also be allowed to reach the SCM/deployment endpoint.

## 2. Configure startup and application settings

In the Web App's **Settings > Configuration > Stack settings**, set **Startup Command** to:

```text
bash startup.sh
```

For this repository, that script checks for the built frontend and starts the equivalent of the following command when `WEB_CONCURRENCY=1` and `PORT` is unset:

```bash
gunicorn --chdir backend --bind 0.0.0.0:8000 --workers 1 --timeout 120 --access-logfile - --error-logfile - app:app
```

Do not use the local PowerShell launcher on Azure Linux: it expects a Windows virtual environment and interactive password prompts. Do not use `python backend/app.py` as the Azure startup command; that starts Flask's development server.

Apply the startup command and **this application's non-secret settings** with Azure CLI. This overwrites settings of the same name on the selected Web App, so first confirm the targets in the table above:

```powershell
$resourceGroup = "ILB-3790RG-Team39"
$appName = "ilb3790team39python"
az webapp config set --name $appName --resource-group $resourceGroup --startup-file "bash startup.sh" --output none
if ($LASTEXITCODE -ne 0) { throw "Startup configuration failed." }
$dbpulseSettings = @(
    "SCM_DO_BUILD_DURING_DEPLOYMENT=true"
    "WEB_CONCURRENCY=1"
    "PGHOST=ilb-3790team39postgres.postgres.database.azure.com"
    "PGPORT=5432"
    "PGUSER=team39admin"
    "PGSSLMODE=require"
    "INCIDENT_DATABASE=test"
    "AZURE_FOUNDRY_ENDPOINT=https://ilb-3790-team39aifoundry.services.ai.azure.com/openai/v1/responses"
    "AZURE_FOUNDRY_MODEL=gpt-5.6-sol"
    "AZURE_FOUNDRY_USE_MANAGED_IDENTITY=false"
)
az webapp config appsettings set --name $appName --resource-group $resourceGroup --settings $dbpulseSettings --output none
if ($LASTEXITCODE -ne 0) { throw "dbpulse settings update failed." }
az webapp log config --name $appName --resource-group $resourceGroup --docker-container-logging filesystem --output none
```

In **Settings > Environment variables > App settings**, set or confirm the following. Enter the database password privately in the portal, or retain your existing resolved Key Vault reference.

| Name | Value |
| --- | --- |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true`, so Azure installs Python dependencies |
| `WEB_CONCURRENCY` | `1`, because demo state is held in process memory |
| `PGHOST` | `ilb-3790team39postgres.postgres.database.azure.com` |
| `PGPORT` | `5432` |
| `PGUSER` | `team39admin`, the login used by the repository's launcher |
| `PGPASSWORD` | The password for that login, entered privately, or its existing Key Vault reference |
| `PGSSLMODE` | `require` |
| `INCIDENT_DATABASE` | `test` |

The command deliberately does not set passwords or keys. In the portal, add `PGPASSWORD` for the login above and `AZURE_FOUNDRY_KEY` for the Foundry resource below, then select **Apply**. Retain existing valid secret values or resolved references rather than replacing them unnecessarily. Do not paste a JSON export of all settings into chat: it can contain secrets.

`team39admin` is the checked-in launcher default, not a least-privilege recommendation. If your DBA has already provided a dedicated app login or stricter TLS settings, substitute those approved values in the settings array before running it.

Use **App settings**, not the separate Connection strings blade: the code reads these exact variable names. Local terminal settings and [start-dbpulse.ps1](start-dbpulse.ps1) are not automatically transferred to Azure, and the backend does not automatically load an environment file.

Before applying the settings array, check for `POSTGRES_URL` or `DATABASE_URL` in the portal. Those URLs override the `PG*` values. If retaining an approved URL-based configuration, omit the five `PG*` entries from the array. Otherwise remove only stale URL settings when intentionally switching to the concrete `PG*` configuration above.

For this remote-build method, remove `WEBSITE_RUN_FROM_PACKAGE` if set. Review any old pre/post-build commands and remove only those that conflict with this deployment. Do not set up a Vite server or frontend port. The existing [startup.sh](startup.sh) binds to `${PORT:-8000}`; no custom `PORT` or `WEBSITES_PORT` is normally needed for the built-in Python stack.

Use one App Service instance as well as one worker for consistent scenario/timeline state. If the current app scales out, coordinate this constraint with its owner rather than changing a shared plan blindly. Enable Always On if the existing tier supports it. Optionally configure **Monitoring > Health check** with `/healthz`.

Save/apply the settings. Configuration changes restart the app.

## 3. Check access to the existing database

No database creation or seed scripts are required by this deployment procedure. Confirm the existing database environment meets the application's requirements:

- Fleet monitoring expects `gcc_banking_core`, `gcc_reconciliation`, and `gcc_audit_service` on the configured server. Setting `PGDATABASE` does not change these names.
- The incident database selected by `INCIDENT_DATABASE` must contain `public.incidents` with the schema expected by the app. The schema definition is in [mock_data/seed_incident_store.sql](mock_data/seed_incident_store.sql), for reference only; do not rerun it against an initialized database.
- The existing login needs connection and monitoring access to all three fleet databases, read access to public tables for table browsing, and `SELECT`/`INSERT` access to the incident table. Fleet and incident connections share the configured server/login.
- The Web App, not just your laptop or pgAdmin, must have network access to PostgreSQL. For public access, confirm approved firewall rules cover the app's outbound addresses. For private access, confirm existing VNet integration, routing, and private DNS allow TCP 5432.

Find outbound addresses in the Web App's **Properties**, or run:

```powershell
az webapp show --name $appName --resource-group $resourceGroup --query "{current:outboundIpAddresses,possible:possibleOutboundIpAddresses}" --output json
```

Do not open PostgreSQL to all IPs as a workaround. If database names, schema, permissions, or connectivity differ, resolve that prerequisite with the database owner. A successful deployment cannot fix those mismatches; the dashboard may show demo fallback and incident requests may return HTTP 503.

### This application's Foundry settings

The settings command uses the endpoint and model selected by the local launcher. Confirm this existing deployment is accessible from the Web App, and add its API key privately in App settings:

| Name | Value |
| --- | --- |
| `AZURE_FOUNDRY_ENDPOINT` | `https://ilb-3790-team39aifoundry.services.ai.azure.com/openai/v1/responses` |
| `AZURE_FOUNDRY_MODEL` | `gpt-5.6-sol` |
| `AZURE_FOUNDRY_KEY` | Existing API key entered privately, or a resolved Key Vault reference |
| `AZURE_FOUNDRY_USE_MANAGED_IDENTITY` | `false` for the current code on App Service |

The agent's current managed-identity implementation targets Azure VMs and does not work unchanged on App Service, which is why this guide deliberately differs from the local launcher's default. Existing Key Vault references are independent of that limitation. If no valid key is configured or inference fails, the app uses deterministic RAG fallback; a deployed dashboard is not proof that the model is working. No AI or Key Vault resource creation is included in this guide.

## 4. Build and package the application locally

Run from the project root, not from the backend directory:

```powershell
npm.cmd ci
if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
```

The frontend build must produce an index page and assets in the generated `dist` directory. No separate API base URL is needed: the deployed UI uses the same origin as Flask.

Before packaging, open [startup.sh](startup.sh) in VS Code and confirm the status bar shows **LF**, not CRLF. If necessary, select the line-ending indicator, choose LF, and save. Bash can fail on Windows CRLF line endings; `bash startup.sh` avoids needing an executable permission bit but does not fix line endings.

Create a temporary staging folder outside the repository and save the finished ZIP in the project root. Copy only the runtime files; do not upload the Windows virtual environment, Node dependencies, Git history, credentials, data exports, or presentations. Keep generated deployment ZIPs out of source control.

Paste the following as **one command in PowerShell**, from the repository root after the frontend build succeeds. Semicolons separate the commands; visual wrapping in the editor is fine. It stops on errors and prints the ZIP path when complete. Each run replaces `dbpulse-deploy.zip` in the project root; retain a separate known-good copy before packaging if rollback is needed. Keep this terminal open so `$zipPath` is available for archive inspection.

```powershell
$stage = Join-Path (Get-Item $env:TEMP -ErrorAction Stop).FullName ("dbpulse-stage-" + [guid]::NewGuid().ToString("N")); $zipPath = Join-Path (Get-Location).Path "dbpulse-deploy.zip"; New-Item -ItemType Directory -Path $stage -ErrorAction Stop | Out-Null; New-Item -ItemType Directory -Path (Join-Path $stage "backend") -ErrorAction Stop | Out-Null; Copy-Item -Path ".\dist" -Destination $stage -Recurse -ErrorAction Stop; Copy-Item -Path ".\requirements.txt", ".\startup.sh" -Destination $stage -ErrorAction Stop; Get-ChildItem -Path ".\backend" -File -ErrorAction Stop | Where-Object { $_.Extension -eq ".py" -or $_.Name -eq "requirements.txt" } | Copy-Item -Destination (Join-Path $stage "backend") -ErrorAction Stop; Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem; $stream = [System.IO.File]::Open($zipPath, [System.IO.FileMode]::Create); try { $archive = [System.IO.Compression.ZipArchive]::new($stream, [System.IO.Compression.ZipArchiveMode]::Create); try { Get-ChildItem -Path $stage -File -Recurse -ErrorAction Stop | ForEach-Object { $entryName = $_.FullName.Substring($stage.Length + 1).Replace('\', '/'); [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $_.FullName, $entryName) | Out-Null } } finally { $archive.Dispose() } } finally { $stream.Dispose() }; Write-Output "Deployment ZIP: $zipPath"
```

This explicitly writes `/` separators in ZIP entry names for Azure Linux. Windows PowerShell 5.1 `Compress-Archive` can write backslashes, causing Linux to miss files such as `backend/requirements.txt` even when they appear present in a Windows archive viewer.

The ZIP must contain these entries at its root, with **no extra enclosing project or staging directory**:

```text
requirements.txt
startup.sh
backend/
    app.py
    agent.py
    multi_db_monitor.py
    incident_store.py
    rag_engine.py
    ...other Python files...
    requirements.txt
dist/
    index.html
    assets/
```

Inspect the archive and fail early if key files are missing:

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    $entries = @($archive.Entries | ForEach-Object { $_.FullName })
    if (@($entries | Where-Object { $_.Contains('\') }).Count) { throw "ZIP contains Windows path separators. Recreate it using the packaging command above." }
    foreach ($required in @("requirements.txt", "startup.sh", "backend/app.py", "backend/requirements.txt", "dist/index.html")) {
        if ($required -notin $entries) { throw "Missing ZIP entry: $required" }
    }
    $entries
} finally {
    $archive.Dispose()
}
```

The package deliberately excludes the Node package manifest: React is already built, so Azure only needs to detect and build Python. The root [requirements.txt](requirements.txt) includes [backend/requirements.txt](backend/requirements.txt); both must be packaged. Do not deploy the Windows Python environment because Azure installs Linux dependencies.

## 5. Deploy the ZIP

Run from the project root in PowerShell:

```powershell
$resourceGroup = "ILB-3790RG-Team39"
$appName = "ilb3790team39python"
az webapp deploy --resource-group $resourceGroup --name $appName --src-path "dbpulse-deploy.zip" --type zip --output none
if ($LASTEXITCODE -ne 0) { throw "Azure deployment failed; inspect Deployment Center logs." }
$appHost = az webapp show --resource-group $resourceGroup --name $appName --query defaultHostName --output tsv
$baseUrl = "https://$appHost"
Write-Output $baseUrl
```

Use Azure's returned hostname rather than constructing it: some Web Apps use a generated hostname suffix. Deployment restarts the app. Allow the remote build and startup to finish before verifying it.

In the portal, check **Deployment Center > Logs** for dependency installation and deployment success. Check **Monitoring > Log stream** for Gunicorn startup and Python errors. A successful file upload alone is not proof that the application started.

If deployment cannot reach the SCM endpoint, check your network restrictions and the signed-in user's deployment permissions. Use a current Azure CLI with Microsoft Entra authentication; do not broadly enable publishing passwords or expose the SCM endpoint to bypass policy.

## 6. Verify the deployment

Open `$baseUrl` in a browser and sign in with an approved account. In that same authenticated browser session, open the routes below:

| Route/action | Expected result |
| --- | --- |
| `/` | dbpulse dashboard, styles, and interactive controls load |
| `/healthz` | HTTP 200 JSON with `status: ok` |
| `/api/fleet` | JSON fleet response; not proof of live database connectivity |
| `/api/db-health` | HTTP 200 only when all three fleet checks succeed; 503 is expected in demo mode or on connection/query failure |
| `/api/agent-status` | Provider/model configuration; `configured: true` alone does not prove a successful inference request |
| `/api/next-incident-id` | Next incident ID when incident storage is configured; HTTP 503 otherwise |
| Agent/DBA mode switch | Both views render correctly |
| Simulated anomaly control | Scenario updates and diagnosis appears; a live AI deployment must show a live model label rather than deterministic fallback |
| Table explorer | Fleet table inventory and previews load if database setup/permissions succeeded |
| Create Incident | On an approved test database, submit a clearly labeled deployment-test incident and verify its row in `public.incidents` |

Test incident submission creates a real database row. Do not run it against production without approval. Table browsing and successful fleet responses do not prove that the separate incident database is configured.

For an environment where anonymous access is explicitly allowed and there is no sign-in gate, this PowerShell liveness check is also available:

```powershell
Invoke-RestMethod -Uri "$baseUrl/healthz"
```

With required authentication, an unauthenticated command may return 401/403 or sign-in HTML. Use the authenticated browser or an approved API authentication flow; do not disable authentication just to make a smoke test pass.

## 7. Troubleshooting and redeployment

### Recover from a startup 503 without Azure CLI

If the site itself returns 503, open the Web App `ilb3790team39python` in the Azure portal. Under **Settings > Configuration > Stack settings**, replace **Startup Command** with this single line to bypass a CRLF-affected Bash script:

```bash
gunicorn --chdir backend --bind 0.0.0.0:8000 --workers 1 --timeout 120 --access-logfile - --error-logfile - app:app
```

Select **Save/Apply**, then restart the Web App. This restarts the running application and skips the script's frontend-file check. It assumes the built-in Linux Python stack's default port and successfully installed dependencies. Open **Monitoring > Log stream** and check for Gunicorn startup or the first error/traceback. Test `/healthz` in your authenticated browser; expect HTTP 200 with `status: ok`. Do not change database firewall or authentication settings to fix a startup failure.

The source startup script has been converted to LF and the local `dbpulse-deploy.zip` rebuilt. Deploy that corrected archive before returning Startup Command to `bash startup.sh`. A successful local archive check does not verify live Azure startup. If 503 continues, share the first startup error from Log stream with credentials, tokens, and connection strings removed.

Stream runtime logs when needed; press Ctrl+C when finished:

```powershell
az webapp log tail --resource-group $resourceGroup --name $appName
```

| Symptom | Check/fix |
| --- | --- |
| Default Azure landing page | Confirm deployment completed, Python stack is selected, and Startup Command is `bash startup.sh` |
| Startup reports missing frontend | Rebuild React and confirm the ZIP has `dist/index.html` at the expected root level |
| Bash errors mentioning `\r` or invalid options | Convert the startup script to LF, recreate the ZIP, and redeploy |
| `ModuleNotFoundError`, missing Gunicorn, or pip skipped | Include both requirements files, enable `SCM_DO_BUILD_DURING_DEPLOYMENT`, and inspect Oryx logs; never upload a Windows virtual environment |
| 502/503 from the site itself | Inspect startup/import failures, Gunicorn bind address, runtime version, memory pressure, and build logs |
| Dashboard loads but database health is 503 | Check hostname, Key Vault resolution, credentials, firewall/private DNS, all three database names, and monitoring/table grants |
| Incident endpoints return 503 | Check `INCIDENT_DATABASE`, table initialization, `SELECT`/`INSERT` grants, and duplicate incident IDs |
| AI falls back despite `configured: true` | Check real deployment name, endpoint, key validity, quota/network access, and runtime logs; the current managed-identity path is VM-specific |
| Key Vault reference is unresolved | Check managed identity, RBAC/access policy, secret URI, network/DNS access, and reference status in the portal |
| Scenario/timeline changes appear inconsistent | Confirm `WEB_CONCURRENCY=1` and one App Service instance; restarting resets in-memory data |
| Sign-in page or 401/403 during checks | Confirm intended user assignment, tenant, access restrictions, and authenticated browser session |
| Frontend looks stale | Rebuild and redeploy a fresh ZIP, then refresh the browser; verify the new asset bundle is served |

Do not hard-code `/home/site/wwwroot` into the startup command. Python remote builds can run from an extracted application path under `/tmp`; use project-relative paths as the existing startup script does.

For updates, repeat sections 4-6 with a fresh ZIP. To roll back, deploy your retained known-good package and verify it again. This does not reverse database changes or App Service settings. No resource deletion or database reset is part of this procedure.

## References

- [Configure Python on Linux App Service](https://learn.microsoft.com/en-us/azure/app-service/configure-language-python)
- [ZIP deployment and remote build](https://learn.microsoft.com/en-us/azure/app-service/deploy-zip)

These instructions prepare deployment to your existing resources; no Azure deployment has been executed as part of writing this document.