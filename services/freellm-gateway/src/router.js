/**
 * Intelligent Cascading Router with Multi-Key Rotation and Fallback
 */

export class SmartRouter {
  /**
   * @param {Object} options
   * @param {import('./providers/registry.js').ProviderRegistry} options.registry
   * @param {import('./keyPool.js').KeyPoolManager} options.keyPool
   * @param {import('./compression/pipeline.js').CompressionPipeline} options.compression
   */
  constructor({ registry, keyPool, compression }) {
    this.registry = registry;
    this.keyPool = keyPool;
    this.compression = compression;
  }

  /**
   * Route a chat completion request with key rotation and cascade
   * @param {Object} body Original OpenAI chat payload
   * @param {Object} [options]
   * @param {string} [options.compressionMode='stacked']
   * @param {Function} [options.fetchFn=globalThis.fetch]
   */
  async routeChatCompletion(body, options = {}) {
    const compMode = options.compressionMode || this.compression.defaultMode;
    const fetchFn = options.fetchFn || globalThis.fetch;

    // 1. Run prompt compression (RTK -> Caveman)
    const { payload, metrics, headerValue } = this.compression.compressChatPayload(body, compMode);

    // 2. Identify candidate providers and models
    const requestedModel = payload.model || 'auto';
    const candidateChain = this.buildCandidateChain(requestedModel);

    if (candidateChain.length === 0) {
      throw new Error(`No available providers configured for model: ${requestedModel}`);
    }

    let lastError = null;

    // 3. Cascade across candidate providers and keys
    for (const candidate of candidateChain) {
      const { providerId, modelId, config } = candidate;

      // Try available keys for this provider
      const triedKeys = new Set();

      while (true) {
        const apiKey = this.keyPool.getKey(providerId, 'lru');
        if (!apiKey || triedKeys.has(apiKey)) {
          // No more active healthy keys in this provider pool
          break;
        }
        triedKeys.add(apiKey);

        try {
          let effectiveBaseUrl = config.baseUrl.replace(/\/$/, '');
          if (effectiveBaseUrl.includes('{account_id}')) {
            const accountId = process.env.CLOUDFLARE_ACCOUNT_ID || '';
            effectiveBaseUrl = effectiveBaseUrl.replace('{account_id}', accountId);
          }
          const upstreamUrl = `${effectiveBaseUrl}/chat/completions`;
          const reqBody = { ...payload, model: modelId };

          const res = await fetchFn(upstreamUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify(reqBody)
          });

          // Handle 429 Too Many Requests (Rate limit)
          if (res.status === 429) {
            const cooldown = this.keyPool.markRateLimited(providerId, apiKey);
            console.warn(`[Router] Provider ${providerId} key rate-limited (429). Placed on ${cooldown}ms cooldown. Retrying next key...`);
            continue; // Try next key
          }

          // Handle 401/403 (Invalid key or quota depleted)
          if (res.status === 401 || res.status === 403) {
            this.keyPool.markRateLimited(providerId, apiKey, 300000); // 5 min cooldown
            console.warn(`[Router] Provider ${providerId} key rejected (${res.status}). Quarantining key. Retrying next...`);
            continue;
          }

          if (!res.ok) {
            const errText = await res.text();
            this.keyPool.markFailure(providerId, apiKey);
            throw new Error(`Provider ${providerId} returned ${res.status}: ${errText.slice(0, 300)}`);
          }

          // Request succeeded!
          this.keyPool.markSuccess(providerId, apiKey);
          const data = await res.json();

          return {
            status: 200,
            data,
            providerId,
            modelId,
            compressionMetrics: metrics,
            compressionHeader: headerValue
          };

        } catch (err) {
          lastError = err;
          // Continue to next key or candidate
        }
      }
    }

    throw new Error(`All providers and key pools failed for ${requestedModel}. Last error: ${lastError ? lastError.message : 'No healthy keys'}`);
  }

  /**
   * Build priority cascade chain of candidate providers
   * @param {string} requestedModel
   */
  buildCandidateChain(requestedModel) {
    const chain = [];
    const isAuto = requestedModel === 'auto' || requestedModel === 'auto:free';

    if (isAuto) {
      // Prioritize Tier 1 -> Tier 2 -> Tier 3 providers that have active keys
      for (const tier of [1, 2, 3]) {
        const pIds = this.registry.tierGroups[tier] || [];
        for (const pId of pIds) {
          const config = this.registry.getProvider(pId);
          if (config) {
            chain.push({
              providerId: pId,
              modelId: config.defaultModel,
              config
            });
          }
        }
      }
      return chain;
    }

    // Explicit model requested
    const resolved = this.registry.resolveModel(requestedModel);
    if (resolved) {
      chain.push(resolved);
    }

    // Add fallback providers from Tier 1 if the primary provider fails
    for (const pId of this.registry.tierGroups[1] || []) {
      if (!resolved || pId !== resolved.providerId) {
        const config = this.registry.getProvider(pId);
        if (config) {
          chain.push({
            providerId: pId,
            modelId: config.defaultModel,
            config
          });
        }
      }
    }

    return chain;
  }
}
