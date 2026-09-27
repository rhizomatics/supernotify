// Capture a PNG thumbnail of each Archify diagram in docs/developer/diagrams, for the docs
// pages that link to the interactive HTML. Needs the archify skill installed under .agents/
// (as for regenerating the diagrams themselves) and Google Chrome.
//
//   node docgen/diagram_thumbnails.mjs                 - regenerate all thumbnails
//   node docgen/diagram_thumbnails.mjs <diagram.html>  - only where the thumbnail is older than
//                                                       the diagram, as run by pre-commit, since
//                                                       captures aren't byte-for-byte repeatable
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const diagramDir = path.join(root, 'docs', 'developer', 'diagrams');

const diagrams = process.argv.length > 2
  ? process.argv.slice(2).map((f) => path.resolve(f)).filter((html) => {
      const png = html.replace(/\.html$/, '.png');
      return !fs.existsSync(png) || fs.statSync(png).mtimeMs < fs.statSync(html).mtimeMs;
    })
  : fs.readdirSync(diagramDir).filter((f) => f.endsWith('.html')).sort().map((f) => path.join(diagramDir, f));
if (diagrams.length === 0) process.exit(0);

const { ChromeVisualBrowser, findChrome } = await import('../.agents/skills/archify/bin/visual-check.mjs');
const chrome = findChrome();
if (!chrome) throw new Error('Google Chrome not found');
const browser = new ChromeVisualBrowser(chrome);
try {
  for (const html of diagrams) {
    await browser.inspect({ artifactPath: html, width: 1600, height: 1000, theme: 'light' });
    const sessionId = await browser.sessionPromise;
    // the diagram itself is the largest svg on the page, the rest are toolbar icons
    const evaluated = await browser.cdp.send('Runtime.evaluate', {
      expression: `(function () {
        const svg = Array.from(document.querySelectorAll('svg'))
          .map((s) => s.getBoundingClientRect())
          .sort((a, b) => b.width * b.height - a.width * a.height)[0];
        return { x: svg.x, y: svg.y, width: svg.width, height: svg.height };
      })()`,
      returnByValue: true,
    }, sessionId);
    const clip = { ...evaluated.result.value, scale: 1 };
    const capture = await browser.cdp.send('Page.captureScreenshot', { format: 'png', clip }, sessionId, 20000);
    const output = html.replace(/\.html$/, '.png');
    fs.writeFileSync(output, Buffer.from(capture.data, 'base64'));
    console.log(`${path.relative(root, output)} ${Math.round(clip.width)}x${Math.round(clip.height)}`);
  }
} finally {
  await browser.close();
}
