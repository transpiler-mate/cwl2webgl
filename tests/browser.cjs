// Run after generating examples/atlas.html. Requires Playwright and Chromium.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || undefined,
    headless: true,
    args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  });
  try {
    const page = await browser.newPage({ viewport: {width: 1440, height: 960} });
    const errors = [], requests = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => { if (/^https?:/.test(r.url())) requests.push(r.url()); });
    await page.goto(pathToFileURL(path.resolve(process.argv[2] || 'examples/atlas.html')).href);
    await page.waitForFunction(() => document.querySelectorAll('#nodes button').length === 6);
    assert.equal(await page.locator('#error').isVisible(), false);
    assert.ok(await page.locator('#graph').evaluate(c => !!c.getContext('webgl')));
    const pixels = await page.locator('#graph').evaluate(c => {
      const gl = c.getContext('webgl');
      return new Promise(resolve => requestAnimationFrame(() => {
        // Trigger a fresh draw and read immediately after the viewer's RAF.
        document.getElementById('fit').click();
        requestAnimationFrame(() => {
          const p = new Uint8Array(c.width * c.height * 4);
          gl.readPixels(0, 0, c.width, c.height, gl.RGBA, gl.UNSIGNED_BYTE, p);
          resolve(p.filter((v, i) => i % 4 === 3 && v > 0).length);
        });
      }));
    });
    assert.ok(pixels > 200, 'WebGL must draw visible geometry');
    await page.getByRole('button', {name: 'Process scenes · workflow', exact: true}).click();
    assert.match(await page.locator('#detail').textContent(), /scatter/);
    await page.locator('#direction').selectOption('down');
    await page.getByRole('button', {name: 'Open subworkflow →', exact: true}).click();
    assert.match(await page.locator('#breadcrumb').textContent(), /Scene processing/);
    assert.equal(await page.locator('#nodes button').count(), 4);
    await page.getByRole('button', {name: '← Parent', exact: true}).click();
    assert.equal(await page.locator('#nodes button').count(), 6);
    await page.locator('#search').fill('report');
    assert.equal(await page.locator('#nodes button').count(), 2);
    await page.locator('#search').fill('');
    await page.getByRole('button', {name: 'Publish report · step', exact: true}).click();
    assert.match(await page.locator('#detail').textContent(), /when/);
    await page.locator('#connections button').first().click();
    assert.match(await page.locator('#detail').textContent(), /sourcePort/);
    await page.locator('#fit').click();
    await page.screenshot({path: process.env.SCREENSHOT_PATH || 'browser-preview.png', fullPage: true});
    assert.deepEqual(errors, []);
    assert.deepEqual(requests, [], 'Viewer must remain offline');
    const fallback = await browser.newPage();
    await fallback.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(kind, ...args) {
        return kind === 'webgl' ? null : original.call(this, kind, ...args);
      };
    });
    await fallback.goto(page.url());
    assert.equal(await fallback.locator('#error').isVisible(), true);
    await fallback.getByRole('button', {name: 'Process scenes · workflow', exact: true}).click();
    await fallback.getByRole('button', {name: 'Open subworkflow →', exact: true}).click();
    assert.equal(await fallback.locator('#nodes button').count(), 4);
    console.log('PASS: WebGL geometry, selection, tracing control, nested navigation, search, connection inspector, offline operation and no-WebGL fallback');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
