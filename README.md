# Orbit CRM

A lightweight CRM built with a single Tailwind-styled HTML frontend, a Flask API, and Supabase storage.

## Local setup

1. Create a Python virtual environment and install `requirements.txt`.
2. Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in your environment.
3. Run `flask --app app run`.

The service-role key must remain server-side. The browser never connects directly to Supabase.

## Deployment

Railway uses `railway.toml` and starts the service with Gunicorn. Configure these Railway service variables:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

