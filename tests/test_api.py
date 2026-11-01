import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from server.app import app
from server.cli import ApiClient, run_cli
from server.models import Exercise, Workout, db


@pytest.fixture
def client(tmp_path):
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'test.db'}",
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


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
