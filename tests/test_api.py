import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from server.auth import issue_access_token
from server.app import app
from server.cli import ApiClient, run_cli
from server.models import Exercise, User, Workout, db


@pytest.fixture
def client(tmp_path):
    original_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'test.db'}",
    )
    with app.app_context():
        original_engine = db.engines[None]
        test_engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
        db.engines[None] = test_engine
        try:
            db.drop_all()
            db.create_all()
            admin = User(username="test-admin", role="admin")
            admin.set_password("test-admin-password")
            db.session.add(admin)
            db.session.commit()
            client = app.test_client()
            client.environ_base["HTTP_AUTHORIZATION"] = (
                f"Bearer {issue_access_token(admin)}"
            )
            yield client
        finally:
            db.session.remove()
            db.drop_all()
            test_engine.dispose()
            db.engines[None] = original_engine
            app.config["SQLALCHEMY_DATABASE_URI"] = original_uri


def test_registration_hashes_password_and_login_returns_token(client):
    registration = client.post(
        "/auth/register",
        json={"username": "Regular.User", "password": "a-very-long-password"},
    )

    assert registration.status_code == 201
    assert registration.json == {
        "id": 2,
        "username": "regular.user",
        "role": "user",
    }
    with app.app_context():
        user = User.query.filter_by(username="regular.user").one()
        assert user.password_hash != "a-very-long-password"
        assert user.check_password("a-very-long-password")

    login = client.post(
        "/auth/login",
        json={"username": "REGULAR.USER", "password": "a-very-long-password"},
    )

    assert login.status_code == 200
    assert login.json["token_type"] == "Bearer"
    assert login.json["expires_in"] == 3600
    profile = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login.json['access_token']}"},
    )
    assert profile.json["username"] == "regular.user"
    assert profile.json["role"] == "user"


def test_registration_rejects_short_password(client):
    response = client.post(
        "/auth/register",
        json={"username": "new-user", "password": "short"},
    )

    assert response.status_code == 400
    assert "password" in response.json["errors"]


def test_registration_cannot_assign_admin_role(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "not-an-admin",
            "password": "a-very-long-password",
            "role": "admin",
        },
    )

    assert response.status_code == 400
    assert "role" in response.json["errors"]


def test_login_rejects_invalid_password(client):
    response = client.post(
        "/auth/login",
        json={"username": "test-admin", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json["error"] == "Invalid username or password."


def test_resources_require_authentication(client):
    response = client.get("/workouts", headers={"Authorization": ""})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_resources_reject_invalid_bearer_token(client):
    response = client.get(
        "/workouts",
        headers={"Authorization": "Bearer not-a-token"},
    )

    assert response.status_code == 401


def test_standard_user_can_read_but_cannot_write(client):
    registration = client.post(
        "/auth/register",
        json={"username": "standard-user", "password": "another-long-password"},
    )
    assert registration.status_code == 201
    login = client.post(
        "/auth/login",
        json={"username": "standard-user", "password": "another-long-password"},
    )
    user_headers = {"Authorization": f"Bearer {login.json['access_token']}"}

    assert client.get("/workouts", headers=user_headers).status_code == 200
    denied = client.post(
        "/workouts",
        json={"name": "User-created workout"},
        headers=user_headers,
    )

    assert denied.status_code == 403
    assert denied.json["error"] == "Administrator access is required."


def test_create_admin_command_uses_environment_credentials(client, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "initial-admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "a-strong-admin-password")

    result = app.test_cli_runner().invoke(args=["create-admin"])

    assert result.exit_code == 0
    assert "Created admin account 'initial-admin'." in result.output
    with app.app_context():
        user = User.query.filter_by(username="initial-admin").one()
        assert user.role == "admin"
        assert user.check_password("a-strong-admin-password")


def test_create_admin_command_defaults_to_requested_local_credentials(client, monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    result = app.test_cli_runner().invoke(args=["create-admin"])

    assert result.exit_code == 0
    assert "Created admin account 'admin'." in result.output
    with app.app_context():
        admin = User.query.filter_by(username="admin").one()
        assert admin.role == "admin"
        assert admin.check_password("admin101")
        assert admin.password_hash != "admin101"


def test_cli_api_client_can_register_a_standard_user(client):
    def transport(method, path, payload):
        response = client.open(path, method=method, json=payload)
        return response.status_code, response.get_json()

    api = ApiClient(transport=transport)

    response = api.register("new-cli-user", "another-long-password")

    assert response["username"] == "new-cli-user"
    assert response["role"] == "user"


def test_create_and_list_workout(client):
    response = client.post("/workouts", json={"name": "Leg day"})

    assert response.status_code == 201
    assert response.json["name"] == "Leg day"
    assert client.get("/workouts").json == [response.json]


def test_workout_schema_rejects_blank_name(client):
    response = client.post("/workouts", json={"name": "  "})

    assert response.status_code == 400
    assert "name" in response.json["errors"]


def test_association_requires_valid_prescription(client):
    workout = client.post("/workouts", json={"name": "Leg day"}).json
    exercise = client.post(
        "/exercises",
        json={"name": "Squat", "muscle_group": "Legs"},
    ).json

    response = client.post(
        f"/workouts/{workout['id']}/exercises/{exercise['id']}/workout_exercises",
        json={"sets": 3},
    )

    assert response.status_code == 400
    assert "_schema" in response.json["errors"]


def test_association_is_serialized_with_workout(client):
    workout = client.post("/workouts", json={"name": "Leg day"}).json
    exercise = client.post(
        "/exercises",
        json={"name": "Squat", "muscle_group": "Legs"},
    ).json
    response = client.post(
        f"/workouts/{workout['id']}/exercises/{exercise['id']}/workout_exercises",
        json={"sets": 3, "reps": 8},
    )

    assert response.status_code == 201
    assert response.json["exercise"]["name"] == "Squat"
    assert client.get(f"/workouts/{workout['id']}").json["workout_exercises"][0][
        "reps"
    ] == 8


def test_delete_workout_cascades_to_associations(client):
    workout = client.post("/workouts", json={"name": "Leg day"}).json
    exercise = client.post(
        "/exercises",
        json={"name": "Squat", "muscle_group": "Legs"},
    ).json
    client.post(
        f"/workouts/{workout['id']}/exercises/{exercise['id']}/workout_exercises",
        json={"sets": 3, "reps": 8},
    )

    response = client.delete(f"/workouts/{workout['id']}")

    assert response.status_code == 204
    assert client.get(f"/workouts/{workout['id']}").status_code == 404
    assert client.get(f"/exercises/{exercise['id']}").status_code == 200


def test_database_constraint_rejects_partial_prescription(client):
    workout = Workout(name="Leg day")
    exercise = Exercise(name="Squat", muscle_group="Legs")
    with app.app_context():
        db.session.add_all([workout, exercise])
        db.session.commit()
        with pytest.raises(IntegrityError):
            db.session.execute(
                text(
                    "INSERT INTO workout_exercises "
                    "(workout_id, exercise_id, sets, reps, duration_seconds) "
                    "VALUES (:workout_id, :exercise_id, 3, NULL, NULL)"
                ),
                {"workout_id": workout.id, "exercise_id": exercise.id},
            )
            db.session.commit()
        db.session.rollback()


def test_cli_creates_and_maps_workout_exercise_relationship(client):
    answers = iter(
        [
            "3", "Strength day", "Beginner session",
            "7", "Squat", "Legs", "",
            "9", "1", "1", "1", "3", "10",
            "2", "1",
            "0",
        ]
    )
    output = []

    def transport(method, path, payload):
        response = client.open(path, method=method, json=payload)
        return response.status_code, response.get_json()

    run_cli(
        api=ApiClient(transport=transport),
        input_fn=lambda _prompt: next(answers),
        output_fn=output.append,
    )

    workout = client.get("/workouts/1").json
    assert workout["name"] == "Strength day"
    assert workout["workout_exercises"][0]["exercise"]["name"] == "Squat"
    assert workout["workout_exercises"][0]["sets"] == 3
    assert any("Squat (Legs): 3 sets x 10 reps" in line for line in output)


def test_cli_requires_confirmation_before_deleting_workout(client):
    workout = client.post("/workouts", json={"name": "Keep this workout"}).json
    answers = iter(["4", str(workout["id"]), "n", "0"])
    output = []

    def transport(method, path, payload):
        response = client.open(path, method=method, json=payload)
        return response.status_code, response.get_json()

    run_cli(
        api=ApiClient(transport=transport),
        input_fn=lambda _prompt: next(answers),
        output_fn=output.append,
    )

    assert client.get(f"/workouts/{workout['id']}").status_code == 200
    assert "Delete cancelled." in output
