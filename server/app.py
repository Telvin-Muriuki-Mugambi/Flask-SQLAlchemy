from pathlib import Path

from flask import Flask, jsonify, request
from flask_migrate import Migrate
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from .models import Exercise, Workout, WorkoutExercise, db
from .schemas import ExerciseSchema, WorkoutExerciseSchema, WorkoutSchema


app = Flask(__name__)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
migrate = Migrate(app, db)

workout_schema = WorkoutSchema()
workouts_schema = WorkoutSchema(many=True)
exercise_schema = ExerciseSchema()
exercises_schema = ExerciseSchema(many=True)
workout_exercise_schema = WorkoutExerciseSchema()


@app.errorhandler(ValidationError)
def handle_validation_error(error):
    return jsonify({"errors": error.messages}), 400


@app.errorhandler(HTTPException)
def handle_http_error(error):
    message = "Resource not found." if error.code == 404 else error.description
    return jsonify({"error": message}), error.code


@app.get("/workouts")
def get_workouts():
    return jsonify(workouts_schema.dump(Workout.query.order_by(Workout.id).all()))


@app.get("/workouts/<int:workout_id>")
def get_workout(workout_id):
    workout = db.get_or_404(Workout, workout_id)
    return jsonify(workout_schema.dump(workout))


@app.post("/workouts")
def create_workout():
    workout = Workout(**workout_schema.load(request.get_json()))
    db.session.add(workout)
    return commit_and_respond(workout, workout_schema, 201)


@app.delete("/workouts/<int:workout_id>")
def delete_workout(workout_id):
    workout = db.get_or_404(Workout, workout_id)
    db.session.delete(workout)
    db.session.commit()
    return "", 204


@app.get("/exercises")
def get_exercises():
    return jsonify(exercises_schema.dump(Exercise.query.order_by(Exercise.id).all()))


@app.get("/exercises/<int:exercise_id>")
def get_exercise(exercise_id):
    exercise = db.get_or_404(Exercise, exercise_id)
    return jsonify(exercise_schema.dump(exercise))


@app.post("/exercises")
def create_exercise():
    exercise = Exercise(**exercise_schema.load(request.get_json()))
    db.session.add(exercise)
    return commit_and_respond(exercise, exercise_schema, 201)


@app.delete("/exercises/<int:exercise_id>")
def delete_exercise(exercise_id):
    exercise = db.get_or_404(Exercise, exercise_id)
    db.session.delete(exercise)
    db.session.commit()
    return "", 204


@app.post(
    "/workouts/<int:workout_id>/exercises/<int:exercise_id>/workout_exercises"
)
def add_exercise_to_workout(workout_id, exercise_id):
    workout = db.get_or_404(Workout, workout_id)
    exercise = db.get_or_404(Exercise, exercise_id)
    prescription = workout_exercise_schema.load(request.get_json())
    association = WorkoutExercise(
        workout=workout,
        exercise=exercise,
        **prescription,
    )
    db.session.add(association)
    return commit_and_respond(association, workout_exercise_schema, 201)


def commit_and_respond(instance, schema, status_code):
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return (
            jsonify(
                {"error": "The resource conflicts with existing data or constraints."}
            ),
            409,
        )
    return jsonify(schema.dump(instance)), status_code


if __name__ == "__main__":
    app.run(port=5555, debug=True)
