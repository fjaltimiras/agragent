from app.config import settings


def get_db():
    """
    Return a database client.
    Uses Supabase when credentials are configured, otherwise falls back to
    a local SQLite adapter with the same query-builder interface.
    """
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY
    if settings.SUPABASE_URL and key:
        from supabase import create_client
        return create_client(settings.SUPABASE_URL, key)

    from app.local_db import get_local_db
    return get_local_db()


def get_user_db(jwt_token: str):
    """Return a user-scoped database client (Supabase only)."""
    if settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY:
        from supabase import create_client
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        client.auth.set_session(jwt_token, "")
        return client

    from app.local_db import get_local_db
    return get_local_db()
