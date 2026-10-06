// Chart pack 体检：图片是否都加载、有没有横向溢出、关键内容是否在。
// 用法：node tools/check_chartpack.js
const puppeteer = require('C:/Users/Xie Yulong/Documents/ChatGPT/知识库/_qs_tmp/node_modules/puppeteer-core');
const path = require('path');

// 可选参数：给一个线上地址就体检线上版本，不给就检查本地 index.html
const ARG = process.argv[2];
const PAGE = ARG
  ? ARG
  : 'file:///' + path.resolve(__dirname, '..', 'index.html').replace(/\\/g, '/')
      .replace(/ /g, '%20').replace(/[^\x00-\x7F]/g, (c) => encodeURIComponent(c));

(async () => {
  const b = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new', args: ['--allow-file-access-from-files', '--no-first-run'],
  });
  const out = [];
  for (const w of [1440, 390]) {
    const p = await b.newPage();
    const errs = [];
    p.on('pageerror', (e) => errs.push(e.message));
    await p.setViewport({ width: w, height: 1000 });
    await p.goto(PAGE, { waitUntil: 'load' });
    await p.evaluate(() => document.fonts.ready);
    await p.evaluate(() => Promise.all(Array.from(document.images)
      .map((i) => (i.complete ? null : new Promise((r) => { i.onload = i.onerror = r; })))));
    out.push(await p.evaluate((w) => {
      const de = document.documentElement;
      const imgs = Array.from(document.images);
      return {
        width: w,
        overflow: de.scrollWidth - de.clientWidth,
        images: imgs.length,
        brokenImages: imgs.filter((i) => !(i.naturalWidth > 0)).map((i) => i.getAttribute('src')),
        exhibits: document.querySelectorAll('.ex').length,
        hasTable: !!document.querySelector('table tbody tr'),
        takeaways: document.querySelectorAll('.takeaways li').length,
        title: document.querySelector('h1').textContent.slice(0, 30),
        widest: Array.from(document.querySelectorAll('body *'))
          .map((el) => ({ el: el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''),
                          right: Math.round(el.getBoundingClientRect().right) }))
          .filter((x) => x.right > w + 1)
          .sort((a, b) => b.right - a.right).slice(0, 4),
      };
    }, w));
    await p.close();
  }
  await b.close();
  console.log(JSON.stringify(out, null, 1));
})().catch((e) => { console.error('FAILED', e.message); process.exit(1); });
