import os
import json
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory
from supabase import Client, create_client

app = Flask(__name__, static_folder="static")
CONTACT_STATUSES = {"lead", "active", "customer", "inactive"}
DEAL_STAGES = {"lead", "qualified", "proposal", "negotiation", "won", "lost"}


def db() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured")
    return create_client(url, key)


def utcnow():
    return datetime.now(timezone.utc)


def json_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return None
    return body


def error(message, status=400):
    return jsonify({"error": message}), status


def parse_timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def stalled_records(client):
    """Return one actionable open opportunity per contact after seven quiet days."""
    contacts = {row["id"]: row for row in client.table("contacts").select("*").execute().data}
    activities = client.table("activities").select("contact_id, occurred_at").execute().data
    deals = client.table("deals").select("*").execute().data
    drafts = client.table("follow_up_drafts").select("contact_id").eq("status", "pending").execute().data
    already_pending = {row["contact_id"] for row in drafts}
    latest_activity = defaultdict(lambda: None)
    for activity in activities:
        occurred = parse_timestamp(activity["occurred_at"])
        contact_id = activity["contact_id"]
        if latest_activity[contact_id] is None or occurred > latest_activity[contact_id]:
            latest_activity[contact_id] = occurred
    cutoff = utcnow().timestamp() - 7 * 24 * 60 * 60
    candidates = []
    for deal in deals:
        if deal["stage"] in ("won", "lost") or deal["contact_id"] in already_pending:
            continue
        last_activity = latest_activity[deal["contact_id"]]
        deal_updated = parse_timestamp(deal["updated_at"])
        is_quiet = (last_activity is None or last_activity.timestamp() < cutoff)
        is_stale_deal = deal_updated.timestamp() < cutoff
        if is_quiet or is_stale_deal:
            reason = "No recorded activity in the last seven days" if is_quiet else "Opportunity has not been updated in the last seven days"
            candidates.append({"contact": contacts[deal["contact_id"]], "deal": deal, "reason": reason, "last_activity": last_activity})
    return candidates


def openrouter_draft(context):
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY must be configured before drafting follow-ups")
    prompt = f'''You are a careful B2B sales assistant. Write a warm, concise follow-up draft for this CRM record. Never claim an action was performed, never propose sending automatically, and do not invent facts. Return only valid JSON with keys: subject, body, suggested_next_action.\n\nContact: {context["contact"]["name"]}, {context["contact"].get("title") or ""} at {context["contact"].get("company") or "their company"}\nOpportunity: {context["deal"]["name"]}, stage {context["deal"]["stage"]}, value ${context["deal"]["value"]}\nStall signal: {context["reason"]}.'''
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/responses",
        data=json.dumps({"model": os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"), "input": prompt}).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "X-OpenRouter-Title": "Orbit CRM"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    text = result.get("output_text")
    if not text:
        for item in result.get("output", []):
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text = part.get("text")
                    break
    if not text:
        raise RuntimeError("OpenRouter did not return draft text")
    return json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())


def run_follow_up_agent():
    client = db()
    candidates = stalled_records(client)
    created = 0
    for candidate in candidates:
        draft = openrouter_draft(candidate)
        client.table("follow_up_drafts").insert({
            "contact_id": candidate["contact"]["id"], "deal_id": candidate["deal"]["id"],
            "rationale": candidate["reason"], "subject": draft["subject"], "body": draft["body"],
            "suggested_next_action": draft["suggested_next_action"], "status": "pending",
        }).execute()
        created += 1
    client.table("agent_runs").insert({"status": "completed", "draft_count": created}).execute()
    return created


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard():
    client = db()
    contacts = client.table("contacts").select("*").order("created_at", desc=True).execute().data
    deals = client.table("deals").select("*, contacts(name, company)").order("updated_at", desc=True).execute().data
    activities = client.table("activities").select("*, contacts(name)").order("occurred_at", desc=True).limit(8).execute().data
    stages = ["lead", "qualified", "proposal", "negotiation", "won", "lost"]
    pipeline = {stage: sum(float(d["value"]) for d in deals if d["stage"] == stage) for stage in stages}
    return jsonify({
        "contacts": contacts,
        "deals": deals,
        "activities": activities,
        "metrics": {
            "contact_count": len(contacts),
            "open_pipeline": sum(float(d["value"]) for d in deals if d["stage"] not in ("won", "lost")),
            "won_value": pipeline["won"],
            "pipeline": pipeline,
        },
    })


@app.get("/api/follow-ups")
def follow_ups():
    drafts = db().table("follow_up_drafts").select("*, contacts(name, email, company), deals(name, value, stage)").order("created_at", desc=True).execute().data
    return jsonify(drafts)


@app.post("/api/follow-ups/<draft_id>/review")
def review_follow_up(draft_id):
    payload = json_body()
    if payload is None:
        return error("A JSON decision is required.")
    decision = payload.get("decision")
    if decision not in ("approved", "rejected"):
        return error("Decision must be approved or rejected.")
    result = db().table("follow_up_drafts").update({"status": decision, "reviewed_at": utcnow().isoformat()}).eq("id", draft_id).eq("status", "pending").execute()
    if not result.data:
        return error("Draft is no longer pending.", 409)
    # Approval only records a human decision. This application has no email-sending code or integration.
    return jsonify(result.data[0])


@app.post("/api/agent/run")
def run_agent():
    token = request.headers.get("X-Agent-Token", "")
    if not token or token != os.environ.get("AGENT_RUN_TOKEN"):
        return error("Unauthorized agent invocation.", 401)
    try:
        return jsonify({"drafts_created": run_follow_up_agent()})
    except Exception as error:
        db().table("agent_runs").insert({"status": "failed", "error": str(error), "draft_count": 0}).execute()
        return error("Agent run failed. Review server logs.", 500)


@app.post("/api/contacts")
def create_contact():
    payload = json_body()
    if payload is None:
        return error("A JSON contact is required.")
    required = ("name", "email")
    if any(not isinstance(payload.get(field), str) or not payload[field].strip() for field in required):
        return error("Name and email are required.")
    if "@" not in payload["email"]:
        return error("Enter a valid email address.")
    status = payload.get("status", "lead")
    if status not in CONTACT_STATUSES:
        return error("Invalid contact status.")
    record = {
        "name": payload["name"].strip(), "email": payload["email"].strip(),
        "company": payload.get("company", "").strip() or None,
        "title": payload.get("title", "").strip() or None,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = db().table("contacts").insert(record).execute()
    return jsonify(result.data[0]), 201


@app.post("/api/deals")
def create_deal():
    payload = json_body()
    if payload is None:
        return error("A JSON deal is required.")
    if not isinstance(payload.get("name"), str) or not payload["name"].strip() or not payload.get("contact_id"):
        return error("Deal name and contact are required.")
    stage = payload.get("stage", "lead")
    if stage not in DEAL_STAGES:
        return error("Invalid deal stage.")
    try:
        value = float(payload.get("value") or 0)
    except (TypeError, ValueError):
        return error("Deal value must be a number.")
    if value < 0:
        return error("Deal value cannot be negative.")
    record = {
        "name": payload["name"].strip(), "contact_id": payload["contact_id"],
        "value": value, "stage": stage,
        "expected_close": payload.get("expected_close") or None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = db().table("deals").insert(record).execute()
    return jsonify(result.data[0]), 201


@app.patch("/api/deals/<deal_id>")
def update_deal(deal_id):
    payload = json_body()
    if payload is None:
        return error("A JSON deal update is required.")
    allowed = {key: payload[key] for key in ("stage", "name", "value", "expected_close") if key in payload}
    if not allowed:
        return error("Provide at least one deal field to update.")
    if "stage" in allowed and allowed["stage"] not in DEAL_STAGES:
        return error("Invalid deal stage.")
    if "name" in allowed and (not isinstance(allowed["name"], str) or not allowed["name"].strip()):
        return error("Deal name cannot be empty.")
    if "name" in allowed:
        allowed["name"] = allowed["name"].strip()
    if "value" in allowed:
        try:
            allowed["value"] = float(allowed["value"])
        except (TypeError, ValueError):
            return error("Deal value must be a number.")
        if allowed["value"] < 0:
            return error("Deal value cannot be negative.")
    allowed["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = db().table("deals").update(allowed).eq("id", deal_id).execute()
    if not result.data:
        return error("Deal not found.", 404)
    return jsonify(result.data[0])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

