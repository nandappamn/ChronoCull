import test from 'node:test';
import assert from 'node:assert/strict';
import { KeyPoolManager } from '../src/keyPool.js';

test('KeyPoolManager - sets and rotates keys via Round-Robin', () => {
  const pool = new KeyPoolManager({ defaultCooldownMs: 1000 });
  pool.setKeys('groq', ['key-a', 'key-b', 'key-c']);

  const k1 = pool.getKey('groq', 'round-robin');
  const k2 = pool.getKey('groq', 'round-robin');
  const k3 = pool.getKey('groq', 'round-robin');
  const k4 = pool.getKey('groq', 'round-robin');

  assert.equal(k1, 'key-a');
  assert.equal(k2, 'key-b');
  assert.equal(k3, 'key-c');
  assert.equal(k4, 'key-a'); // wrapped around
});

test('KeyPoolManager - selects least-recently used key in LRU mode', () => {
  const pool = new KeyPoolManager();
  pool.setKeys('mistral', ['key-1', 'key-2']);

  const first = pool.getKey('mistral', 'lru');
  const second = pool.getKey('mistral', 'lru');

  // Since first was just used, second should be chosen next
  assert.notEqual(first, second);
});

test('KeyPoolManager - rate limit (429) isolates key to cooldown and fails over to next', () => {
  const pool = new KeyPoolManager({ defaultCooldownMs: 5000 });
  pool.setKeys('gemini', ['key-fast', 'key-backup']);

  // Key-fast gets selected
  const key1 = pool.getKey('gemini', 'round-robin');
  assert.equal(key1, 'key-fast');

  // Simulate 429 Rate Limit on key-fast
  const cooldownMs = pool.markRateLimited('gemini', 'key-fast');
  assert.ok(cooldownMs >= 5000);

  // Next request MUST skip key-fast and pick key-backup
  const key2 = pool.getKey('gemini', 'round-robin');
  assert.equal(key2, 'key-backup');

  // Key-fast is still in cooldown
  const key3 = pool.getKey('gemini', 'round-robin');
  assert.equal(key3, 'key-backup');
});

test('KeyPoolManager - reports circuit break when all keys in a pool are exhausted', () => {
  const pool = new KeyPoolManager({ defaultCooldownMs: 5000 });
  pool.setKeys('cerebras', ['k1', 'k2']);

  pool.markRateLimited('cerebras', 'k1');
  pool.markRateLimited('cerebras', 'k2');

  assert.equal(pool.hasActiveKeys('cerebras'), false);
  assert.equal(pool.getKey('cerebras'), null);

  const stats = pool.getStats('cerebras');
  assert.equal(stats.total, 2);
  assert.equal(stats.active, 0);
  assert.equal(stats.cooling, 2);
});
