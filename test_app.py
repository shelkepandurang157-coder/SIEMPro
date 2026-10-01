import os
import tempfile
import unittest

os.environ["SIEMPRO_DB_PATH"] = os.path.join(os.getcwd(), "test_siempro.db")

from fastapi.testclient import TestClient

import app as app_module


class SIEMProChatTests(unittest.TestCase):
    def setUp(self):
        self.database_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.database_dir.cleanup)
        app_module.DB_PATH = app_module.Path(self.database_dir.name) / "siempro.db"
        app_module.init_db()
        self.client = TestClient(app_module.app)
        self.addCleanup(self.client.close)
        self.client.post("/api/login", json={"username": "admin", "password": "admin123"})

    def test_dashboard_data_is_scoped_by_role(self):
        event = self.client.post(
            "/api/events",
            json={"name": "Access Week", "date": "2027-04-10", "location": "Hall", "description": ""},
        )
        event_id = event.json()["id"]
        competition = self.client.post(
            "/api/competitions",
            json={
                "event_id": event_id,
                "name": "Access Challenge",
                "time": "10 AM",
                "venue": "Lab",
                "capacity": 20,
                "coordinator_name": "Admin",
                "description": "",
                "rules": "",
            },
        )
        competition_id = competition.json()["id"]

        for name, email, phone in [
            ("Participant One", "one@example.com", "9000000001"),
            ("Participant Two", "two@example.com", "9000000002"),
        ]:
            response = self.client.post(
                "/api/participants",
                json={
                    "event_id": event_id,
                    "competition_id": competition_id,
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "department": "CSE",
                    "year": "2",
                    "registration_no": phone,
                },
            )
            self.assertEqual(response.status_code, 200)

        self.client.post(
            "/api/volunteers",
            json={
                "event_id": event_id,
                "competition_id": competition_id,
                "name": "Volunteer One",
                "email": "helper@example.com",
                "phone": "9000000003",
                "preferred_role": "Support",
                "skills": "Organizing",
            },
        )

        participant_client = TestClient(app_module.app)
        self.addCleanup(participant_client.close)
        participant_client.post(
            "/api/signup",
            json={"username": "one@example.com", "password": "secret123", "role": "participant"},
        )
        participant_data = participant_client.get("/api/dashboard").json()
        self.assertEqual([row["email"] for row in participant_data["all_participants"]], ["one@example.com"])
        self.assertEqual(participant_data["all_volunteers"], [])
        self.assertEqual(participant_client.get("/api/volunteers").status_code, 403)
        self.assertEqual(participant_client.post("/api/events", json={}).status_code, 403)

        volunteer_client = TestClient(app_module.app)
        self.addCleanup(volunteer_client.close)
        volunteer_client.post(
            "/api/signup",
            json={"username": "helper@example.com", "password": "secret123", "role": "volunteer"},
        )
        volunteer_data = volunteer_client.get("/api/dashboard").json()
        self.assertEqual({row["email"] for row in volunteer_data["all_participants"]}, {"one@example.com", "two@example.com"})
        self.assertEqual([row["email"] for row in volunteer_data["all_volunteers"]], ["helper@example.com"])

        anonymous_client = TestClient(app_module.app)
        self.addCleanup(anonymous_client.close)
        self.assertEqual(anonymous_client.get("/api/dashboard").status_code, 401)

    def test_chat_message_round_trip(self):
        event = self.client.post(
            "/api/events",
            json={
                "name": "Tech Fest",
                "date": "2026-11-15",
                "location": "Main Hall",
                "description": "Annual festival",
            },
        )
        self.assertEqual(event.status_code, 200)
        event_id = event.json()["id"]

        competition = self.client.post(
            "/api/competitions",
            json={
                "event_id": event_id,
                "name": "Coding Battle",
                "time": "10:00 AM",
                "venue": "Lab 1",
                "capacity": 25,
                "coordinator_name": "Asha",
                "description": "Challenge round",
                "rules": "Register before 9 AM and bring your ID card.",
            },
        )
        self.assertEqual(competition.status_code, 200)
        competition_id = competition.json()["id"]

        message = self.client.post(
            "/api/competition-messages",
            json={
                "event_id": event_id,
                "competition_id": competition_id,
                "sender": "coordinator",
                "sender_name": "Asha",
                "message": "All participants must submit their code before the final round.",
            },
        )
        self.assertEqual(message.status_code, 200)

        response = self.client.get(
            f"/api/competition-messages?event_id={event_id}&competition_id={competition_id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.json()) >= 1)
        self.assertIn("code", response.json()[0]["message"].lower())

    def test_admin_login_and_record_delete(self):
        event = self.client.post(
            "/api/events",
            json={
                "name": "Sports Day",
                "date": "2026-12-10",
                "location": "Ground",
                "description": "Annual sports",
            },
        )
        event_id = event.json()["id"]

        login = self.client.post(
            "/api/login",
            json={"username": "admin", "password": "admin123"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["role"], "admin")

        delete_response = self.client.delete(f"/api/events/{event_id}")
        self.assertEqual(delete_response.status_code, 200)

        remaining = self.client.get("/api/events")
        self.assertEqual(remaining.json(), [])

    def test_export_report_and_update_competition(self):
        event = self.client.post(
            "/api/events",
            json={
                "name": "Innovation Fair",
                "date": "2027-01-20",
                "location": "Auditorium",
                "description": "Innovation fair",
            },
        )
        event_id = event.json()["id"]

        competition = self.client.post(
            "/api/competitions",
            json={
                "event_id": event_id,
                "name": "Startup Pitch",
                "time": "2:00 PM",
                "venue": "Room 5",
                "capacity": 12,
                "coordinator_name": "Neha",
                "description": "Startup idea competition",
                "rules": "Teams of 3",
            },
        )
        competition_id = competition.json()["id"]

        participant = self.client.post(
            "/api/participants",
            json={
                "event_id": event_id,
                "competition_id": competition_id,
                "name": "Riya",
                "email": "riya@example.com",
                "phone": "9876543210",
                "department": "CSE",
                "year": "2nd",
                "registration_no": "CS-201",
            },
        )
        self.assertEqual(participant.status_code, 200)

        csv_response = self.client.get(f"/api/reports/participants/csv?event_id={event_id}")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("Riya", csv_response.text)

        update = self.client.patch(
            f"/api/competitions/{competition_id}",
            json={"name": "Startup Pitch Final", "capacity": 15, "rules": "Teams of 3 and final pitch"},
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["name"], "Startup Pitch Final")
        self.assertEqual(update.json()["capacity"], 15)

    def test_edit_and_delete_registered_records(self):
        event = self.client.post(
            "/api/events",
            json={
                "name": "Festival Week",
                "date": "2027-02-15",
                "location": "Campus",
                "description": "Cultural festival",
            },
        )
        event_id = event.json()["id"]

        competition = self.client.post(
            "/api/competitions",
            json={
                "event_id": event_id,
                "name": "Dance Contest",
                "time": "4:00 PM",
                "venue": "Stage",
                "capacity": 20,
                "coordinator_name": "Rohit",
                "description": "Dance event",
                "rules": "Team size 5",
            },
        )
        competition_id = competition.json()["id"]

        participant = self.client.post(
            "/api/participants",
            json={
                "event_id": event_id,
                "competition_id": competition_id,
                "name": "Meera",
                "email": "meera@example.com",
                "phone": "9123456780",
                "department": "ECE",
                "year": "3rd",
                "registration_no": "EC-305",
            },
        )
        participant_id = participant.json()["id"]

        volunteer = self.client.post(
            "/api/volunteers",
            json={
                "event_id": event_id,
                "competition_id": competition_id,
                "name": "Aman",
                "email": "aman@example.com",
                "phone": "9988776655",
                "preferred_role": "Stage Setup",
                "skills": "Lighting and sound",
            },
        )
        volunteer_id = volunteer.json()["id"]

        updated_participant = self.client.patch(
            f"/api/participants/{participant_id}",
            json={"name": "Meera S", "department": "EEE"},
        )
        self.assertEqual(updated_participant.status_code, 200)
        self.assertEqual(updated_participant.json()["name"], "Meera S")

        updated_volunteer = self.client.patch(
            f"/api/volunteers/{volunteer_id}",
            json={"preferred_role": "Stage Manager", "assignment": "Assigned"},
        )
        self.assertEqual(updated_volunteer.status_code, 200)
        self.assertEqual(updated_volunteer.json()["preferred_role"], "Stage Manager")

        delete_participant = self.client.delete(f"/api/participants/{participant_id}")
        delete_volunteer = self.client.delete(f"/api/volunteers/{volunteer_id}")
        self.assertEqual(delete_participant.status_code, 200)
        self.assertEqual(delete_volunteer.status_code, 200)

    def test_coordinator_login_is_supported(self):
        login = self.client.post(
            "/api/login",
            json={"username": "coordinator", "password": "coord123"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["role"], "coordinator")

    def test_homepage_has_platform_briefing(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text.lower()
        self.assertIn("siempro", html)
        self.assertIn("college event coordination platform", html)
        self.assertIn("/signin", html)
        self.assertIn("/signup", html)
        self.assertIn("make every event easier", html)

    def test_participant_excel_export(self):
        event = self.client.post(
            "/api/events",
            json={
                "name": "Excel Week",
                "date": "2027-03-05",
                "location": "Hall 3",
                "description": "Spreadsheet export check",
            },
        )
        event_id = event.json()["id"]

        competition = self.client.post(
            "/api/competitions",
            json={
                "event_id": event_id,
                "name": "UI Design",
                "time": "1:30 PM",
                "venue": "Room B",
                "capacity": 16,
                "coordinator_name": "Mehul",
                "description": "UI challenge",
                "rules": "Submit mockup",
            },
        )
        competition_id = competition.json()["id"]

        self.client.post(
            "/api/participants",
            json={
                "event_id": event_id,
                "competition_id": competition_id,
                "name": "Aditi",
                "email": "aditi@example.com",
                "phone": "9812345678",
                "department": "IT",
                "year": "4th",
                "registration_no": "IT-404",
            },
        )

        response = self.client.get(f"/api/reports/participants/xlsx?event_id={event_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("openxmlformats-officedocument.spreadsheetml.sheet", response.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()
