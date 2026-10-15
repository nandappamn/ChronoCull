---
name: browser-use
description: >-
  Automate web browsing, scraping, interaction, and multi-step web workflows.
  Use this skill when the user asks to navigate websites, click elements, fill forms,
  extract live dynamic data from the web, or run browser-based agent tasks.
---

# Browser Use Skill

This skill equips the agent to automate web browsing using the [`browser-use`](https://github.com/browser-use/browser-use) framework. It enables headless or headed navigation, form submission, dynamic DOM inspection, and visual verification.

## When to Use

- Navigating web pages requiring authentication or dynamic JavaScript execution.
- Automating form submissions, checkout flows, or web application actions.
- Extracting content behind pagination, infinite scrolling, or interactive filters.
- Capturing screenshots or recording visual verification traces of web apps.

---

## Installation & Environment Setup

Ensure the browser environment has the required dependencies:

```bash
# Install browser-use and playwright
pip install browser-use playwright
playwright install
```

---

## Standard Execution Procedure

### 1. Define the High-Level Goal
Formulate a concise, unambiguous objective for the browser agent:
- Target URL
- Specific actions (search, click button with text X, extract table Y)
- Expected completion criteria or output format

### 2. Run the Task via Helper Script
Use the provided runner script in `scripts/run_browser_task.py`:

```bash
python .agents/skills/browser-use/scripts/run_browser_task.py --task "Go to news.ycombinator.com and extract top 5 stories" --headless
```

### 3. Programmatic Pattern

```python
import asyncio
from browser_use import Agent
from langchain_openai import ChatOpenAI  # or langchain_google_genai

async def main():
    agent = Agent(
        task="Navigate to target URL and extract relevant data",
        llm=ChatOpenAI(model="gpt-4o"),
    )
    result = await agent.run()
    print(result)

if __name__ == '__main__':
    asyncio.run(main())
```

---

## Best Practices & Safety

1. **Avoid Hardcoded Secrets**: Never pass raw passwords or API tokens in command-line arguments. Use environment variables.
2. **Headless by Default**: Run in headless mode in CI/CD or automated terminal environments.
3. **Handle CAPTCHAs & Rate Limits**: If a page triggers Cloudflare or bot protection, report gracefully rather than hammering the endpoint.
4. **Log Traces**: Save traces and screenshots to `artifacts/browser/` for debugging.
