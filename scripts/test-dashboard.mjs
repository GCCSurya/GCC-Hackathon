import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const dist = path.resolve('dist');
const server = createServer(async (request, response) => {
  try {
    const pathname = new URL(request.url, 'http://localhost').pathname;
    const filename = path.resolve(dist, `.${pathname === '/' ? '/index.html' : pathname}`);
    if (!filename.startsWith(`${dist}${path.sep}`)) throw new Error('Invalid path');
    const content = await readFile(filename);
    const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' };
    response.writeHead(200, { 'Content-Type': types[path.extname(filename)] || 'application/octet-stream' });
    response.end(content);
  } catch {
    response.writeHead(404);
    response.end();
  }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
try {
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => { errors.push(error.message); console.error(error.message); });
  const databaseNames = ['gcc_banking_core', 'gcc_reconciliation', 'gcc_audit_service'];
  const makeAnomaly = database => ({
    type: 'LOCK_CONTENTION', database, title: `Lock on ${database}`,
    target_table: 'public.orders', blocking_pid: 42, wait_event: 'Lock',
    severity: 'HIGH', description: 'Fixture anomaly',
  });
  let anomaly = makeAnomaly(databaseNames[0]);
  let diagnoses = 0;
  let delayNextDiagnosis = false;
  let releaseDiagnosis;
  let heldDiagnosis;
  let submissions = [];
  let rejectScenario = false;
  let simulationEnabled = false;
  let telemetryUnavailable = false;
  const liveConnectionMessage = 'Connected to 3/3 configured databases. Live telemetry available.';
  const unavailableConnectionMessage = 'Database check failed. Telemetry unavailable.';
  const nonGetRequests = [];
  const unexpected = [];
  await page.route('**/api/**', async route => {
    const pathname = new URL(route.request().url()).pathname;
    if (route.request().method() !== 'GET') nonGetRequests.push(pathname);
    let data;
    let status = 200;
    switch (pathname) {
      case '/api/fleet':
        data = {
          fleet: databaseNames.map(name => ({
            name, status: telemetryUnavailable ? 'UNAVAILABLE' : 'HEALTHY',
            risk_score: telemetryUnavailable ? null : 10,
            data_source: telemetryUnavailable ? 'unavailable' : 'live',
            status_desc: telemetryUnavailable ? 'Telemetry unavailable' : 'Live telemetry healthy',
          })),
          last_polled_sec_ago: 1, simulation_enabled: simulationEnabled, active_scenario: 'HEALTHY',
        };
        break;
      case '/api/kpis':
        data = {
          kpis: telemetryUnavailable
            ? { active_sessions: null, blocked_sessions: null, cache_hit_ratio: null, avg_query_time_ms: null }
            : { active_sessions: 4, blocked_sessions: 1, cache_hit_ratio: 99, avg_query_time_ms: 100 },
          connection: { state: telemetryUnavailable ? 'error' : 'connected', message: telemetryUnavailable ? unavailableConnectionMessage : liveConnectionMessage, simulation_enabled: simulationEnabled },
        };
        break;
      case '/api/anomaly':
        data = { anomaly };
        break;
      case '/api/diagnose': {
        const snapshot = structuredClone(anomaly);
        diagnoses += 1;
        data = { success: true, anomaly: snapshot, diagnosis: {
          model: 'dbpulse rule-based runbook', root_cause: `Diagnosis ${diagnoses}: ${snapshot?.database}`,
          citations: 'Runbook references: pg_locks', disclaimer: 'Review SQL before use.',
          remediation_steps: [{ step: 1, title: 'Inspect', sql: 'SELECT 1;' }],
        } };
        if (delayNextDiagnosis) {
          delayNextDiagnosis = false;
          await new Promise(resolve => { releaseDiagnosis = resolve; heldDiagnosis?.(); });
        }
        break;
      }
      case '/api/timeline': data = { timeline: [] }; break;
      case '/api/databases/gcc_banking_core/tables':
      case '/api/databases/gcc_reconciliation/tables':
      case '/api/databases/gcc_audit_service/tables': data = { tables: [] }; break;
      case '/api/next-incident-id': data = { next_incident_id: 'INC-12345678' }; break;
      case '/api/raise-incident': {
        const payload = route.request().postDataJSON();
        submissions.push(payload);
        data = { success: true, incident: payload };
        break;
      }
      case '/api/reset': data = { success: true, active_scenario: 'HEALTHY' }; break;
      case '/api/trigger-anomaly':
        status = rejectScenario ? 503 : 200;
        data = { success: !rejectScenario, active_scenario: route.request().postDataJSON().scenario };
        break;
      default:
        unexpected.push(pathname);
        data = {};
    }
    await route.fulfill({ status, json: data });
  });
  const nextPoll = () => page.waitForResponse(response => new URL(response.url()).pathname === '/api/timeline');
  const waitDiagnosis = number => page.getByText(`Diagnosis ${number}:`, { exact: false }).waitFor();
  const submit = () => page.getByRole('button', { name: /Submit & Dispatch Incident/ }).click();
  const goBack = () => page.getByRole('button', { name: /Return to Fleet Console/ }).click();

  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await waitDiagnosis(1);
  assert.equal(await page.locator('[role="status"] strong').textContent(), liveConnectionMessage);
  assert.equal(await page.locator('.demo-controls').count(), 0);
  assert.equal(await page.getByText('RISK 10/100', { exact: true }).count(), 3);
  console.log('PASS: normal mode displays live risk scores without simulation controls');
  await page.getByRole('button', { name: 'Raise Incident', exact: true }).click();
  await page.locator('#inc-title').fill('Reviewed draft');
  await page.locator('#inc-notes').fill('Keep this handover');
  await page.locator('.readonly-box').fill('Reviewed cause');
  await page.locator('.sql-editor').fill('SELECT 42;\nSELECT 43;');
  await nextPoll();
  await nextPoll();
  assert.equal(await page.locator('#inc-title').inputValue(), 'Reviewed draft');
  assert.equal(await page.locator('#inc-notes').inputValue(), 'Keep this handover');
  assert.equal(await page.locator('.readonly-box').inputValue(), 'Reviewed cause');
  assert.equal(await page.locator('.sql-editor').inputValue(), 'SELECT 42;\nSELECT 43;');
  await submit();
  await page.getByText('Incident Successfully Stored', { exact: true }).waitFor();
  assert.equal(submissions[0].remediation_steps[0].sql, 'SELECT 42;\nSELECT 43;');
  assert.equal(submissions[0].root_cause, 'Reviewed cause');
  await page.getByText('1 step(s) stored with the incident').waitFor();
  await goBack();

  await page.getByRole('button', { name: /Create Incident/, exact: false }).first().click();
  await page.locator('.sql-editor').fill('');
  await submit();
  await page.getByText('Incident Successfully Stored', { exact: true }).waitFor();
  assert.deepEqual(submissions[1].remediation_steps, []);
  await page.getByText('0 step(s) stored with the incident').waitFor();
  await goBack();
  console.log('PASS: draft survives polls; edited and empty SQL are submitted exactly');

  anomaly = makeAnomaly(databaseNames[1]);
  await waitDiagnosis(2);
  anomaly = null;
  await nextPoll();
  await page.locator('.agent-panel').waitFor({ state: 'hidden' });
  anomaly = makeAnomaly(databaseNames[1]);
  await waitDiagnosis(3);
  console.log('PASS: same-type database changes and recovery invalidate diagnosis');

  await page.getByRole('button', { name: /DBA Mode/ }).click();
  await page.getByText('PREVIEW ONLY', { exact: true }).waitFor();
  await page.getByText('Sample SQL Inspection & Remediation Preview', { exact: true }).waitFor();
  await page.getByText('Demonstration Session Output', { exact: true }).waitFor();
  assert.equal(await page.getByText(/PNCPRD01|Direct SQL Inspection|MANUAL CONTROL ACTIVE/).count(), 0);
  assert.equal(await page.locator('.dba-raw-table tbody tr').count(), 4);
  await page.getByRole('button', { name: /Idle Connections/ }).click();
  assert.equal(await page.locator('.dba-raw-table tbody tr').count(), 3);
  await page.getByRole('button', { name: /Table Scans/ }).click();
  assert.equal(await page.locator('.dba-raw-table tbody tr').count(), 1);
  await page.locator('.dba-sql-input').fill('THIS IS NOT VALID SQL');
  const requestsBeforePreview = [...nonGetRequests];
  await page.getByRole('button', { name: 'Preview Query', exact: true }).click();
  await page.getByText(/SQL was not sent to PostgreSQL/).waitFor();
  await nextPoll();
  assert.deepEqual(nonGetRequests, requestsBeforePreview);
  console.log('PASS: DBA samples and SQL preview are disclosed; preview sends no non-GET API request');
  await page.getByRole('button', { name: /Ask Agent for Suggestion/ }).click();
  await waitDiagnosis(4);
  await page.getByRole('button', { name: 'Refresh Agent Suggestion' }).click();
  await waitDiagnosis(5);
  console.log('PASS: DBA consultation requests fresh guidance');

  delayNextDiagnosis = true;
  const diagnosisHeld = new Promise(resolve => { heldDiagnosis = resolve; });
  await page.getByRole('button', { name: /Agent Mode/ }).click();
  await diagnosisHeld;
  await page.getByRole('button', { name: /DBA Mode/ }).click();
  releaseDiagnosis();
  await nextPoll();
  assert.equal(await page.getByText('Diagnosis 6:', { exact: false }).count(), 0);
  await page.getByRole('button', { name: /Ask Agent for Suggestion/ }).click();
  await waitDiagnosis(7);
  console.log('PASS: delayed diagnosis from prior mode is discarded');

  await page.getByRole('button', { name: /Agent Mode/ }).click();
  await waitDiagnosis(8);
  simulationEnabled = true;
  await page.getByRole('button', { name: 'Reset (Healthy)' }).waitFor();
  assert.equal(await page.locator('[role="status"] strong').textContent(), liveConnectionMessage);
  await page.getByText('Simulation enabled', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Reset (Healthy)' }).click();
  await waitDiagnosis(9);
  await page.getByText(`Lock on ${databaseNames[1]}`, { exact: false }).first().waitFor();
  rejectScenario = true;
  await page.getByRole('button', { name: 'Pool Exhaustion', exact: true }).click();
  await waitDiagnosis(10);
  await page.getByText(`Lock on ${databaseNames[1]}`, { exact: false }).first().waitFor();
  console.log('PASS: reset and failed scenario requests do not invent healthy/demo state');

  simulationEnabled = false;
  telemetryUnavailable = true;
  anomaly = null;
  await page.getByText('RISK N/A', { exact: true }).first().waitFor();
  await page.locator('.kpi-value').filter({ hasText: 'N/A' }).first().waitFor();
  assert.equal(await page.getByText('RISK N/A', { exact: true }).count(), 3);
  assert.equal(await page.locator('.kpi-value').filter({ hasText: 'N/A' }).count(), 4);
  assert.equal(await page.locator('.fleet-row.healthy').count(), 0);
  await page.locator('.demo-controls').waitFor({ state: 'hidden' });
  assert.equal(await page.locator('[role="status"] strong').textContent(), unavailableConnectionMessage);
  console.log('PASS: failed telemetry displays unavailable scores and KPIs, not healthy values');

  await mkdir('artifacts/dashboard-tests', { recursive: true });
  await page.screenshot({ path: 'artifacts/dashboard-tests/unavailable.png', fullPage: true });
  telemetryUnavailable = false;
  await page.getByText('RISK 10/100', { exact: true }).first().waitFor();
  await page.getByText('99%', { exact: true }).waitFor();
  await page.screenshot({ path: 'artifacts/dashboard-tests/desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true,
    'Mobile dashboard must not overflow horizontally');
  await page.screenshot({ path: 'artifacts/dashboard-tests/mobile.png', fullPage: true });
  assert.deepEqual(errors, []);
  assert.deepEqual(unexpected, []);
  console.log('PASS: no browser exceptions or unmocked API requests');
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}