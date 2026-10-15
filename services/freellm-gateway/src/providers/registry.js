import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export class ProviderRegistry {
  constructor(configPath) {
    const defaultPath = path.resolve(__dirname, '../../config/providers.json');
    this.configPath = configPath || defaultPath;
    this.providers = {};
    this.modelToProvider = new Map();
    this.tierGroups = { 1: [], 2: [], 3: [] };

    this.loadConfig();
  }

  loadConfig() {
    try {
      if (fs.existsSync(this.configPath)) {
        const data = JSON.parse(fs.readFileSync(this.configPath, 'utf8'));
        this.providers = data.providers || {};
        
        for (const [providerId, p] of Object.entries(this.providers)) {
          const tier = p.tier || 1;
          if (!this.tierGroups[tier]) this.tierGroups[tier] = [];
          this.tierGroups[tier].push(providerId);

          if (Array.isArray(p.models)) {
            for (const modelId of p.models) {
              this.modelToProvider.set(modelId.toLowerCase(), providerId);
            }
          }
          if (p.defaultModel) {
            this.modelToProvider.set(p.defaultModel.toLowerCase(), providerId);
          }
        }
      }
    } catch (err) {
      console.error(`[ProviderRegistry] Failed to load config at ${this.configPath}:`, err.message);
    }
  }

  /**
   * Find provider for a given model ID
   * Supports prefixes like 'groq/llama-3.3-70b-versatile' or exact model name 'mistral-small-latest'
   * @param {string} model
   * @returns {{ providerId: string, modelId: string, providerConfig: Object } | null}
   */
  resolveModel(model) {
    if (!model || typeof model !== 'string') return null;
    const lower = model.toLowerCase().trim();

    // Check prefix format: 'provider/model'
    if (lower.includes('/')) {
      const parts = lower.split('/');
      const prefix = parts[0];
      const modelPart = parts.slice(1).join('/');
      if (this.providers[prefix]) {
        return {
          providerId: prefix,
          modelId: modelPart,
          config: this.providers[prefix]
        };
      }
    }

    // Direct model lookup in catalog
    const providerId = this.modelToProvider.get(lower);
    if (providerId && this.providers[providerId]) {
      return {
        providerId,
        modelId: model,
        config: this.providers[providerId]
      };
    }

    // Fallback: check if model name starts with provider id
    for (const [pId, p] of Object.entries(this.providers)) {
      if (lower.startsWith(pId)) {
        return {
          providerId: pId,
          modelId: model,
          config: p
        };
      }
    }

    return null;
  }

  /**
   * Get all registered providers
   */
  getAllProviders() {
    return this.providers;
  }

  /**
   * Get provider by ID
   * @param {string} providerId
   */
  getProvider(providerId) {
    return this.providers[providerId] || null;
  }

  /**
   * Get all models across all providers
   */
  getAllModels() {
    const list = [];
    for (const [pId, p] of Object.entries(this.providers)) {
      if (Array.isArray(p.models)) {
        for (const m of p.models) {
          list.push({
            id: m,
            object: 'model',
            owned_by: pId,
            tier: p.tier,
            free_quota: p.freeQuotaMonthly
          });
        }
      }
    }
    return list;
  }
}
