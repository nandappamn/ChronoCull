import fs from 'node:fs';
import path from 'node:path';

export class KeyPoolManager {
  /**
   * @param {Object} options
   * @param {string} [options.keysFilePath]
   * @param {number} [options.defaultCooldownMs=60000]
   */
  constructor(options = {}) {
    this.keysFilePath = options.keysFilePath || null;
    this.defaultCooldownMs = options.defaultCooldownMs || 60000;
    
    // Map of providerId -> Array of KeyState
    // KeyState: { key, lastUsedAt, cooldownUntil, consecutive429s, successCount, failureCount, roundRobinIndex }
    this.pools = new Map();
    this.rrIndices = new Map();

    if (this.keysFilePath && fs.existsSync(this.keysFilePath)) {
      this.loadKeysFromFile(this.keysFilePath);
    }
    this.loadKeysFromEnv();
  }

  /**
   * Load keys from environment variables (e.g. MISTRAL_API_KEY, GROQ_API_KEYS)
   */
  loadKeysFromEnv() {
    const knownProviders = ['mistral', 'groq', 'gemini', 'cerebras', 'sambanova', 'cloudflare', 'siliconflow', 'zhipu', 'llm7'];
    for (const p of knownProviders) {
      const singleKey = process.env[`${p.toUpperCase()}_API_KEY`];
      if (singleKey) {
        this.addKey(p, singleKey);
      }
      const multiKeys = process.env[`${p.toUpperCase()}_API_KEYS`];
      if (multiKeys) {
        for (const k of multiKeys.split(',')) {
          this.addKey(p, k.trim());
        }
      }
    }
  }

  /**
   * Load keys from JSON file
   * @param {string} filePath
   */
  loadKeysFromFile(filePath) {
    try {
      const raw = fs.readFileSync(filePath, 'utf8');
      const data = JSON.parse(raw);
      for (const [providerId, keys] of Object.entries(data)) {
        if (Array.isArray(keys)) {
          this.setKeys(providerId, keys);
        }
      }
    } catch (err) {
      console.error(`[KeyPool] Failed to read keys file at ${filePath}:`, err.message);
    }
  }

  /**
   * Register or update keys for a provider
   * @param {string} providerId
   * @param {string[]} keys
   */
  setKeys(providerId, keys) {
    const validKeys = (keys || []).map(k => typeof k === 'string' ? k.trim() : '').filter(Boolean);
    const existing = this.pools.get(providerId) || [];
    const existingMap = new Map(existing.map(k => [k.key, k]));

    const updated = validKeys.map(key => {
      if (existingMap.has(key)) {
        return existingMap.get(key);
      }
      return {
        key,
        lastUsedAt: 0,
        cooldownUntil: 0,
        consecutive429s: 0,
        successCount: 0,
        failureCount: 0
      };
    });

    this.pools.set(providerId, updated);
    if (!this.rrIndices.has(providerId)) {
      this.rrIndices.set(providerId, 0);
    }
  }

  /**
   * Add a single key to a provider's pool
   * @param {string} providerId
   * @param {string} key
   */
  addKey(providerId, key) {
    if (!key || typeof key !== 'string') return;
    const cleanKey = key.trim();
    if (!cleanKey) return;

    const list = this.pools.get(providerId) || [];
    if (!list.some(k => k.key === cleanKey)) {
      list.push({
        key: cleanKey,
        lastUsedAt: 0,
        cooldownUntil: 0,
        consecutive429s: 0,
        successCount: 0,
        failureCount: 0
      });
      this.pools.set(providerId, list);
    }
  }

  /**
   * Get an available healthy key for a provider
   * @param {string} providerId
   * @param {'lru'|'round-robin'} [strategy='lru']
   * @returns {string|null}
   */
  getKey(providerId, strategy = 'lru') {
    const list = this.pools.get(providerId);
    if (!list || list.length === 0) {
      return null;
    }

    const now = Date.now();
    // Filter active keys not under cooldown
    const active = list.filter(k => k.cooldownUntil <= now);
    if (active.length === 0) {
      return null;
    }

    let selected;
    if (strategy === 'round-robin') {
      let idx = this.rrIndices.get(providerId) || 0;
      selected = active[idx % active.length];
      this.rrIndices.set(providerId, (idx + 1) % active.length);
    } else {
      // LRU: least recently used has the lowest lastUsedAt timestamp
      selected = active.reduce((earliest, cur) => cur.lastUsedAt < earliest.lastUsedAt ? cur : earliest, active[0]);
    }

    selected.lastUsedAt = now;
    return selected.key;
  }

  /**
   * Report success for a key
   * @param {string} providerId
   * @param {string} key
   */
  markSuccess(providerId, key) {
    const list = this.pools.get(providerId);
    if (!list) return;
    const target = list.find(k => k.key === key);
    if (target) {
      target.successCount += 1;
      target.consecutive429s = 0;
      target.cooldownUntil = 0;
    }
  }

  /**
   * Mark key as rate limited (429) and place in cooldown
   * @param {string} providerId
   * @param {string} key
   * @param {number} [customCooldownMs]
   * @returns {number} Cooldown duration in ms applied
   */
  markRateLimited(providerId, key, customCooldownMs) {
    const list = this.pools.get(providerId);
    if (!list) return 0;
    const target = list.find(k => k.key === key);
    if (!target) return 0;

    target.consecutive429s += 1;
    target.failureCount += 1;

    // Exponential backoff multiplier: base * 2^(retries - 1), capped at 10x
    const multiplier = Math.min(Math.pow(2, target.consecutive429s - 1), 10);
    const duration = (customCooldownMs || this.defaultCooldownMs) * multiplier;

    target.cooldownUntil = Date.now() + duration;
    return duration;
  }

  /**
   * Mark generic failure (non-429)
   * @param {string} providerId
   * @param {string} key
   */
  markFailure(providerId, key) {
    const list = this.pools.get(providerId);
    if (!list) return;
    const target = list.find(k => k.key === key);
    if (target) {
      target.failureCount += 1;
    }
  }

  /**
   * Check if provider has at least one active (non-cooling) key
   * @param {string} providerId
   * @returns {boolean}
   */
  hasActiveKeys(providerId) {
    const list = this.pools.get(providerId);
    if (!list || list.length === 0) return false;
    const now = Date.now();
    return list.some(k => k.cooldownUntil <= now);
  }

  /**
   * Get stats for a provider or all providers
   * @param {string} [providerId]
   */
  getStats(providerId) {
    const now = Date.now();
    const formatPool = (list) => {
      const total = list.length;
      const active = list.filter(k => k.cooldownUntil <= now).length;
      const cooling = total - active;
      return { total, active, cooling };
    };

    if (providerId) {
      const list = this.pools.get(providerId) || [];
      return formatPool(list);
    }

    const allStats = {};
    for (const [pId, list] of this.pools.entries()) {
      allStats[pId] = formatPool(list);
    }
    return allStats;
  }
}
