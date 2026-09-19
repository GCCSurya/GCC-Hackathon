import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const baseUrl = process.env.DASHBOARD_URL || 'http://127.0.0.1:5000';
const scenario = process.env.AGENT_DEMO_SCENARIO || 'RUNAWAY_QUERY';
const headless = process.env.HEADLESS === 'true';
const submitRequested = process.env.SUBMIT_INCIDENT !== 'false';
const scenarioButtons = {
  LOCK_CONTENTION: 'Row Lock Contention',
  POOL_EXHAUSTION: 'Pool Exhaustion',
  RUNAWAY_QUERY: 'Runaway Scan',
};

if (!scenarioButtons[scenario]) {
  throw new Error(`Unknown AGENT_DEMO_SCENARIO: ${scenario}`);
}

const runId = new Date().toISOString().replaceAll(':', '-').replaceAll('.', '-');
const outputDir = path.resolve('artifacts', 'agent-demo', runId);
await mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ headless, slowMo: headless ? 0 : 250 });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const result = {
  baseUrl,
  scenario,
  databaseConnected: false,
  incidentSubmitted: false,
  screenshots: [],
};

async function capture(name, locator) {
  if (locator) {
    await locator.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
  }
  const screenshotPath = path.join(outputDir, `${name}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: false });
  result.screenshots.push(screenshotPath);
  console.log(`Captured ${screenshotPath}`);
}

try {
  console.log(`Opening ${baseUrl}`);
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.getByRole('button', { name: /Agent Mode/ }).click();

  console.log(`Injecting ${scenario}`);
  await page.getByRole('button', { name: scenarioButtons[scenario] }).click();
  const remediationHeading = page.getByText('Suggested Remediation Steps:');
  await remediationHeading.waitFor({ state: 'visible', timeout: 45000 });
  await capture('01-agent-diagnosis', remediationHeading);

  console.log('Opening the pre-populated incident form');
  await page.getByRole('button', { name: 'Raise Incident' }).click();
  await page.getByText('AGENT AUTONOMOUS DISPATCH').waitFor({ state: 'visible' });
  await capture('02-incident-form', page.getByRole('button', { name: /Submit & Dispatch Incident/ }));

  const statusText = await page.getByRole('status').innerText();
  result.databaseConnected = statusText.includes('PostgreSQL connected');

  if (submitRequested && result.databaseConnected) {
    console.log('PostgreSQL is connected; submitting the incident');
    await page.getByRole('button', { name: /Submit & Dispatch Incident/ }).click();
    const receipt = page.getByText('Incident Successfully Stored');
    await receipt.waitFor({ state: 'visible', timeout: 30000 });
    result.incidentSubmitted = true;
    await capture('03-incident-receipt', receipt);
  } else {
    const reason = submitRequested
      ? 'PostgreSQL is not connected; skipping submission to avoid a fake demo receipt.'
      : 'Incident submission disabled by SUBMIT_INCIDENT=false.';
    console.log(reason);
  }

  console.log('Returning to the fleet console');
  await page.getByRole('button', { name: /Fleet Console/ }).first().click();
  await page.getByText('Database Fleet Status').waitFor({ state: 'visible' });
  await capture('04-fleet-console', page.getByText('Database Fleet Status'));
} catch (error) {
  await capture('99-failure');
  throw error;
} finally {
  await writeFile(path.join(outputDir, 'result.json'), `${JSON.stringify(result, null, 2)}\n`);
  await browser.close();
  console.log(`Demo artifacts: ${outputDir}`);
}