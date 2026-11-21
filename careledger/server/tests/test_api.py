import os, tempfile, unittest
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
import app as A


class ApiTest(unittest.TestCase):
    def setUp(self):
        A.init_db()
        self.c = A.app.test_client()

    def auth(self, email="t@x.io"):
        r = self.c.post("/api/auth/register", json={"name": "T", "email": email, "password": "password1"})
        return {"Authorization": "Bearer " + r.get_json()["token"]}

    def test_register_login_and_duplicate(self):
        self.auth("a@x.io")
        self.assertEqual(self.c.post("/api/auth/login", json={"email": "a@x.io", "password": "password1"}).status_code, 200)
        self.assertEqual(self.c.post("/api/auth/login", json={"email": "a@x.io", "password": "nope"}).status_code, 401)
        self.assertEqual(self.c.post("/api/auth/register", json={"name": "T", "email": "a@x.io", "password": "password1"}).status_code, 409)

    def test_crud_and_isolation(self):
        h1, h2 = self.auth("u1@x.io"), self.auth("u2@x.io")
        r = self.c.post("/api/bills", json={"provider": "Clinic", "amount": 500, "date": "2026-01-02"}, headers=h1)
        self.assertEqual(r.status_code, 201)
        bid = r.get_json()["id"]
        self.assertEqual(len(self.c.get("/api/bills", headers=h2).get_json()), 0)
        self.assertEqual(self.c.delete(f"/api/bills/{bid}", headers=h2).status_code, 404)
        self.assertEqual(self.c.post("/api/bills", json={"provider": "X"}, headers=h1).status_code, 400)

    def test_dashboard_and_admin_guard(self):
        h = self.auth("d@x.io")
        self.assertIn("month_spend", self.c.get("/api/dashboard", headers=h).get_json())
        self.assertEqual(self.c.get("/api/admin/stats", headers=h).status_code, 403)
        self.assertEqual(self.c.get("/api/bills").status_code, 401)


if __name__ == "__main__":
    unittest.main()
