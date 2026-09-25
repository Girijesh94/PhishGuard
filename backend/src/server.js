require('dotenv/config');
const { Pool } = require('pg');
const { createApp } = require('./app');

if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL is required');
if (!process.env.JWT_SECRET || Buffer.byteLength(process.env.JWT_SECRET) < 32) {
  throw new Error('JWT_SECRET must be at least 32 bytes');
}
const pool = new Pool({ connectionString: process.env.DATABASE_URL });
const app = createApp({
  pool,
  jwtSecret: process.env.JWT_SECRET,
  fastapiUrl: process.env.FASTAPI_URL || 'http://127.0.0.1:8000',
  mobileOrigin: process.env.MOBILE_ORIGIN
});
const server = app.listen(Number(process.env.PORT || 3000), () => {
  console.log('PhishGuard API listening on port ' + (process.env.PORT || 3000));
});
process.on('SIGINT', () => server.close(() => pool.end()));
process.on('SIGTERM', () => server.close(() => pool.end()));
