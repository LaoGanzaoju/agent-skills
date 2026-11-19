// 一次性下载器：从 IMA 媒体链接下载 zip 二进制（带自定义 headers）
const https = require('https');
const fs = require('fs');
const url = process.argv[2];
const out = process.argv[3];
const headers = JSON.parse(process.argv[4] || '{}');

function get(u, redirects) {
  if (redirects > 5) {
    console.error('too many redirects');
    process.exit(1);
  }
  https.get(u, { headers }, (res) => {
    if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
      res.resume();
      return get(res.headers.location, redirects + 1);
    }
    if (res.statusCode !== 200) {
      console.error('HTTP ' + res.statusCode);
      let body = '';
      res.on('data', (c) => (body += c));
      res.on('end', () => {
        console.error(body.slice(0, 500));
        process.exit(1);
      });
      return;
    }
    const f = fs.createWriteStream(out);
    res.pipe(f);
    f.on('finish', () => {
      f.close(() => {
        const size = fs.statSync(out).size;
        console.log(JSON.stringify({ ok: true, bytes: size, path: out }));
      });
    });
  }).on('error', (e) => {
    console.error(e.message);
    process.exit(1);
  });
}

get(url, 0);
