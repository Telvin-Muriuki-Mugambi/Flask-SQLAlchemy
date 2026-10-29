# Workout Tracking API

A Flask REST API for managing reusable exercises and workouts. A workout can
contain multiple exercises, each with a rep-based prescription (sets and reps)
or a timed prescription (duration in seconds).

## Requirements

- Python 3.8 or newer
- Pipenv

## Installation and database setup

From the repository root, install the dependencies and apply the included
database migration:

```bash
pipenv install --dev
pipenv run flask --app server.app db upgrade
pipenv run python -m server.seed
```

After changing the models, create a migration with
`pipenv run flask --app server.app db migrate -m "Describe the schema change"`
and apply it with `pipenv run flask --app server.app db upgrade`.

The seed command resets the database and inserts example workouts, exercises,
and their associations. Re-running it is safe.

## Run the API

```bash
pipenv run flask --app server.app run --port 5555
```

The API is available at `http://127.0.0.1:5555`.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/workouts` | List workouts and their exercise prescriptions. |
| GET | `/workouts/<id>` | Retrieve one workout and its exercise prescriptions. |
| POST | `/workouts` | Create a workout with `name` and optional `description`. |
| DELETE | `/workouts/<id>` | Delete a workout and its exercise associations. |
| GET | `/exercises` | List reusable exercises. |
| GET | `/exercises/<id>` | Retrieve one exercise. |
| POST | `/exercises` | Create an exercise with `name`, `muscle_group`, and optional `description`. |
| DELETE | `/exercises/<id>` | Delete an exercise and its workout associations. |
| POST | `/workouts/<workout_id>/exercises/<exercise_id>/workout_exercises` | Add an exercise to a workout with either `sets` and `reps`, or `duration_seconds`. |

Creation endpoints return the created resource with status `201`. Invalid
request data returns `400`, missing resources return `404`, and database
constraint conflicts return `409`. Successful deletes return `204`.

Names and muscle groups must be non-empty and within their configured length
limits. Workout and exercise names are unique. Prescriptions must use positive
integer values, and an exercise cannot be added to the same workout twice.

## Tests

```bash
pipenv run pytest
```
