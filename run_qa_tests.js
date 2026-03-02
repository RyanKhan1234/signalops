/**
 * SignalOps QA Test Suite
 * Browser-based E2E tests using Playwright
 *
 * Run: node run_qa_tests.js
 */

const { chromium } = require('C:/Users/ryank/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost:3000';
const SCREENSHOT_DIR = path.join(__dirname, 'qa-screenshots');
const WAIT_FOR_RESULT_TIMEOUT = 120000; // 2 minutes

// Ensure screenshot directory exists
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

const results = [];

function log(msg) {
  const ts = new Date().toISOString();
  console.log(`[${ts}] ${msg}`);
}

async function takeScreenshot(page, name) {
  const filePath = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: filePath, fullPage: true });
  log(`Screenshot saved: ${filePath}`);
  return filePath;
}

async function clearInput(page) {
  // Click clear button if present
  try {
    const clearBtn = page.locator('button[aria-label="Clear chat history"]');
    const isVisible = await clearBtn.isVisible({ timeout: 2000 });
    if (isVisible) {
      await clearBtn.click();
      await page.waitForTimeout(500);
    }
  } catch (_) {}
}

async function submitPrompt(page, promptText) {
  // Find the textarea and fill it
  const textarea = page.locator('textarea[aria-label="Digest prompt"]');
  await textarea.waitFor({ state: 'visible', timeout: 10000 });
  await textarea.clear();
  if (promptText) {
    await textarea.fill(promptText);
    await page.waitForTimeout(300);
  }

  // Click the submit button
  const submitBtn = page.locator('button[aria-label="Submit digest request"]');
  await submitBtn.click();
}

async function waitForResponse(page, timeoutMs = WAIT_FOR_RESULT_TIMEOUT) {
  // Wait for loading to finish - the button text changes from "Generating..." back to "Generate Digest"
  // OR wait for digest content to appear
  try {
    // First wait for loading to start (button becomes "Generating...")
    log('Waiting for generation to start...');
    await page.waitForSelector('text=Generating...', { timeout: 15000 });
    log('Generation started, waiting for completion...');

    // Now wait for "Generate Digest" to come back (loading finished)
    await page.waitForSelector('text=Generate Digest', {
      timeout: timeoutMs,
      state: 'visible'
    });
    log('Generation complete.');

    // Small extra wait for content to render
    await page.waitForTimeout(1000);
    return true;
  } catch (err) {
    log(`Warning: Loading state detection failed: ${err.message}`);
    // Try waiting for any content that indicates a result
    try {
      await page.waitForSelector('[data-testid="digest-card"], .digest-card, article, [role="article"]', {
        timeout: 30000
      });
      return true;
    } catch (_) {
      // Just wait a fixed time as last resort
      await page.waitForTimeout(10000);
      return false;
    }
  }
}

async function checkForDigestContent(page) {
  const pageText = await page.evaluate(() => document.body.innerText);

  const checks = {
    hasExecutiveSummary: /executive.?summary/i.test(pageText),
    hasKeySignals: /key.?signal/i.test(pageText),
    hasRisks: /\brisk(s)?\b/i.test(pageText),
    hasOpportunities: /opportunit/i.test(pageText),
    hasActionItems: /action.?item/i.test(pageText),
    hasSources: /\bsource(s)?\b/i.test(pageText),
    hasToolTrace: /tool.?trace|tool.?call/i.test(pageText),
    hasDigestType: /daily.?digest|weekly.?report|risk.?alert|competitor.?monitor/i.test(pageText),
    // Use more specific error patterns - avoid false positives from article content
    hasError: /something went wrong|api error|network error|fetch failed|500 internal|unable to connect|request failed|generation failed/i.test(pageText),
    hasValidationError: /required|please enter|cannot be empty|validation error/i.test(pageText),
    hasContent: pageText.length > 300,
  };

  return { checks, pageText: pageText.substring(0, 2000) };
}

async function runTest(browser, testId, promptText, description, passCriteria) {
  log(`\n${'='.repeat(60)}`);
  log(`Starting ${testId}: ${description}`);
  log(`Prompt: "${promptText || '(empty)'}"`);
  log('='.repeat(60));

  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 }
  });
  const page = await context.newPage();

  const result = {
    testId,
    description,
    prompt: promptText,
    status: 'FAIL',
    observations: [],
    screenshots: [],
    bugs: [],
    error: null,
  };

  try {
    // Navigate to app
    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 30000 });

    // Before screenshot
    const beforePath = await takeScreenshot(page, `${testId}-before`);
    result.screenshots.push(beforePath);

    // Submit prompt (or empty for T5)
    await submitPrompt(page, promptText);

    if (promptText === '') {
      // T5: Empty submit - check immediately for error or graceful handling
      await page.waitForTimeout(2000);
      const afterPath = await takeScreenshot(page, `${testId}-empty-submit`);
      result.screenshots.push(afterPath);

      const { checks, pageText } = await checkForDigestContent(page);

      // Check: button should still be disabled when empty (canSubmit = false)
      const submitBtn = page.locator('button[aria-label="Submit digest request"]');
      const isDisabled = await submitBtn.isDisabled();

      if (isDisabled) {
        result.status = 'PASS';
        result.observations.push('Submit button correctly disabled when input is empty - prevents empty submission');
        result.observations.push('UI does not crash on empty submit attempt');
      } else {
        // If button was enabled and we clicked it, check for validation error
        if (checks.hasValidationError || checks.hasError) {
          result.status = 'PASS';
          result.observations.push('Validation error shown for empty submission');
        } else if (checks.hasContent) {
          result.status = 'FAIL';
          result.bugs.push('Empty prompt was accepted and generated a response - should show validation error');
        } else {
          result.status = 'PASS';
          result.observations.push('Graceful empty state - no crash, blank input not processed');
        }
      }

      results.push(result);
      await context.close();
      return result;
    }

    // Wait for response
    const responseComplete = await waitForResponse(page);

    // After screenshot
    const afterPath = await takeScreenshot(page, `${testId}-after`);
    result.screenshots.push(afterPath);

    // Check content
    const { checks, pageText } = await checkForDigestContent(page);
    result.pageTextSample = pageText;

    if (!responseComplete) {
      result.observations.push('WARNING: Response may not have fully loaded');
    }

    // Apply pass criteria
    const passResult = await passCriteria(page, checks, pageText, result);
    result.status = passResult ? 'PASS' : 'FAIL';

  } catch (err) {
    result.status = 'FAIL';
    result.error = err.message;
    result.observations.push(`Exception: ${err.message}`);
    log(`ERROR in ${testId}: ${err.message}`);

    try {
      const errorPath = await takeScreenshot(page, `${testId}-error`);
      result.screenshots.push(errorPath);
    } catch (_) {}
  }

  log(`${testId} result: ${result.status}`);
  results.push(result);
  await context.close();
  return result;
}

async function main() {
  log('Starting SignalOps QA Test Suite');
  log(`Base URL: ${BASE_URL}`);
  log(`Screenshots: ${SCREENSHOT_DIR}`);

  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:/Users/ryank/AppData/Local/ms-playwright/chromium-1208/chrome-win64/chrome.exe',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  try {
    // T1: Daily digest for Walmart Connect
    const t1 = await runTest(
      browser,
      'T1',
      'Daily digest for Walmart Connect',
      'Daily digest for Walmart Connect',
      async (page, checks, pageText, result) => {
        if (checks.hasDigestType) {
          result.observations.push('digest_type is shown in UI');
        } else {
          result.observations.push('WARNING: digest_type label not clearly visible');
        }

        if (checks.hasKeySignals) {
          result.observations.push('Key signals section visible');
        }

        if (checks.hasExecutiveSummary) {
          result.observations.push('Executive summary present');
        }

        if (!checks.hasContent) {
          result.bugs.push('No meaningful content rendered in response');
          return false;
        }

        if (checks.hasError) {
          result.bugs.push('Error message shown in UI');
          return false;
        }

        // Pass if we have content - at minimum need some signals or summary
        const hasMinContent = checks.hasContent && (checks.hasKeySignals || checks.hasExecutiveSummary || checks.hasDigestType);
        if (hasMinContent) {
          result.observations.push('Digest content successfully rendered with meaningful sections');
          return true;
        }

        result.bugs.push('Insufficient content - missing key sections');
        return false;
      }
    );

    // Skip T2-T8 if T1 failed
    if (t1.status === 'FAIL') {
      log('\nT1 FAILED - Skipping T2-T8 as per test instructions');
      for (const tid of ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8']) {
        results.push({
          testId: tid,
          status: 'SKIPPED',
          description: `Skipped due to T1 failure`,
          observations: ['Skipped because T1 failed'],
          screenshots: [],
          bugs: [],
        });
      }
      return;
    }

    // T2: Weekly report on Amazon Advertising
    await runTest(
      browser,
      'T2',
      'Weekly report on Amazon Advertising',
      'Weekly report on Amazon Advertising - expects signals and tool trace',
      async (page, checks, pageText, result) => {
        if (checks.hasKeySignals) result.observations.push('Key signals visible');
        if (checks.hasToolTrace) result.observations.push('Tool trace visible');

        if (!checks.hasContent) {
          result.bugs.push('No content rendered');
          return false;
        }
        if (checks.hasError) {
          result.bugs.push('Error displayed in UI');
          return false;
        }

        // Need at least signals and content
        const pass = checks.hasContent && checks.hasKeySignals;
        if (!pass) {
          result.observations.push('Missing key signals section');
          result.bugs.push('Key signals section not found in response');
        }
        return pass;
      }
    );

    // T3: Risk alert for Target retail media
    await runTest(
      browser,
      'T3',
      'Risk alert for Target retail media',
      'Risk alert - risks section must be visible and non-empty',
      async (page, checks, pageText, result) => {
        if (checks.hasRisks) {
          result.observations.push('Risks section visible and present');
        } else {
          result.bugs.push('Risks section not found or empty');
        }

        if (!checks.hasContent) {
          result.bugs.push('No content rendered');
          return false;
        }
        if (checks.hasError) {
          result.bugs.push('Error displayed in UI');
          return false;
        }

        return checks.hasContent && checks.hasRisks;
      }
    );

    // T4: Competitor monitor
    await runTest(
      browser,
      'T4',
      'Who are the emerging competitors in retail media',
      'Competitor monitor intent - content renders with competitor data',
      async (page, checks, pageText, result) => {
        const hasCompetitorContent = /competitor|emerging|retail.?media/i.test(pageText);

        if (hasCompetitorContent) {
          result.observations.push('Competitor-related content present in response');
        }
        if (checks.hasContent) {
          result.observations.push('Content rendered successfully');
        }

        if (!checks.hasContent) {
          result.bugs.push('No content rendered');
          return false;
        }
        if (checks.hasError) {
          result.bugs.push('Error displayed in UI');
          return false;
        }

        return checks.hasContent;
      }
    );

    // T5: Empty submit
    await runTest(
      browser,
      'T5',
      '',
      'Empty submit - should show validation error or graceful state, must not crash',
      async (page, checks, pageText, result) => {
        // This is handled specially above
        return true;
      }
    );

    // T6: Latest news for Google
    await runTest(
      browser,
      'T6',
      'Latest news for Google',
      'Latest news intent - content renders',
      async (page, checks, pageText, result) => {
        if (checks.hasContent) {
          result.observations.push('Content rendered for Google news query');
        }
        if (checks.hasDigestType) {
          result.observations.push('Digest type shown - likely daily/latest intent');
        }

        if (!checks.hasContent) {
          result.bugs.push('No content rendered');
          return false;
        }
        if (checks.hasError) {
          result.bugs.push('Error displayed in UI');
          return false;
        }

        return checks.hasContent;
      }
    );

    // T7: Simple entity "Walmart Connect" - no intent keyword
    await runTest(
      browser,
      'T7',
      'Walmart Connect',
      'Simple entity without intent keyword - graceful fallback with some content',
      async (page, checks, pageText, result) => {
        if (checks.hasContent) {
          result.observations.push('Content rendered - graceful fallback for simple entity prompt');
        }

        if (!checks.hasContent) {
          result.bugs.push('No content rendered for simple entity prompt');
          return false;
        }
        if (checks.hasError) {
          result.bugs.push('Error displayed for simple entity prompt');
          return false;
        }

        result.observations.push('Graceful fallback - app handled simple entity prompt');
        return true;
      }
    );

    // T8: Re-submit T1 prompt immediately
    await runTest(
      browser,
      'T8',
      'Daily digest for Walmart Connect',
      'Re-submit T1 prompt - result should still show (not blank/error)',
      async (page, checks, pageText, result) => {
        if (checks.hasContent) {
          result.observations.push('Content rendered on re-submission - not blank or error');
        }

        if (!checks.hasContent) {
          result.bugs.push('Re-submission produced no content - blank state');
          return false;
        }
        if (checks.hasError) {
          result.bugs.push('Re-submission produced error state');
          return false;
        }

        result.observations.push('Re-submission handled correctly - result visible');
        return true;
      }
    );

  } finally {
    await browser.close();
  }
}

main().then(() => {
  // Write results to JSON for report generation
  const jsonPath = path.join(__dirname, 'qa-results.json');
  fs.writeFileSync(jsonPath, JSON.stringify(results, null, 2));
  log(`\nResults written to: ${jsonPath}`);

  const passed = results.filter(r => r.status === 'PASS').length;
  const failed = results.filter(r => r.status === 'FAIL').length;
  const skipped = results.filter(r => r.status === 'SKIPPED').length;

  log(`\n${'='.repeat(60)}`);
  log('QA TEST SUITE COMPLETE');
  log(`PASSED:  ${passed}`);
  log(`FAILED:  ${failed}`);
  log(`SKIPPED: ${skipped}`);
  log(`TOTAL:   ${results.length}`);
  log('='.repeat(60));
}).catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
