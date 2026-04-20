const express = require('express');

const app = express();
const port = Number(process.env.PORT || 8080);

app.get('/hello', (_req, res) => {
  res.json({ ok: true, at: new Date().toISOString() });
});

app.get('/health', (_req, res) => {
  res.json({ ok: true });
});

const server = app.listen(port, '0.0.0.0', () => {
  console.log(`sample-app listening on :${port}`);
});

function shutdown() {
  server.close(() => process.exit(0));
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
