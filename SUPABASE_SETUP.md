# Supabase persistence setup

Manual inputs (value, previous, forecast, date, source, frequency, notes) are saved to a
Supabase table and reloaded when the app starts.

1. Run `supabase/setup.sql` once in the Supabase SQL Editor (creates `manual_values`, RLS on,
   no browser access).
2. In Streamlit "Settings -> Secrets" add:

```
SUPABASE_URL = "https://<project-ref>.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_..."
APP_PASSWORD = "choose-a-strong-password"
```

Never commit the secret key to GitHub. `APP_PASSWORD` is optional but recommended: the app
shares one dataset and has no user accounts, so anyone who can open it can edit the data.

Without Supabase secrets the app falls back to temporary in-memory data.
