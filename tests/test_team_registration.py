from event_app.team_registration import validate_team_members


def test_team_registration_normalizes_member_contacts_and_student_ids():
    members, errors = validate_team_members(
        [
            {
                "Name": "  Grace   Hopper ",
                "Student ID": "stu-2",
                "Email": "GRACE@example.edu",
                "Phone": "+1 555 123 4567",
            },
            {
                "Name": "Katherine Johnson",
                "Student ID": "STU-3",
                "Email": "katherine@example.edu",
                "Phone": "",
            },
        ],
        team_size=3,
        leader_student_id="STU-1",
    )

    assert errors == []
    assert members == [
        {
            "name": "Grace Hopper",
            "student_id": "STU-2",
            "email": "grace@example.edu",
            "phone": "+1 555 123 4567",
        },
        {
            "name": "Katherine Johnson",
            "student_id": "STU-3",
            "email": "katherine@example.edu",
            "phone": "",
        },
    ]


def test_team_registration_requires_every_other_member_and_unique_student_ids():
    members, errors = validate_team_members(
        [
            {
                "Name": "Member One",
                "Student ID": "stu-1",
                "Email": "member@example.edu",
                "Phone": "",
            },
            {
                "Name": "",
                "Student ID": "",
                "Email": "invalid",
                "Phone": "",
            },
        ],
        team_size=3,
        leader_student_id="STU-1",
    )

    assert members is None
    assert any("Student IDs must be unique" in error for error in errors)
    assert any("valid email" in error for error in errors)


def test_single_person_registration_has_no_additional_member_requirements():
    members, errors = validate_team_members(
        [],
        team_size=1,
        leader_student_id="STU-1",
    )

    assert members == []
    assert errors == []
