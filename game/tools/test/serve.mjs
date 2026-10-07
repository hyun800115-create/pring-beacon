// Tiny static file server for frost-village/ (no dependencies).
//   node tools/test/serve.mjs [port]        -> serves on the port (0 / omitted = a free port)
// Also importable: const { start } = await import('./serve.mjs'); const { url, close } = await start();
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp',
  '.ogg': 'audio/ogg', '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.css': 'text/css', '.svg': 'image/svg+xml',
  '.webmanifest': 'application/manifest+json', '.md': 'text/markdown; charset=utf-8', '.gif': 'image/gif',
};

export function start(port = 0, opts = {}) {
  const prefix = opts.prefix || '/';   // serve under a sub-path to prove relative URLs work
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      let u = decodeURIComponent((req.url || '/').split('?')[0]);
      if (!u.startsWith(prefix)) { res.writeHead(404); res.end('not found'); return; }
      u = '/' + u.slice(prefix.length);
      if (u.endsWith('/')) u += 'index.html';
      const fp = path.join(ROOT, path.normalize(u));
      if (!fp.startsWith(ROOT)) { res.writeHead(403); res.end(); return; }
      fs.stat(fp, (err, st) => {
        if (err || !st.isFile()) { res.writeHead(404, { 'content-type': 'text/plain' }); res.end('not found'); return; }
        res.writeHead(200, { 'content-type': TYPES[path.extname(fp).toLowerCase()] || 'application/octet-stream', 'cache-control': 'no-cache', 'content-length': st.size });
        fs.createReadStream(fp).pipe(res);
      });
    });
    server.listen(port, '127.0.0.1', () => {
      const p = server.address().port;
      resolve({ url: `http://127.0.0.1:${p}${prefix}`, port: p, close: () => new Promise((r) => server.close(r)) });
    });
  });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const port = Number(process.argv[2] || 0);
  start(port).then(({ url }) => console.log('Frost Village served at ' + url + '  (Ctrl+C to stop)'));
}
