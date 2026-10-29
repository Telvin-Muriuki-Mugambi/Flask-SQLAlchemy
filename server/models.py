from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import validates
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Workout(db.Model):
    __tablename__ = "workouts"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_workouts_name_nonempty"),
        UniqueConstraint("name", name="uq_workouts_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    workout_exercises = db.relationship(
        "WorkoutExercise",
        back_populates="workout",
        cascade="all, delete-orphan",
    )
    exercises = db.relationship(
        "Exercise",
        secondary="workout_exercises",
        viewonly=True,
    )

    @validates("name")
    def validate_name(self, _key, value):
        if not isinstance(value, str):
            raise ValueError("Workout name must be a string.")
        value = value.strip()
        if not value or len(value) > 120:
            raise ValueError("Workout name must contain 1 to 120 characters.")
        return value

    @validates("description")
    def validate_description(self, _key, value):
        if value is not None and (not isinstance(value, str) or len(value) > 500):
            raise ValueError("Workout description must be at most 500 characters.")
        return value


class Exercise(db.Model):
    __tablename__ = "exercises"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_exercises_name_nonempty"),
        CheckConstraint(
            "length(trim(muscle_group)) > 0",
            name="ck_exercises_muscle_group_nonempty",
        ),
        UniqueConstraint("name", name="uq_exercises_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    muscle_group = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    workout_exercises = db.relationship(
        "WorkoutExercise",
        back_populates="exercise",
        cascade="all, delete-orphan",
    )
    workouts = db.relationship(
        "Workout",
        secondary="workout_exercises",
        viewonly=True,
    )

    @validates("name")
    def validate_name(self, _key, value):
        if not isinstance(value, str):
            raise ValueError("Exercise name must be a string.")
        value = value.strip()
        if not value or len(value) > 120:
            raise ValueError("Exercise name must contain 1 to 120 characters.")
        return value

    @validates("muscle_group")
    def validate_muscle_group(self, _key, value):
        if not isinstance(value, str):
            raise ValueError("Muscle group must be a string.")
        value = value.strip()
        if not value or len(value) > 80:
            raise ValueError("Muscle group must contain 1 to 80 characters.")
        return value

    @validates("description")
    def validate_description(self, _key, value):
        if value is not None and (not isinstance(value, str) or len(value) > 500):
            raise ValueError("Exercise description must be at most 500 characters.")
        return value


class WorkoutExercise(db.Model):
    __tablename__ = "workout_exercises"
    __table_args__ = (
        UniqueConstraint(
            "workout_id",
            "exercise_id",
            name="uq_workout_exercises_workout_exercise",
        ),
        CheckConstraint(
            "(duration_seconds IS NOT NULL AND duration_seconds > 0 "
            "AND sets IS NULL AND reps IS NULL) OR "
            "(duration_seconds IS NULL AND sets IS NOT NULL AND sets > 0 "
            "AND reps IS NOT NULL AND reps > 0)",
            name="ck_workout_exercises_positive_prescription",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(
        db.Integer,
        db.ForeignKey("workouts.id", ondelete="CASCADE"),
        nullable=False,
    )
    exercise_id = db.Column(
        db.Integer,
        db.ForeignKey("exercises.id", ondelete="CASCADE"),
        nullable=False,
    )
    sets = db.Column(db.Integer, nullable=True)
    reps = db.Column(db.Integer, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)
    workout = db.relationship("Workout", back_populates="workout_exercises")
    exercise = db.relationship("Exercise", back_populates="workout_exercises")

    @validates("sets", "reps", "duration_seconds")
    def validate_positive_prescription(self, key, value):
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
        ):
            raise ValueError(f"{key.replace('_', ' ').capitalize()} must be a positive integer.")
        return value
