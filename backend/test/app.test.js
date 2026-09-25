const test = require('node:test');
const assert = require('node:assert/strict');
const request = require('supertest');
const { createApp } = require('../src/app');

const SECRET = 'a-secret-long-enough-for-testing-only-1234567890';
function fixture() {
  const users = [];
  const scans = [];
  const queries = [];
  const pool = { async query(sql, params = []) {
    queries.push({ sql, params });
    if (sql.startsWith('INSERT INTO users')) {
      if (users.some(u => u.email === params[0])) { const error = new Error('duplicate'); error.code = '23505'; throw error; }
      const user = { id: '11111111-1111-4111-8111-111111111111', email: params[0], password_hash: params[1], created_at: new Date().toISOString() };
      users.push(user); return { rows: [user] };
    }
    if (sql.startsWith('SELECT id, email, password_hash')) return { rows: users.filter(u => u.email === params[0]) };
    if (sql.startsWith('SELECT id, email, created_at')) return { rows: users.filter(u => u.id === params[0]) };
    if (sql.startsWith('INSERT INTO scan_history')) {
      const row = { id: '22222222-2222-4222-8222-222222222222', created_at: new Date().toISOString(), user_id: params[0],
        url: params[1], normalized_url: params[2], label: params[3], confidence: params[4],
        phishing_probability: params[5], model_sha256: params[6], top_features: JSON.parse(params[7]), top_features_method: params[8] };
      scans.push(row); return { rows: [row] };
    }
    if (sql.includes('FROM scan_history')) return { rows: scans.filter(s => s.user_id === params[0]).slice(0, params[1]) };
    return { rows: [] };
  }};
  const prediction = { normalized_url: 'https://example.com', label: 'legitimate', confidence: 0.8,
    phishing_probability: 0.2, model_sha256: 'a'.repeat(64), top_features: [{ feature: 'example', contribution: -1 }],
    top_features_method: 'text only' };
  const app = createApp({ pool, jwtSecret: SECRET, predict: async () => prediction });
  return { app, queries };
}

test('register, login, authenticated scan and private history', async () => {
  const { app, queries } = fixture();
  const register = await request(app).post('/api/auth/register').send({ email: 'TEST@Example.com', password: 'pass123456' });
  assert.equal(register.status, 201);
  assert.equal(register.body.user.email, 'test@example.com');
  assert.ok(register.body.token);
  const duplicate = await request(app).post('/api/auth/register').send({ email: 'test@example.com', password: 'pass123456' });
  assert.equal(duplicate.status, 409);
  const badLogin = await request(app).post('/api/auth/login').send({ email: 'test@example.com', password: 'wrong' });
  assert.equal(badLogin.status, 401);
  const login = await request(app).post('/api/auth/login').send({ email: 'test@example.com', password: 'pass123456' });
  assert.equal(login.status, 200);
  const anonymous = await request(app).post('/api/scans').send({ url: 'https://example.com' });
  assert.equal(anonymous.status, 401);
  const saved = await request(app).post('/api/scans').set('Authorization', 'Bearer ' + login.body.token).send({ url: 'https://example.com' });
  assert.equal(saved.status, 201);
  assert.equal(saved.body.model_sha256, 'a'.repeat(64));
  const history = await request(app).get('/api/scans').set('Authorization', 'Bearer ' + login.body.token);
  assert.equal(history.status, 200);
  assert.equal(history.body.scans.length, 1);
  assert.equal(history.body.scans[0].url, 'https://example.com');
  assert.ok(queries.some(q => q.sql.includes('WHERE user_id = $1') && q.params[0] === register.body.user.id));
});

test('validates scan input and history limit', async () => {
  const { app } = fixture();
  const registered = await request(app).post('/api/auth/register').send({ email: 'a@example.com', password: 'pass123456' });
  const auth = 'Bearer ' + registered.body.token;
  assert.equal((await request(app).post('/api/scans').set('Authorization', auth).send({ url: '' })).status, 422);
  assert.equal((await request(app).get('/api/scans?limit=999').set('Authorization', auth)).status, 422);
  assert.equal((await request(app).get('/api/scans').set('Authorization', 'Bearer bad')).status, 401);
});
