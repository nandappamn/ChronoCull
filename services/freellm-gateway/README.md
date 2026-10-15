# FreeLLM Gateway

A modular, zero-dependency Node.js AI proxy that aggregates high-yield free LLM providers, manages multi-key rotation with automatic 429 failover, and multiplies effective token capacity via stacked **RTK (Recursive Token Killer)** and **Caveman** prompt compression.

---

## ⚡ Key Highlights

1. **High-Yield Free Provider Catalog**:
   - **Mistral AI**: ~1.0 Billion tokens/month (`mistral-small-latest`, `codestral-latest`, `open-mistral-nemo`)
   - **LLM7**: ~150 Million tokens/month (`llm7-free`)
   - **Groq**: ~117 Million tokens/month (`llama-3.3-70b-versatile`, `mixtral-8x7b-32768`)
   - **Google Gemini**: ~60 Million tokens/month (`gemini-2.5-flash`, `gemini-3.0-flash`)
   - **Cerebras & SambaNova**: ~30 Million tokens/month each (Ultra-fast Llama-3.3-70B)
   - **Cloudflare Workers AI**: ~30 Million tokens/month (10k Neurons/day)
   - **SiliconFlow & Z.AI (GLM-4-Flash)**: Permanently free uncapped tiers

2. **Multi-Key Pooling & Project Rotation**:
   - Accepts multiple API keys per provider in `config/keys.json`.
   - Dispatches requests using **Least-Recently-Used (LRU)** or **Round-Robin**.
   - Automatic **429 Rate Limit Cooldown**: When a key hits a rate limit, it is quarantined with exponential backoff while the router immediately retries the request using the next healthy key in the pool.

3. **Stacked Prompt Compression (RTK + Caveman)**:
   - **RTK (Recursive Token Killer)**: Compresses terminal and tool outputs. Strips ANSI escape codes, terminal spinners, git diff metadata/hashes, repetitive test logs, and internal framework stack traces.
   - **Caveman Engine**: Condenses conversation prose, removes polite hedging ("Sure!", "I'd be happy to help", "As an AI..."), while **strictly shielding code blocks, URLs, and file paths**.
   - **Stacked Mode**: Executes `RTK ➔ Caveman` on inbound payloads, slashing token consumption by **20% to 80%** without quality degradation.

---

## 🚀 Quick Start

### 1. Configure Your API Keys
Edit `config/keys.json` with one or more free API keys for each provider (or provide them via root `.env` / environment variables):

```json
{
  "mistral": ["your_mistral_key_1", "your_mistral_key_2"],
  "groq": ["gsk_groq_key_1", "gsk_groq_key_2"],
  "gemini": ["AIzaSy_gemini_key_1"]
}
```

The server also automatically loads `.env` and supports:
- `FREELLM_PORT` (default: `20128`)
- `FREELLM_HOST` (default: `127.0.0.1`)
- `FREELLM_COMPRESSION_MODE` (default: `stacked`, options: `stacked`, `rtk`, `caveman`, `none`)

### 2. Start the Gateway
```bash
node src/server.js
# Or
npm start
```
The gateway boots on `http://127.0.0.1:20128`.

### 3. Verify Health & Models
```bash
# Check health and key pool stats
curl http://127.0.0.1:20128/health

# List available models
curl http://127.0.0.1:20128/v1/models
```

---

## 🔌 Connecting Coding Agents & Tools

Any OpenAI-compatible tool connects seamlessly by setting:
- **Base URL**: `http://127.0.0.1:20128/v1`
- **API Key**: `any-key` (the gateway uses its internal key pool)

### Cursor / Cline / Roo Code / Claude Code
Configure the OpenAI Compatible provider:
- **API Base URL**: `http://127.0.0.1:20128/v1`
- **Model**: `auto` (cascades across all active free tiers) or a specific model like `llama-3.3-70b-versatile` or `mistral-small-latest`.

### cURL Example with Compression Headers
```bash
curl http://127.0.0.1:20128/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-FreeLLM-Compress: stacked" \
  -d '{
    "model": "auto",
    "messages": [
      {
        "role": "user",
        "content": "Hello! Could you please help me check why this fails: \n\u001b[31mFAIL\u001b[39m tests/auth.test.js\nRan 1 test. 1 failed."
      }
    ]
  }'
```

Response headers will show exact savings:
```http
X-FreeLLM-Compress: stacked; rtk_saved=18; caveman_saved=32; saved~=13
X-Routed-Provider: groq
X-Routed-Model: llama-3.3-70b-versatile
```

---

## 🧪 Testing

Run the automated test suite with Node.js built-in test runner:
```bash
npm test
```
All 12 test assertions (RTK noise removal, Caveman code shielding, multi-key rotation, and 429 failover) run in milliseconds with zero dependencies.
