import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ProviderRegistry } from './providers/registry.js';
import { KeyPoolManager } from './keyPool.js';
import { CompressionPipeline } from './compression/pipeline.js';
import { SmartRouter } from './router.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load .env if present (checking service dir and repo root)
const envCandidates = [
  path.resolve(__dirname, '../.env'),
  path.resolve(__dirname, '../../../.env')
];
for (const envPath of envCandidates) {
  if (fs.existsSync(envPath)) {
    if (typeof process.loadEnvFile === 'function') {
      try { process.loadEnvFile(envPath); } catch {}
    }
    break;
  }
}

const PORT = parseInt(process.env.FREELLM_PORT || process.env.PORT || '20128', 10);
const HOST = process.env.FREELLM_HOST || process.env.HOST || '127.0.0.1';
const defaultCompression = process.env.FREELLM_COMPRESSION_MODE || process.env.COMPRESSION_MODE || 'stacked';

const configDir = path.resolve(__dirname, '../config');
const providersConfigPath = path.join(configDir, 'providers.json');
const keysConfigPath = path.join(configDir, 'keys.json');

// Initialize components
const registry = new ProviderRegistry(providersConfigPath);
const keyPool = new KeyPoolManager({ keysFilePath: keysConfigPath });
const compression = new CompressionPipeline({ defaultMode: defaultCompression });
const router = new SmartRouter({ registry, keyPool, compression });

/**
 * Helper to parse JSON body from incoming request
 * @param {http.IncomingMessage} req
 * @returns {Promise<any>}
 */
function parseJsonBody(req) {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', chunk => { raw += chunk; });
    req.on('end', () => {
      if (!raw) return resolve({});
      try {
        resolve(JSON.parse(raw));
      } catch (err) {
        reject(new Error(`Invalid JSON: ${err.message}`));
      }
    });
    req.on('error', reject);
  });
}

/**
 * Send JSON response
 * @param {http.ServerResponse} res
 * @param {number} status
 * @param {any} data
 * @param {Record<string, string>} [headers={}]
 */
function sendJson(res, status, data, headers = {}) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-FreeLLM-Compress',
    ...headers
  });
  res.end(JSON.stringify(data, null, 2));
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = url.pathname;

  // Handle CORS Preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-FreeLLM-Compress',
    });
    return res.end();
  }

  // 1. Health check & status
  if (req.method === 'GET' && (pathname === '/' || pathname === '/health')) {
    const stats = keyPool.getStats();
    return sendJson(res, 200, {
      status: 'healthy',
      name: 'FreeLLM Gateway',
      version: '1.0.0',
      port: PORT,
      compression: {
        defaultMode: compression.defaultMode,
        engines: ['RTK (Command/Tool noise killer)', 'Caveman (Prose & filler condenser)']
      },
      keyPools: stats,
      providersCount: Object.keys(registry.getAllProviders()).length
    });
  }

  // 2. OpenAI /v1/models endpoint
  if (req.method === 'GET' && pathname === '/v1/models') {
    const models = registry.getAllModels();
    // Add auto models
    models.unshift(
      { id: 'auto', object: 'model', owned_by: 'freellm-gateway', tier: 1, free_quota: 'Auto-fallback cascade' },
      { id: 'auto:free', object: 'model', owned_by: 'freellm-gateway', tier: 1, free_quota: 'Auto-fallback free tier' }
    );
    return sendJson(res, 200, { object: 'list', data: models });
  }

  // 3. OpenAI /v1/chat/completions endpoint
  if (req.method === 'POST' && pathname === '/v1/chat/completions') {
    try {
      const body = await parseJsonBody(req);
      const compressHeader = req.headers['x-freellm-compress'];
      const compressionMode = typeof compressHeader === 'string' ? compressHeader.trim() : 'stacked';

      const result = await router.routeChatCompletion(body, { compressionMode });

      return sendJson(res, 200, result.data, {
        'X-FreeLLM-Compress': result.compressionHeader,
        'X-Routed-Provider': result.providerId,
        'X-Routed-Model': result.modelId
      });
    } catch (err) {
      console.error('[Server Error /v1/chat/completions]:', err.message);
      return sendJson(res, 500, {
        error: {
          message: err.message,
          type: 'gateway_error',
          code: 500
        }
      });
    }
  }

  // 4. Key Pool Management endpoints
  if (req.method === 'GET' && pathname === '/api/keys/stats') {
    return sendJson(res, 200, keyPool.getStats());
  }

  if (req.method === 'POST' && pathname === '/api/keys/add') {
    try {
      const body = await parseJsonBody(req);
      const { provider, key } = body;
      if (!provider || !key) {
        return sendJson(res, 400, { error: 'provider and key are required' });
      }
      keyPool.addKey(provider, key);
      return sendJson(res, 200, { message: `Key added to ${provider}`, stats: keyPool.getStats(provider) });
    } catch (err) {
      return sendJson(res, 400, { error: err.message });
    }
  }

  // 404 Fallback
  return sendJson(res, 404, { error: 'Not Found', path: pathname });
});

export function startServer(port = PORT, host = HOST) {
  return new Promise((resolve) => {
    server.listen(port, host, () => {
      console.log(`[FreeLLM Gateway] Listening on http://${host}:${port}`);
      console.log(`[FreeLLM Gateway] Ready for OpenAI-compatible clients (Cursor, Claude Code, Cline, etc.)`);
      console.log(`[FreeLLM Gateway] RTK + Caveman prompt compression ACTIVE.`);
      resolve(server);
    });
  });
}

// Auto-start when executed directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  startServer();
}
