import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Lazy initialization - client created on first use
_supabase_client: Client | None = None

def get_supabase_client() -> Client:
    """Get or create the Supabase client.
    
    Uses lazy initialization to allow module import without env vars.
    Raises ValueError at runtime if credentials are missing.
    """
    global _supabase_client
    
    if _supabase_client is None:
        url: str | None = os.environ.get("SUPABASE_URL")
        key: str | None = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("Supabase URL and Key must be set in .env file")
        
        _supabase_client = create_client(url, key)
    
    return _supabase_client
