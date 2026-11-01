import os
from pathlib import Path
import secrets

from flask import Flask, g, jsonify, request
from flask_migrate import Migrate
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from .auth import admin_required, authentication_required, issue_access_token
from .models import Exercise, User, Workout, WorkoutExercise, db
from .schemas import (
    CredentialsSchema,
    ExerciseSchema,
    RegistrationSchema,
    UserSchema,
    WorkoutExerciseSchema,
    WorkoutSchema,
)


app = Flask(__name__)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY") or secrets.token_urlsafe(32)
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 3600

db.init_app(app)
migrate = Migrate(app, db)

credentials_schema = CredentialsSchema()
registration_schema = RegistrationSchema()
user_schema = UserSchema()
workout_schema = WorkoutSchema()
workouts_schema = WorkoutSchema(many=True)
exercise_schema = ExerciseSchema()
exercises_schema = ExerciseSchema(many=True)
workout_exercise_schema = WorkoutExerciseSchema()


@app.post("/auth/register")
def register():
    credentials = registration_schema.load(request.get_json())
    user = User(username=credentials["username"])
    user.set_password(credentials["password"])
    db.session.add(user)
    return commit_and_respond(user, user_schema, 201)


@app.post("/auth/login")
def login():
    credentials = credentials_schema.load(request.get_json())
    user = User.query.filter_by(username=credentials["username"].strip().lower()).first()
    if user is None or not user.check_password(credentials["password"]):
        return jsonify({"error": "Invalid username or password."}), 401

    return jsonify(
        {
            "access_token": issue_access_token(user),
            "token_type": "Bearer",
            "expires_in": app.config["JWT_ACCESS_TOKEN_EXPIRES"],
        }
    )


@app.get("/auth/me")
@authentication_required
def get_current_user():
    return jsonify(user_schema.dump(db.session.get(User, g.current_user.id)))


@app.errorhandler(ValidationError)
def handle_validation_error(error):
    return jsonify({"errors": error.messages}), 400


@app.errorhandler(HTTPException)
def handle_http_error(error):
    message = "Resource not found." if error.code == 404 else error.description
    return jsonify({"error": message}), error.code


@app.get("/workouts")
@authentication_required
def get_workouts():
    return jsonify(workouts_schema.dump(Workout.query.order_by(Workout.id).all()))


@app.get("/workouts/<int:workout_id>")
@authentication_required
def get_workout(workout_id):
    workout = db.get_or_404(Workout, workout_id)
    return jsonify(workout_schema.dump(workout))


@app.post("/workouts")
@admin_required
def create_workout():
    workout = Workout(**workout_schema.load(request.get_json()))
    db.session.add(workout)
    return commit_and_respond(workout, workout_schema, 201)


@app.delete("/workouts/<int:workout_id>")
@admin_required
def delete_workout(workout_id):
    workout = db.get_or_404(Workout, workout_id)
    db.session.delete(workout)
    db.session.commit()
    return "", 204


@app.get("/exercises")
@authentication_required
def get_exercises():
    return jsonify(exercises_schema.dump(Exercise.query.order_by(Exercise.id).all()))


@app.get("/exercises/<int:exercise_id>")
@authentication_required
def get_exercise(exercise_id):
    exercise = db.get_or_404(Exercise, exercise_id)
    return jsonify(exercise_schema.dump(exercise))


@app.post("/exercises")
@admin_required
def create_exercise():
    exercise = Exercise(**exercise_schema.load(request.get_json()))
    db.session.add(exercise)
    return commit_and_respond(exercise, exercise_schema, 201)


@app.delete("/exercises/<int:exercise_id>")
@admin_required
def delete_exercise(exercise_id):
    exercise = db.get_or_404(Exercise, exercise_id)
    db.session.delete(exercise)
    db.session.commit()
    return "", 204


@app.post(
    "/workouts/<int:workout_id>/exercises/<int:exercise_id>/workout_exercises"
)
@admin_required
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


@app.cli.command("create-admin")
def create_admin():
    """Create the initial admin; defaults are for local development only."""
    import click

    username = os.environ.get("ADMIN_USERNAME", "admin")
    password = os.environ.get("ADMIN_PASSWORD", "admin101")

    try:
        credentials = credentials_schema.load(
            {"username": username, "password": password}
        )
    except ValidationError as error:
        raise click.ClickException(str(error.messages)) from error
    normalized_username = credentials["username"].strip().lower()
    existing_user = User.query.filter_by(username=normalized_username).first()
    if existing_user is not None:
        if existing_user.role == "admin":
            click.echo(f"Admin account '{normalized_username}' already exists.")
            return
        raise click.ClickException(
            f"Username '{normalized_username}' already belongs to a standard user."
        )

    user = User(username=normalized_username, role="admin")
    user.set_password(credentials["password"])
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise click.ClickException("Could not create the admin account.") from error
    click.echo(f"Created admin account '{normalized_username}'.")


if __name__ == "__main__":
    app.run(port=5555, debug=True)
