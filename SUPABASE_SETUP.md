# Supabase persistence setup

The app can save every manual input record, including its date, source, frequency, notes, value, previous value, and forecast. On a fresh Streamlit session it loads those records back from Supabase.

## 1. Create the table

Open your Supabase project's **SQL Editor**, paste the contents of [supabase/setup.sql](supabase/setup.sql), and run it. The table has row-level security enabled and grants table access only to the server-side `service_role`. Browser-facing `anon` and `authenticated` roles receive no table access.

## 2. Configure the Streamlit server

Add these values to Streamlit's server-side secrets. For local development, put them in `.streamlit/secrets.toml`; in Streamlit Community Cloud, use the app's **Settings → Secrets** page.

```toml
SUPABASE_URL = "https://<project-ref>.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_..."
```

A legacy `service_role` key is also accepted as `SUPABASE_SERVICE_ROLE_KEY`. Use the project URL from Supabase **Connect** and the secret key from **Settings → API Keys**. Never commit a real secret key or place it in browser-delivered code.

Environment variables named `SUPABASE_URL` and `SUPABASE_SECRET_KEY` are also supported.

## 3. Keep the app private

This version uses a server-side secret key and does not add user sign-in. Anyone who can open the Streamlit app can read or change the shared manual dataset through the app. Restrict access to the Streamlit deployment to yourself or a trusted group. The secret key stays on the server, but it bypasses row-level security for server requests.

## Behavior

- With Supabase settings present, the app loads saved values on startup and saves the manual-data snapshot after the input page updates.
- **Load illustrative sample data** saves the sample to Supabase too.
- **Reset all data** deletes the shared manual records from Supabase.
- Without Supabase settings, the app falls back to its original in-memory behavior and displays a setup notice.
