const fs = require('fs');
const { spawn } = require('child_process');
const { chromium } = require('C:/Users/BenTo/AppData/Local/npm-cache/_npx/31e32ef8478fbf80/node_modules/playwright-core');

const FFMPEG = 'C:/Users/BenTo/Desktop/Repo/ds-imitating-draw/tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe';
const HTML = 'file:///C:/Users/BenTo/Desktop/Repo/ds-imitating-draw/index.html?record=1';
const CHROME = 'C:/Users/BenTo/AppData/Local/ms-playwright/chromium-1246/chrome-win64/chrome.exe';
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const OUT = arg('--out', 'painting_process_chunks.mp4');
const CHUNK = parseInt(arg('--chunk', '1800'), 10);
const START = parseInt(arg('--start', '0'), 10);
const LIMIT = parseInt(arg('--limit', '0'), 10);
const GQ = parseInt(arg('--q', '18'), 10);
const JQ = parseInt(arg('--jq', '95'), 10);
const PNG = process.argv.includes('--png');
const DSF = parseFloat(arg('--dsf', '1'));
const DIR = 'chunks';

(async () => {
  fs.mkdirSync(DIR, { recursive: true });
  const args = ['--use-angle=vulkan', '--enable-features=Vulkan', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--disable-accelerated-2d-canvas'];
  const browser = await chromium.launch({ executablePath: CHROME, headless: true, args });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: DSF });
  page.on('pageerror', e => console.error('[pageerror]', e.message));

  await page.goto(HTML);
  await page.waitForFunction('window.__ready === true', null, { timeout: 180000 });
  const info = await page.evaluate(() => {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl2') || c.getContext('webgl');
    const ext = gl && gl.getExtension('WEBGL_debug_renderer_info');
    return {
      renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'n/a',
      duration: window.__player.duration, tEnd: window.__player.tEnd, n: window.__player.n
    };
  });
  const FPS = 30, STEP = 1000 / FPS;
  const first = Math.round(START / STEP);
  const total = LIMIT > 0 ? first + LIMIT : Math.ceil(info.duration / STEP);
  console.log(JSON.stringify({ ...info, total, chunk: CHUNK }));

  const encArgs = ['-c:v', 'libx264', '-preset', 'slow', '-crf', String(GQ)];
  const files = [];
  const t0 = Date.now();
  for (let cs = first, ci = 0; cs < total; cs += CHUNK, ci++) {
    const count = Math.min(CHUNK, total - cs);
    const s = cs * STEP;
    await page.goto(HTML);
    await page.waitForFunction('window.__ready === true', null, { timeout: 180000 });
    await page.evaluate((s) => { document.body.classList.add('recording'); window.__player.seek(s); }, s);

    const file = `${DIR}/chunk_${String(ci).padStart(3, '0')}.mp4`;
    const ff = spawn(FFMPEG, [
      '-hide_banner', '-loglevel', 'error',
      '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
      ...encArgs, '-force_key_frames', `expr:eq(n,${count - 1})`,
      '-vf', `scale=1920:1080:flags=lanczos:in_range=full:out_range=tv` + (DSF > 1 ? '' : ''),
      '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-profile:v', 'high', '-level', '4.1',
      '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
      '-movflags', '+faststart', '-y', file
    ], { stdio: ['pipe', 'inherit', 'inherit'] });

    for (let i = 0; i < count; i++) {
      const t = s + i * STEP;
      await page.evaluate(tt => window.__player.advance(tt), t);
      const buf = PNG ? await page.screenshot({ type: 'png' })
                      : await page.screenshot({ type: 'jpeg', quality: JQ });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    }
    ff.stdin.end();
    await new Promise((res, rej) => ff.on('close', c => c === 0 ? res() : rej(new Error('ffmpeg exit ' + c))));
    files.push(file);
    console.log(`chunk ${ci} ${(count / FPS).toFixed(1)}s done, total ${((Date.now() - t0) / 60000).toFixed(1)} min`);
  }
  await browser.close();

  fs.writeFileSync(`${DIR}/list.txt`, files.map(f => `file '${f.split('/').pop()}'`).join('\n') + '\n');
  const cat = spawn(FFMPEG, [
    '-hide_banner', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
    '-i', `${DIR}/list.txt`, '-c', 'copy', '-movflags', '+faststart', '-y', OUT
  ], { stdio: 'inherit' });
  await new Promise((res, rej) => cat.on('close', c => c === 0 ? res() : rej(new Error('concat exit ' + c))));
  console.log('done', OUT, fs.statSync(OUT).size, 'bytes');
})();
