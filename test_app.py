import os
import tempfile
import unittest
from unittest.mock import patch

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

    def test_password_hashing_and_legacy_upgrade(self):
        signup = self.client.post(
            "/api/signup",
            json={"username": "hash-check@example.com", "password": "long-enough-secret", "role": "participant"},
        )
        self.assertEqual(signup.status_code, 200)
        with app_module.get_connection() as conn:
            stored_signup_password = conn.execute(
                "SELECT password FROM users WHERE username = ?",
                ("hash-check@example.com",),
            ).fetchone()["password"]
            conn.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                ("legacy-user", "old-plain-password", "participant"),
            )
            conn.commit()
        self.assertNotEqual(stored_signup_password, "long-enough-secret")
        self.assertTrue(stored_signup_password.startswith("pbkdf2_sha256$"))
        self.assertTrue(app_module.verify_password("long-enough-secret", stored_signup_password)[0])

        legacy_client = TestClient(app_module.app)
        self.addCleanup(legacy_client.close)
        login = legacy_client.post(
            "/api/login",
            json={"username": "legacy-user", "password": "old-plain-password"},
        )
        self.assertEqual(login.status_code, 200)
        with app_module.get_connection() as conn:
            migrated_password = conn.execute(
                "SELECT password FROM users WHERE username = ?",
                ("legacy-user",),
            ).fetchone()["password"]
        self.assertNotEqual(migrated_password, "old-plain-password")
        self.assertTrue(app_module.verify_password("old-plain-password", migrated_password)[0])

    def test_demo_credentials_are_rejected_in_production_mode(self):
        with patch.object(app_module, "IS_PRODUCTION", True):
            admin_login = self.client.post(
                "/api/login",
                json={"username": "admin", "password": "admin123"},
            )
            coordinator_login = self.client.post(
                "/api/login",
                json={"username": "coordinator", "password": "coord123"},
            )
        self.assertEqual(admin_login.status_code, 401)
        self.assertEqual(coordinator_login.status_code, 401)

    def test_local_demo_passwords_are_stored_as_hashes(self):
        with app_module.get_connection() as conn:
            passwords = {
                row["username"]: row["password"]
                for row in conn.execute("SELECT username, password FROM users").fetchall()
            }
        self.assertTrue(passwords["admin"].startswith("pbkdf2_sha256$"))
        self.assertTrue(passwords["coordinator"].startswith("pbkdf2_sha256$"))

    def test_startup_migrates_legacy_passwords(self):
        with app_module.get_connection() as conn:
            conn.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                ("startup-legacy", "old-startup-password", "participant"),
            )
            conn.commit()
        app_module.init_db()
        with app_module.get_connection() as conn:
            stored_password = conn.execute(
                "SELECT password FROM users WHERE username = ?",
                ("startup-legacy",),
            ).fetchone()["password"]
        self.assertTrue(stored_password.startswith("pbkdf2_sha256$"))
        self.assertTrue(app_module.verify_password("old-startup-password", stored_password)[0])

    def test_production_bootstrap_creates_only_configured_admin(self):
        previous_database_path = app_module.DB_PATH
        with tempfile.TemporaryDirectory() as database_dir:
            app_module.DB_PATH = app_module.Path(database_dir) / "production.db"
            try:
                with (
                    patch.object(app_module, "IS_PRODUCTION", True),
                    patch.object(app_module, "PRODUCTION_ADMIN_USERNAME", "bootstrap-admin"),
                    patch.object(app_module, "PRODUCTION_ADMIN_PASSWORD", "generated-production-password"),
                ):
                    app_module.init_db()
                    with app_module.get_connection() as conn:
                        accounts = conn.execute("SELECT username, password, role FROM users").fetchall()
                self.assertEqual(len(accounts), 1)
                self.assertEqual(accounts[0]["username"], "bootstrap-admin")
                self.assertEqual(accounts[0]["role"], "admin")
                self.assertTrue(accounts[0]["password"].startswith("pbkdf2_sha256$"))
                self.assertTrue(
                    app_module.verify_password("generated-production-password", accounts[0]["password"])[0]
                )
            finally:
                app_module.DB_PATH = previous_database_path

    def test_dashboard_data_is_scoped_by_role(self):
        dashboard_page = self.client.get("/dashboard")
        self.assertEqual(dashboard_page.status_code, 200)
        self.assertIn('<tbody id="participantList">', dashboard_page.text)
        self.assertIn('<tbody id="volunteerList">', dashboard_page.text)
        self.assertIn("<th>Competition</th>", dashboard_page.text)
        self.assertIn("<th>Event</th>", dashboard_page.text)
        for field in ("Roll number", "Class", "Department", "Division"):
            self.assertIn(f'placeholder="{field}"', dashboard_page.text)
            self.assertIn(f"<th>{field}</th>", dashboard_page.text)
        self.assertIn('id="recordEditDialog"', dashboard_page.text)

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
                    "division": "A",
                },
            )
            self.assertEqual(response.status_code, 200)

        for name, email, phone in [
            ("Volunteer One", "helper@example.com", "9000000003"),
            ("Volunteer Two", "second-helper@example.com", "9000000004"),
        ]:
            response = self.client.post(
                "/api/volunteers",
                json={
                    "event_id": event_id,
                    "competition_id": competition_id,
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "preferred_role": "Support",
                    "skills": "Organizing",
                    "department": "CSE",
                    "year": "2",
                    "registration_no": phone,
                    "division": "A",
                },
            )
            self.assertEqual(response.status_code, 200)

        participant_client = TestClient(app_module.app)
        self.addCleanup(participant_client.close)
        participant_client.post(
            "/api/signup",
            json={"username": "one@example.com", "password": "secret123", "role": "participant"},
        )
        participant_data = participant_client.get("/api/dashboard").json()
        self.assertEqual([row["email"] for row in participant_data["all_participants"]], ["one@example.com"])
        self.assertEqual(participant_data["all_participants"][0]["division"], "A")
        self.assertEqual(participant_data["recent_participants"][0]["event_name"], "Access Week")
        self.assertEqual(participant_data["recent_participants"][0]["competition_name"], "Access Challenge")
        self.assertEqual(participant_data["all_volunteers"], [])
        self.assertEqual(participant_data["stats"], {"events": 0, "competitions": 0, "participants": 1, "volunteers": 0})
        self.assertEqual(participant_data["competition_breakdown"], [])
        self.assertEqual(
            [row["email"] for row in participant_client.get("/api/participants").json()],
            ["one@example.com"],
        )
        self.assertEqual(participant_client.get("/api/volunteers").status_code, 403)
        self.assertEqual(
            participant_client.get(
                f"/api/competition-rules?event_id={event_id}&competition_id={competition_id}"
            ).status_code,
            403,
        )
        self.assertEqual(
            participant_client.get(
                f"/api/competition-messages?event_id={event_id}&competition_id={competition_id}"
            ).status_code,
            403,
        )
        self.assertEqual(participant_client.post("/api/events", json={}).status_code, 403)
        self.assertEqual(
            participant_client.post(
                "/api/participants",
                json={
                    "event_id": event_id,
                    "competition_id": competition_id,
                    "name": "Someone Else",
                    "email": "two@example.com",
                    "phone": "9000000011",
                    "department": "CSE",
                    "year": "2",
                    "registration_no": "9000000011",
                },
            ).status_code,
            403,
        )

        volunteer_client = TestClient(app_module.app)
        self.addCleanup(volunteer_client.close)
        volunteer_client.post(
            "/api/signup",
            json={"username": "helper@example.com", "password": "secret123", "role": "volunteer"},
        )
        volunteer_data = volunteer_client.get("/api/dashboard").json()
        self.assertEqual(volunteer_data["all_participants"], [])
        self.assertEqual([row["email"] for row in volunteer_data["all_volunteers"]], ["helper@example.com"])
        self.assertEqual(volunteer_data["all_volunteers"][0]["registration_no"], "9000000003")
        self.assertEqual(volunteer_data["all_volunteers"][0]["division"], "A")
        self.assertEqual(volunteer_data["recent_volunteers"][0]["event_name"], "Access Week")
        self.assertEqual(volunteer_data["recent_volunteers"][0]["competition_name"], "Access Challenge")
        self.assertEqual(volunteer_data["stats"], {"events": 0, "competitions": 0, "participants": 0, "volunteers": 1})
        self.assertEqual(volunteer_data["competition_breakdown"], [])
        self.assertEqual(volunteer_client.get("/api/participants").status_code, 403)
        self.assertEqual(
            [row["email"] for row in volunteer_client.get("/api/volunteers").json()],
            ["helper@example.com"],
        )
        self.assertEqual(
            volunteer_client.post(
                "/api/volunteers",
                json={
                    "event_id": event_id,
                    "competition_id": competition_id,
                    "name": "Someone Else",
                    "email": "third-helper@example.com",
                    "phone": "9000000012",
                    "preferred_role": "Support",
                    "skills": "Organizing",
                },
            ).status_code,
            403,
        )

        coordinator_data = self.client.get("/api/dashboard").json()
        self.assertEqual(len(coordinator_data["all_participants"]), 2)
        self.assertEqual(len(coordinator_data["all_volunteers"]), 2)
        self.assertEqual(coordinator_data["recent_participants"][0]["event_name"], "Access Week")
        self.assertEqual(coordinator_data["recent_participants"][0]["competition_name"], "Access Challenge")
        self.assertEqual(coordinator_data["recent_volunteers"][0]["event_name"], "Access Week")
        self.assertEqual(coordinator_data["recent_volunteers"][0]["competition_name"], "Access Challenge")
        self.assertEqual(coordinator_data["stats"], {"events": 1, "competitions": 1, "participants": 2, "volunteers": 2})
        self.assertEqual(
            coordinator_data["competition_breakdown"],
            [{
                "event_id": event_id,
                "event_name": "Access Week",
                "competition_id": competition_id,
                "competition_name": "Access Challenge",
                "participants": 2,
                "volunteers": 2,
            }],
        )
        self.assertEqual(len(self.client.get("/api/participants").json()), 2)
        self.assertEqual(len(self.client.get("/api/volunteers").json()), 2)

        coordinator_client = TestClient(app_module.app)
        self.addCleanup(coordinator_client.close)
        coordinator_client.post(
            "/api/login",
            json={"username": "coordinator", "password": "coord123"},
        )
        coordinator_data = coordinator_client.get("/api/dashboard").json()
        self.assertEqual(len(coordinator_data["all_participants"]), 2)
        self.assertEqual(len(coordinator_data["all_volunteers"]), 2)
        self.assertEqual(coordinator_data["competition_breakdown"][0]["participants"], 2)
        self.assertEqual(coordinator_data["competition_breakdown"][0]["volunteers"], 2)
        self.assertEqual(len(coordinator_client.get("/api/participants").json()), 2)
        self.assertEqual(len(coordinator_client.get("/api/volunteers").json()), 2)

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
                "division": "A",
            },
        )
        self.assertEqual(participant.status_code, 200)

        csv_response = self.client.get(f"/api/reports/participants/csv?event_id={event_id}")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("Riya", csv_response.text)
        self.assertIn("Roll number", csv_response.text)
        self.assertIn("Division", csv_response.text)
        self.assertIn("CS-201", csv_response.text)
        self.assertIn(",A,", csv_response.text)

        volunteer = self.client.post(
            "/api/volunteers",
            json={
                "event_id": event_id,
                "competition_id": competition_id,
                "name": "Arjun",
                "email": "arjun@example.com",
                "phone": "9000000042",
                "preferred_role": "Support",
                "skills": "Coordination",
                "registration_no": "CS-242",
                "year": "2nd",
                "department": "CSE",
                "division": "B",
            },
        )
        self.assertEqual(volunteer.status_code, 200)
        for report_path in [
            f"/api/reports/participants/xlsx?event_id={event_id}",
            f"/api/reports/volunteers/csv?event_id={event_id}",
            f"/api/reports/volunteers/xlsx?event_id={event_id}",
            f"/api/reports/combined/xlsx?event_id={event_id}",
        ]:
            self.assertEqual(self.client.get(report_path).status_code, 200)

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
                "division": "B",
                "division": "B",
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
                "department": "ECE",
                "year": "3rd",
                "registration_no": "EC-305",
                "division": "B",
                "department": "ECE",
                "year": "3rd",
                "registration_no": "EC-305",
                "division": "B",
            },
        )
        volunteer_id = volunteer.json()["id"]

        updated_participant = self.client.patch(
            f"/api/participants/{participant_id}",
            json={"name": "Meera S", "department": "EEE", "division": "C", "year": "4th", "registration_no": "EC-406"},
        )
        self.assertEqual(updated_participant.status_code, 200)
        self.assertEqual(updated_participant.json()["name"], "Meera S")
        self.assertEqual(updated_participant.json()["division"], "C")
        self.assertEqual(updated_participant.json()["registration_no"], "EC-406")

        updated_volunteer = self.client.patch(
            f"/api/volunteers/{volunteer_id}",
            json={"preferred_role": "Stage Manager", "assignment": "Assigned", "department": "EEE", "division": "D", "year": "4th", "registration_no": "EC-407"},
        )
        self.assertEqual(updated_volunteer.status_code, 200)
        self.assertEqual(updated_volunteer.json()["preferred_role"], "Stage Manager")
        self.assertEqual(updated_volunteer.json()["division"], "D")
        self.assertEqual(updated_volunteer.json()["registration_no"], "EC-407")

        volunteer_csv = self.client.get(f"/api/reports/volunteers/csv?event_id={event_id}")
        self.assertEqual(volunteer_csv.status_code, 200)
        self.assertIn("Roll number", volunteer_csv.text)
        self.assertIn("Division", volunteer_csv.text)
        self.assertIn("EC-407", volunteer_csv.text)

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
