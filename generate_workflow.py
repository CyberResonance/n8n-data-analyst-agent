#!/usr/bin/env python3
"""Builds Data_Analyst_Agent.json (importable n8n workflow) from profile_data.js."""
import json
from pathlib import Path

HERE = Path(__file__).parent
PROFILE_JS = (HERE / "profile_data.js").read_text(encoding="utf-8")

FORMAT_JS = """const res = $input.first().json;
const answer = res.candidates?.[0]?.content?.parts?.map(p => p.text).join('') || 'No answer returned by Gemini.';
const ctx = $('Profile Data & Build Prompt').first().json;
return [{ json: {
  question: ctx.question,
  answer,
  rows: ctx.profile.rowCount,
  columns: ctx.profile.columns.map(c => c.name)
} }];"""


def node(name, type_, params, pos, ver=1, **extra):
    return {"parameters": params, "name": name, "type": type_,
            "typeVersion": ver, "position": pos, **extra}


nodes = [
    node("Manual Trigger", "n8n-nodes-base.manualTrigger", {}, [-600, 140]),
    node("Webhook", "n8n-nodes-base.webhook",
         {"httpMethod": "POST", "path": "analyze-data", "responseMode": "responseNode", "options": {}},
         [-600, 340], 2, webhookId="data-analyst-agent-webhook"),
    node("Profile Data & Build Prompt", "n8n-nodes-base.code", {"jsCode": PROFILE_JS}, [-340, 240], 2),
    node("Gemini Analyst", "n8n-nodes-base.httpRequest", {
        "method": "POST",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        # API key comes from the n8n credential "Google Gemini(PaLM) Api" (no $env: recent n8n blocks env access in nodes).
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "googlePalmApi",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "Content-Type", "value": "application/json"}]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify($json.requestBody) }}",
        "options": {"timeout": 60000}}, [-80, 240], 4.2,
        credentials={"googlePalmApi": {"id": "", "name": "Gemini API"}}),
    node("Format Answer", "n8n-nodes-base.code", {"jsCode": FORMAT_JS}, [180, 240], 2),
    node("Respond to Webhook", "n8n-nodes-base.respondToWebhook",
         {"respondWith": "json", "responseBody": "={{ $json }}", "options": {}}, [440, 240], 1.1),
]

conn = lambda target: {"main": [[{"node": target, "type": "main", "index": 0}]]}
workflow = {
    "name": "Data Analyst Agent",
    "nodes": nodes,
    "connections": {
        "Manual Trigger": conn("Profile Data & Build Prompt"),
        "Webhook": conn("Profile Data & Build Prompt"),
        "Profile Data & Build Prompt": conn("Gemini Analyst"),
        "Gemini Analyst": conn("Format Answer"),
        "Format Answer": conn("Respond to Webhook"),
    },
    "settings": {"executionOrder": "v1"},
}

if __name__ == "__main__":
    out = HERE / "Data_Analyst_Agent.json"
    out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out}")
