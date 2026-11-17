# Agent Instructions

## Product

Build and maintain a CRM application called Orbit CRM.

## Required stack

- Frontend: one HTML file styled with Tailwind CSS and using inline JavaScript for interactivity.
- Backend: a simple Flask server.
- Storage: Supabase Postgres database; do not use JSON files as application storage.
- Source control: GitHub repository `nahrens1976/Agent-CRM-Project`.
- Hosting: Railway.

## Deployment and secrets

- Deploy the Flask application to Railway from the GitHub repository.
- Keep all secrets server-side as Railway environment variables. Never place secrets in frontend code, source files, commits, logs, or `.env.example`.
- Use the names documented in `.env.example`: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, and `AGENT_RUN_TOKEN`.
- Commit `.env.example` with placeholders only. Keep `.env` ignored.
- Supabase service-role access is backend-only. Enable RLS for tables in the exposed `public` schema and do not grant direct browser access to CRM data.

## CRM behavior

- Maintain contacts, deals, activities, dashboard metrics, and pipeline views in Supabase.
- Seed the database with synthetic data for demonstration and testing.

## Follow-up agent

Create an autonomous, approval-based CRM follow-up agent that runs each morning once its Railway/OpenRouter configuration is present.

1. Identify stalled contacts and open opportunities, using at least seven days without meaningful activity or deal updates as the stall signal.
2. Send only the relevant CRM context to OpenRouter and generate a personalized draft.
3. Store the draft, rationale, and suggested next action in Supabase.
4. Present every draft in a human review queue with Approve and Reject controls.
5. Do not automatically send email. Approval only records the human decision; this application must not contain an email-sending integration.
6. Avoid duplicate pending drafts for the same contact.
7. Keep the OpenRouter key server-side and never expose it to the browser.

## Non-negotiable guardrails

- The agent may analyze CRM data and create internal, reviewable drafts only. It must never send email, create external records, or delete CRM data automatically. Server-side policy must block these actions even if a model proposes them.
- The agent must never invent contacts, companies, owners, customer decisions, or deadlines. When any required information is missing or ambiguous, leave it blank, explain what is missing, and route the suggestion for human review.
- Every guardrail decision must be recorded with the model input, proposed output, triggered guardrail, final action, and business-friendly blocking reason. Approval records a human decision only; it never sends email.
- Keep deterministic guardrail evaluation cases and automated tests for prohibited external actions and missing or ambiguous CRM information.

## Verification expectations

- Verify database changes with a read query and security advisor checks.
- Verify Railway deployments with the health endpoint and relevant API endpoints.
- Preserve this document as the project’s durable implementation brief; update it when requirements change.

