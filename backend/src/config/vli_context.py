import contextvars

# Global context var to track the active VLI Session ID (Client Tab)
vli_client_id = contextvars.ContextVar('vli_client_id', default='default')
