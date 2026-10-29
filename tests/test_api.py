import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from server.app import app
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
