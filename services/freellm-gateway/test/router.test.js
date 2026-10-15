import test from 'node:test';
import assert from 'node:assert/strict';
import { SmartRouter } from '../src/router.js';
import { ProviderRegistry } from '../src/providers/registry.js';
import { KeyPoolManager } from '../src/keyPool.js';
import { CompressionPipeline } from '../src/compression/pipeline.js';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const providersPath = path.resolve(__dirname, '../config/providers.json');

test('SmartRouter - routes with prompt compression and succeeds with active key', async () => {
  const registry = new ProviderRegistry(providersPath);
  const keyPool = new KeyPoolManager({ defaultCooldownMs: 5000 });
  const compression = new CompressionPipeline({ defaultMode: 'stacked' });

  // Add a test key for groq
  keyPool.setKeys('groq', ['valid-groq-key']);

  // Mock fetch function simulating Groq API
  const mockFetch = async (url, options) => {
    const body = JSON.parse(options.body);
    // Verify prompt was compressed (Caveman stripped hello)
    assert.ok(!body.messages[0].content.toLowerCase().includes('hello!'));
    assert.equal(options.headers.Authorization, 'Bearer valid-groq-key');

    return {
      status: 200,
      ok: true,
      json: async () => ({
        id: 'chatcmpl-test-1',
        choices: [{ message: { role: 'assistant', content: 'All systems operational.' } }]
      })
    };
  };

  const router = new SmartRouter({ registry, keyPool, compression });
  const result = await router.routeChatCompletion({
    model: 'llama-3.3-70b-versatile',
    messages: [
      { role: 'user', content: 'Hello! Can you please tell me if everything works?' }
    ]
  }, { fetchFn: mockFetch });

  assert.equal(result.status, 200);
  assert.equal(result.providerId, 'groq');
  assert.ok(result.compressionHeader.includes('stacked'));
  assert.ok(result.compressionMetrics.savedChars > 0);
});

test('SmartRouter - auto-fails over on 429 to second key in pool', async () => {
  const registry = new ProviderRegistry(providersPath);
  const keyPool = new KeyPoolManager({ defaultCooldownMs: 5000 });
  const compression = new CompressionPipeline({ defaultMode: 'stacked' });

  keyPool.setKeys('mistral', ['key-rate-limited', 'key-healthy']);

  let attempt = 0;
  const mockFetch = async (url, options) => {
    attempt++;
    const authKey = options.headers.Authorization.replace('Bearer ', '');

    if (authKey === 'key-rate-limited') {
      return {
        status: 429,
        ok: false,
        text: async () => 'Rate limit exceeded: TPM reached'
      };
    }

    if (authKey === 'key-healthy') {
      return {
        status: 200,
        ok: true,
        json: async () => ({
          id: 'chatcmpl-mistral-backup',
          choices: [{ message: { role: 'assistant', content: 'Responded via backup key.' } }]
        })
      };
    }

    throw new Error('Unknown key');
  };

  const router = new SmartRouter({ registry, keyPool, compression });
  const result = await router.routeChatCompletion({
    model: 'mistral-small-latest',
    messages: [
      { role: 'user', content: 'Testing 429 failover' }
    ]
  }, { fetchFn: mockFetch });

  assert.equal(result.status, 200);
  assert.equal(result.providerId, 'mistral');
  assert.equal(attempt, 2); // First failed with 429, second succeeded!
});
