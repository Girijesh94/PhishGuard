const fs = require('node:fs');
const path = require('node:path');
const { Pool } = require('pg');

async function main() {
  if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL is required');
  const pool = new Pool({ connectionString: process.env.DATABASE_URL });
  try {
    await pool.query(fs.readFileSync(path.join(__dirname, '..', 'schema.sql'), 'utf8'));
    console.log('Database schema ready');
  } finally {
    await pool.end();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
