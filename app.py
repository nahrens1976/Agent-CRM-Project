import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory
from supabase import Client, create_client

app = Flask(__name__, static_folder="static")


def db() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured")
    return create_client(url, key)


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


@app.post("/api/contacts")
def create_contact():
    payload = request.get_json(force=True)
    required = ("name", "email")
    if any(not payload.get(field, "").strip() for field in required):
        return jsonify({"error": "Name and email are required."}), 400
    record = {
        "name": payload["name"].strip(), "email": payload["email"].strip(),
        "company": payload.get("company", "").strip() or None,
        "title": payload.get("title", "").strip() or None,
        "status": payload.get("status", "lead"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = db().table("contacts").insert(record).execute()
    return jsonify(result.data[0]), 201


@app.post("/api/deals")
def create_deal():
    payload = request.get_json(force=True)
    if not payload.get("name", "").strip() or not payload.get("contact_id"):
        return jsonify({"error": "Deal name and contact are required."}), 400
    record = {
        "name": payload["name"].strip(), "contact_id": payload["contact_id"],
        "value": float(payload.get("value") or 0), "stage": payload.get("stage", "lead"),
        "expected_close": payload.get("expected_close") or None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = db().table("deals").insert(record).execute()
    return jsonify(result.data[0]), 201


@app.patch("/api/deals/<deal_id>")
def update_deal(deal_id):
    payload = request.get_json(force=True)
    allowed = {key: payload[key] for key in ("stage", "name", "value", "expected_close") if key in payload}
    allowed["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = db().table("deals").update(allowed).eq("id", deal_id).execute()
    return jsonify(result.data[0])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

