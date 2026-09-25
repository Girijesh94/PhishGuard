const express = require('express');
const cors = require('cors');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const publicUser = row => ({ id: row.id, email: row.email, created_at: row.created_at });

function createApp({ pool, jwtSecret, fastapiUrl = 'http://127.0.0.1:8000', mobileOrigin, predict }) {
  if (!pool || !jwtSecret || Buffer.byteLength(jwtSecret) < 32) throw new Error('pool and 32-byte JWT secret required');
  const app = express();
  app.disable('x-powered-by');
  app.use(express.json({ limit: '70kb' }));
  if (mobileOrigin) app.use(cors({ origin: mobileOrigin }));
  const baseUrl = fastapiUrl.replace(/\/$/, '');
  const runPrediction = predict || (async url => {
    const response = await fetch(baseUrl + '/predict', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }), signal: AbortSignal.timeout(10000)
    });
    const body = await response.json();
    if (!response.ok) {
      const error = new Error(body.detail || 'Prediction service failed');
      error.status = response.status === 422 ? 422 : 502;
      throw error;
    }
    return body;
  });
  const wrap = fn => (req, res, next) => Promise.resolve(fn(req, res)).catch(next);
  const issueToken = user => jwt.sign({ sub: user.id }, jwtSecret, { algorithm: 'HS256', expiresIn: '7d' });
  const authenticate = (req, res, next) => {
    const token = /^Bearer (.+)$/i.exec(req.get('authorization') || '')?.[1];
    if (!token) return res.status(401).json({ error: 'Authentication required' });
    try {
      const payload = jwt.verify(token, jwtSecret, { algorithms: ['HS256'] });
      if (typeof payload.sub !== 'string') throw new Error('Invalid subject');
      req.userId = payload.sub;
      next();
    } catch {
      res.status(401).json({ error: 'Invalid or expired token' });
    }
  };

  app.get('/health', wrap(async (_req, res) => {
    await pool.query('SELECT 1');
    res.json({ status: 'ok' });
  }));

  app.post('/api/auth/register', wrap(async (req, res) => {
    const email = typeof req.body?.email === 'string' ? req.body.email.trim().toLowerCase() : '';
    const password = req.body?.password;
    if (!emailPattern.test(email) || email.length > 254 || typeof password !== 'string' ||
        Buffer.byteLength(password, 'utf8') < 8 || Buffer.byteLength(password, 'utf8') > 72) {
      return res.status(422).json({ error: 'Valid email and password of 8–72 bytes required' });
    }
    const passwordHash = await bcrypt.hash(password, 12);
    try {
      const result = await pool.query(
        'INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id, email, created_at',
        [email, passwordHash]
      );
      const user = publicUser(result.rows[0]);
      res.status(201).json({ user, token: issueToken(user) });
    } catch (error) {
      if (error.code === '23505') return res.status(409).json({ error: 'Email already registered' });
      throw error;
    }
  }));

  app.post('/api/auth/login', wrap(async (req, res) => {
    const email = typeof req.body?.email === 'string' ? req.body.email.trim().toLowerCase() : '';
    const password = req.body?.password;
    if (!email || typeof password !== 'string') return res.status(422).json({ error: 'Email and password required' });
    const result = await pool.query(
      'SELECT id, email, password_hash, created_at FROM users WHERE lower(email) = $1', [email]
    );
    const row = result.rows[0];
    if (!row || !(await bcrypt.compare(password, row.password_hash))) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    const user = publicUser(row);
    res.json({ user, token: issueToken(user) });
  }));

  app.get('/api/me', authenticate, wrap(async (req, res) => {
    const result = await pool.query('SELECT id, email, created_at FROM users WHERE id = $1', [req.userId]);
    if (!result.rows[0]) return res.status(401).json({ error: 'Account no longer exists' });
    res.json({ user: publicUser(result.rows[0]) });
  }));

  app.post('/api/scans', authenticate, wrap(async (req, res) => {
    const url = req.body?.url;
    if (typeof url !== 'string' || url.trim().length === 0 || url.length > 65536) {
      return res.status(422).json({ error: 'URL must be a nonempty string of at most 65536 characters' });
    }
    let result;
    try { result = await runPrediction(url.trim()); }
    catch (error) {
      if (error.status === 422) return res.status(422).json({ error: error.message });
      console.error('Prediction service error:', error);
      return res.status(502).json({ error: 'Prediction service unavailable' });
    }
    const saved = await pool.query(
      `INSERT INTO scan_history
       (user_id, url, normalized_url, label, confidence, phishing_probability,
        model_sha256, top_features, top_features_method)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
       RETURNING id, created_at`,
      [req.userId, url.trim(), result.normalized_url, result.label, result.confidence,
       result.phishing_probability, result.model_sha256, JSON.stringify(result.top_features),
       result.top_features_method]
    );
    res.status(201).json({ ...result, id: saved.rows[0].id, created_at: saved.rows[0].created_at });
  }));

  app.get('/api/scans', authenticate, wrap(async (req, res) => {
    const limit = Number(req.query.limit ?? 50);
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
      return res.status(422).json({ error: 'limit must be an integer from 1 to 100' });
    }
    const result = await pool.query(
      `SELECT id, url, normalized_url, label, confidence, phishing_probability,
              model_sha256, top_features, top_features_method, created_at
       FROM scan_history WHERE user_id = $1 ORDER BY created_at DESC, id DESC LIMIT $2`,
      [req.userId, limit]
    );
    res.json({ scans: result.rows });
  }));

  app.use((error, _req, res, _next) => {
    console.error(error);
    res.status(error.status || 500).json({ error: error.status ? error.message : 'Internal server error' });
  });
  return app;
}
module.exports = { createApp };
