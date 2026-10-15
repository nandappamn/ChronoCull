#!/usr/bin/env python3
"""
Browser Use Runner Script
Executes an automated browser task using browser-use or Playwright.
"""
import sys
import argparse
import asyncio

async def run_task(task_description: str, headless: bool = True):
    print(f"[browser-use] Initializing task: '{task_description}' (headless={headless})")
    try:
        from browser_use import Agent
        from langchain_openai import ChatOpenAI
        
        agent = Agent(
            task=task_description,
            llm=ChatOpenAI(model="gpt-4o-mini"),
            use_vision=True
        )
        result = await agent.run()
        print("[browser-use] Task completed successfully.")
        print(result)
        return result
    except ImportError:
        print("[browser-use] Warning: 'browser-use' library not installed in current environment.")
        print("To install: pip install browser-use playwright && playwright install")
        print(f"[browser-use] Simulating dry run execution for: {task_description}")
        return {"status": "simulated", "task": task_description}

def main():
    parser = argparse.ArgumentParser(description="Run an automated browser task")
    parser.add_argument("--task", type=str, required=True, help="Task description for the agent")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode")
    parser.add_argument("--headed", dest="headless", action="store_false", help="Run browser in headed mode")
    args = parser.parse_args()

    asyncio.run(run_task(args.task, headless=args.headless))

if __name__ == "__main__":
    main()
