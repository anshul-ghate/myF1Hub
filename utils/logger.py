import logging
from datetime import datetime
from utils.db import get_supabase_client

class SupabaseHandler(logging.Handler):
    def __init__(self, component_name):
        super().__init__()
        self.supabase = get_supabase_client()
        self.component = component_name

    def emit(self, record):
        try:
            log_entry = {
                "level": record.levelname,
                "component": self.component,
                "message": self.format(record),
                "metadata": {"filename": record.filename, "lineno": record.lineno}
            }
            # Fire and forget to avoid blocking main execution flow too much
            # In production, might want to batch or use async
            self.supabase.table("app_logs").insert(log_entry).execute()
        except Exception as e:
            print(f"Failed to log to Supabase: {e}")

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Console Handler
    c_handler = logging.StreamHandler()
    c_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)
    
    # Supabase Handler
    s_handler = SupabaseHandler(name)
    s_handler.setFormatter(c_format)
    logger.addHandler(s_handler)
    
    return logger
