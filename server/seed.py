from .app import app
from .models import Exercise, Workout, WorkoutExercise, db


def seed_database():
    db.drop_all()
    db.create_all()

    strength = Workout(name="Full-body strength", description="A balanced strength session.")
    conditioning = Workout(name="Conditioning", description="A short conditioning session.")
    squat = Exercise(name="Goblet squat", muscle_group="Legs")
    push_up = Exercise(name="Push-up", muscle_group="Chest")
    plank = Exercise(name="Plank", muscle_group="Core")

    strength.workout_exercises.extend(
        [
            WorkoutExercise(exercise=squat, sets=3, reps=10),
            WorkoutExercise(exercise=push_up, sets=3, reps=12),
        ]
    )
    conditioning.workout_exercises.append(
        WorkoutExercise(exercise=plank, duration_seconds=45)
    )
    db.session.add_all([strength, conditioning])
    db.session.commit()


if __name__ == "__main__":
    with app.app_context():
        seed_database()
