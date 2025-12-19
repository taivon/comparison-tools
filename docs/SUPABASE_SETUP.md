# Supabase Setup Guide

This guide covers how to connect your Django app to Supabase PostgreSQL.

## 1. Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign in
2. Click "New Project"
3. Choose your organization and set:
   - Project name
   - Database password (save this!)
   - Region (choose closest to your users)
4. Wait for the project to be created (~2 minutes)

## 2. Get Database Credentials

1. In your Supabase dashboard, go to **Settings** → **Database**
2. Scroll to **Connection parameters** section
3. Note down these values:
   - Host (e.g., `db.xxxxxxxxxxxx.supabase.co`)
   - Database name (usually `postgres`)
   - Port (usually `5432`)
   - User (usually `postgres`)
   - Password (the one you set during project creation)

Alternatively, copy the **Connection string** (URI format) from the same page.

## 3. Local Development Setup

Add these to your `.env` file:

```env
# Supabase Database
SUPABASE_DB_HOST=db.xxxxxxxxxxxx.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your-database-password
SUPABASE_DB_PORT=5432
```

## 4. Run Migrations

Once credentials are set, run migrations to create tables in Supabase:

```bash
python manage.py migrate
```

Verify by checking the Supabase dashboard → **Table Editor** - you should see tables like:
- `auth_user`
- `apartments_apartment`
- `apartments_userpreferences`
- `apartments_userprofile`
- `django_session`
- etc.

## 5. Production Setup (Google Cloud)

For production on Google App Engine, add secrets to Google Secret Manager:

```bash
# Add each secret
gcloud secrets create supabase-db-host --data-file=-
gcloud secrets create supabase-db-name --data-file=-
gcloud secrets create supabase-db-user --data-file=-
gcloud secrets create supabase-db-password --data-file=-
gcloud secrets create supabase-db-port --data-file=-
```

Or via the Google Cloud Console:
1. Go to **Security** → **Secret Manager**
2. Click **Create Secret** for each:
   - `supabase-db-host` → your Supabase host
   - `supabase-db-name` → `postgres`
   - `supabase-db-user` → `postgres`
   - `supabase-db-password` → your database password
   - `supabase-db-port` → `5432`

## 6. Connection Pooling (Recommended for Production)

For production, use Supabase's connection pooler to handle multiple connections:

1. In Supabase dashboard, go to **Settings** → **Database**
2. Find **Connection Pooling** section
3. Use the **Pooler** connection string instead of direct connection
4. Update your host to use the pooler URL (usually `pooler.xxxx.supabase.co`)

Update your settings to use port `6543` (pooler port) instead of `5432`.

## 7. SSL Configuration

The Django settings already include SSL:

```python
"OPTIONS": {
    "sslmode": "require",
}
```

This ensures all connections to Supabase are encrypted.

## 8. Troubleshooting

### Connection Refused
- Check that your IP is allowed in Supabase (Settings → Database → Network)
- Verify credentials are correct
- Ensure SSL is enabled

### Timeout Errors
- Use connection pooling for production
- Check if Supabase project is paused (free tier pauses after inactivity)

### Migration Errors
- Ensure the database user has CREATE permissions
- Check for existing tables that might conflict

## 9. Backup & Data

Supabase provides:
- **Automatic backups** (Pro plan)
- **Point-in-time recovery** (Pro plan)
- **Database dumps** via `pg_dump`

To export data:
```bash
pg_dump "postgresql://postgres:PASSWORD@HOST:5432/postgres" > backup.sql
```

## Environment Variables Summary

| Variable | Description | Example |
|----------|-------------|---------|
| `SUPABASE_DB_HOST` | Database host | `db.xxx.supabase.co` |
| `SUPABASE_DB_NAME` | Database name | `postgres` |
| `SUPABASE_DB_USER` | Database user | `postgres` |
| `SUPABASE_DB_PASSWORD` | Database password | `your-secure-password` |
| `SUPABASE_DB_PORT` | Database port | `5432` (or `6543` for pooler) |
