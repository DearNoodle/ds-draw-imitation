const path = require('path');
const { chromium } = require('C:/Users/BenTo/AppData/Local/npm-cache/_npx/31e32ef8478fbf80/node_modules/playwright-core');

(async () => {
  const args = process.env.GPU === 'nvidia'
    ? ['--use-angle=vulkan', '--enable-features=Vulkan', '--ignore-gpu-blocklist', '--enable-gpu-rasterization']
    : ['--disable-gpu'];
  const browser = await chromium.launch({
    executablePath: 'C:/Users/BenTo/AppData/Local/ms-playwright/chromium-1246/chrome-win64/chrome.exe',
    headless: true,
    args
  });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('console', m => console.log('[console]', m.type(), m.text()));
  page.on('pageerror', e => console.log('[pageerror]', e.message));
  const t0 = Date.now();
  await page.goto('file:///C:/Users/BenTo/Desktop/Repo/ds-imitating-draw/player.html?record=1');
  await page.waitForFunction('window.__ready === true', null, { timeout: 120000 });
  console.log('ready ms', Date.now() - t0);
  const info = await page.evaluate(() => {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl2') || c.getContext('webgl');
    const ext = gl && gl.getExtension('WEBGL_debug_renderer_info');
    return { n: window.__player.n, dur: window.__player.duration, renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'n/a' };
  });
  console.log(info);
  await page.screenshot({ path: 'shot_blank.png' });
  const t1 = Date.now();
  await page.evaluate(() => window.__player.seek(window.__player.tEnd * 0.45));
  console.log('seek45 ms', Date.now() - t1);
  await page.screenshot({ path: 'shot_45.png' });
  const t2 = Date.now();
  await page.evaluate(() => window.__player.finish());
  console.log('finish ms', Date.now() - t2);
  await page.screenshot({ path: 'shot_final.png' });
  const dataUrl = await page.evaluate(() => document.getElementById('paint').toDataURL('image/png'));
  require('fs').writeFileSync('canvas_native.png', Buffer.from(dataUrl.split(',')[1], 'base64'));
  await browser.close();
})();
