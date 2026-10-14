from event_app.admin_auth import admin_configuration_error, authenticate_admin


def test_admin_email_is_case_insensitive_and_password_is_checked():
    admins = {"events@university.edu": "a-long-admin-password"}

    assert authenticate_admin(admins, " Events@University.edu ", "a-long-admin-password")
    assert not authenticate_admin(admins, "someone@university.edu", "a-long-admin-password")
    assert not authenticate_admin(admins, "events@university.edu", "wrong-password")


def test_multiple_admins_have_independent_credentials():
    admins = {
        "first@university.edu": "first-password-is-long",
        "second@university.edu": "second-password-is-long",
        "third@university.edu": "third-password-is-long",
    }

    assert authenticate_admin(admins, "second@university.edu", "second-password-is-long")
    assert not authenticate_admin(admins, "second@university.edu", "first-password-is-long")


def test_admin_configuration_requires_one_to_three_valid_accounts_and_long_passwords():
    assert admin_configuration_error({}) is not None
    assert admin_configuration_error(
        {"admin@university.edu": "short"}
    ) == "Each admin password must contain at least 16 characters."
    assert admin_configuration_error(
        {"not-an-email": "a-very-long-admin-password"}
    ) == "Each admin account needs a valid email address."
    four_admins = {
        f"admin{number}@university.edu": f"a-very-long-password-{number}"
        for number in range(4)
    }
    assert admin_configuration_error(four_admins) is not None
