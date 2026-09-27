#!/usr/bin/env python3
"""
Fetch available LLM models from active provider endpoints.
"""
import os
import json
import urllib.request
import urllib.error

PROVIDERS = {
    "OpenRouter": {
        "url": "https://openrouter.ai/api/v1/models",
        "headers": lambda key: {"Authorization": f"Bearer {key}"} if key else {}
    },
    "Anthropic": {
        "url": "https://api.anthropic.com/v1/models",
        "headers": lambda key: {"x-api-key": key, "anthropic-version": "2023-06-01"} if key else {}
    },
    "OpenAI": {
        "url": "https://api.openai.com/v1/models",
        "headers": lambda key: {"Authorization": f"Bearer {key}"} if key else {}
    },
    "Google Gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models",
        "headers": lambda key: {}
    }
}

def fetch_models():
    print("=== Live LLM Model Discovery Tool ===")
    
    # 1. OpenRouter (Public endpoint - works without key)
    try:
        req = urllib.request.Request(PROVIDERS["OpenRouter"]["url"])
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            print("\n[OpenRouter Public Catalog (Live)]")
            anthropic = [m['id'] for m in data.get('data', []) if 'anthropic' in m['id']]
            openai = [m['id'] for m in data.get('data', []) if 'openai' in m['id']]
            gemini = [m['id'] for m in data.get('data', []) if 'google' in m['id'] or 'gemini' in m['id']]
            
            print(f"• Anthropic Models ({len(anthropic)}):", anthropic[:5])
            print(f"• OpenAI Models ({len(openai)}):", openai[:5])
            print(f"• Gemini Models ({len(gemini)}):", gemini[:5])
    except Exception as e:
        print("OpenRouter query failed:", e)

    # 2. Check Local Ollama
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            models = [m['name'] for m in data.get('models', [])]
            print("\n[Local Ollama Models]")
            print("• Installed:", models)
    except Exception as e:
        print("\n[Local Ollama] Not running on localhost:11434")

if __name__ == "__main__":
    fetch_models()
