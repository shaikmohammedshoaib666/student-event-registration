from event_app.supabase_data import create_registration


class FakeQuery:
    def __init__(self):
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        return None


class FakeClient:
    def table(self, table):
        assert table == "registrations"
        self.query = FakeQuery()
        return self.query


def test_team_registration_persists_lead_and_member_details():
    client = FakeClient()
    leader = {
        "student_name": "Ada Lovelace",
        "student_id": "STU-1",
        "email": "ada@example.edu",
        "phone": None,
    }
    members = [
        {
            "name": "Grace Hopper",
            "student_id": "STU-2",
            "email": "grace@example.edu",
            "phone": "",
        }
    ]

    create_registration(
        client,
        "event-1",
        leader,
        "user-1",
        {"Meal": "Vegan"},
        team_size=2,
        team_members=members,
    )

    assert client.query.payload == {
        "event_id": "event-1",
        "user_id": "user-1",
        "form_answers": {"Meal": "Vegan"},
        "team_size": 2,
        "team_members": members,
        **leader,
    }
