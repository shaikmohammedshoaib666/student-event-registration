from event_app.backend_errors import backend_error_message


class SupabaseError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def test_missing_schema_error_directs_admin_to_updated_sql_setup():
    message = backend_error_message(SupabaseError("PGRST205", "Could not find table events"))

    assert "latest `supabase/schema.sql`" in message


def test_invalid_key_error_identifies_secret_setting_without_disclosing_values():
    message = backend_error_message(SupabaseError("401", "Invalid API key"))

    assert "`SUPABASE_SERVICE_ROLE_KEY`" in message
    assert "Invalid API key" not in message
