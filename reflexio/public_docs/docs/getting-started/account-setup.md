# Account Setup

Before using Reflexio, you'll need to set up your Supabase storage and register an account.

---

## Step 1: Get Your Supabase Credentials

Reflexio uses [Supabase](https://supabase.com/) to store your data. You'll need three values from your Supabase project:

### Supabase URL

Click **Connect** at the top of your Supabase dashboard, select the **App Frameworks** tab, and copy the `NEXT_PUBLIC_SUPABASE_URL` value.

Format: `https://<project-id>.supabase.co`

![Supabase Project URL](../assets/account-setup/supabase-project-url.png)

### Database URL (for migrations)

In the same **Connect** dialog, select the **ORMs** tab and copy the `DATABASE_URL` value (port 6543 for connection pooling).

![Supabase DB Connection](../assets/account-setup/supabase-db-connection.png)

### Supabase Anon Key

Navigate to **Project Settings → API Keys**, select the **Legacy anon, service_role API keys** tab, and copy the **anon** public key.

![Supabase API Keys](../assets/account-setup/supabase-api-keys.png)

---

## Step 2: Register and Configure Reflexio

### Create Your Account

1. Go to [https://www.reflexio.com/](https://www.reflexio.com/)
2. Click **Get Started** to register
3. Sign in to access the portal

### Configure Storage

1. Navigate to the **Settings** page
2. Under **Storage Configuration**, select **Supabase**
3. Enter your credentials:
   - Supabase URL
   - Supabase Anon Key
   - Database URL

![Storage Settings](../assets/account-setup/storage-settings.png)

### Add a Profile Extractor

1. Go to the **Extractor Settings** tab
2. Click **Add Profile Extractor**
3. Configure:
   - **Name**: e.g., `user_preferences`
   - **Profile Content Definition**: What to extract (e.g., "user name, interests, preferences")

![Profile Extractor](../assets/account-setup/profile-extractor.png)

> **Tip:** See the [Configuration Guide](configuration.md) for all extractor options.

### Save Configuration

1. Click **Save Configuration** at the top right
2. First save may take ~10 seconds for database migration

---

## Next Steps

- [Quick Start](quickstart.md) — Publish your first interaction
- [Configuration Guide](configuration.md) — Advanced extractor settings
- [Web Portal Usage](../web-portal/basic-usage.md) — Explore all portal features
