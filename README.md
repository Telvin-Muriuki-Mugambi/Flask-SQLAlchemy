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
and their associations. Re-running it is safe, but it also deletes all user
accounts; run the admin bootstrap command again afterward if needed.

## Authentication and authorization

Set a persistent, high-entropy signing key before running the API in production:

```bash
export JWT_SECRET_KEY="replace-with-a-long-random-secret"
```

If `JWT_SECRET_KEY` is not set, the app generates an ephemeral key at startup;
tokens then stop working when the process restarts. Never use that fallback in
production.

All workout and exercise endpoints require an access token. New accounts can be
registered as standard users:

```bash
curl -X POST http://127.0.0.1:5555/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"runner1","password":"a-long-unique-password"}'
```

Passwords must be at least 12 characters and are stored as password hashes.
Registration never grants administrator privileges. After applying migrations,
create the initial admin with the requested local-development credentials:

```bash
pipenv run flask --app server.app create-admin
```

This creates username `admin` with password `admin101`. That password is
intentionally weak and must only be used for local demonstrations. For any
shared or deployed environment, set unique credentials before running the
command:

```bash
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="replace-with-a-long-unique-password"
pipenv run flask --app server.app create-admin
```

This command is idempotent for an existing admin account and will not promote a
standard account. Sign in to obtain a one-hour JWT bearer token:

```bash
curl -X POST http://127.0.0.1:5555/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"runner1","password":"a-long-unique-password"}'
```

Send the returned `access_token` in the `Authorization: Bearer <token>` header.
`GET /auth/me` returns the authenticated account. Standard users can read
workouts and exercises; admins have full read, create, and delete access,
including adding exercises to workouts. Clients should discard tokens when
signing out; there is no server-side token revocation.

## Run the API

```bash
pipenv run flask --app server.app run --port 5555
```

The API is available at `http://127.0.0.1:5555`.

## Interactive CLI

Start the API in one terminal, then launch the interactive CLI from the
repository root in another:

```bash
pipenv run python -m server.cli
```

The CLI guides you through listing, viewing, creating, and deleting workouts
and exercises, and adding exercises to workouts with either sets and reps or a
duration. It shows available records before asking you to select one and asks
for confirmation before deletion. At startup, choose **Sign up** to create a
standard account or **Log in** to use an existing account. It then sends
authenticated requests. API validation messages are shown in the terminal.

To connect to an API running at a different address, set `WORKOUT_API_URL` or
pass `--base-url`:

```bash
pipenv run python -m server.cli --base-url http://127.0.0.1:5555
```

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| POST | `/auth/register` | Register a standard user with a username and password. |
| POST | `/auth/login` | Exchange credentials for a one-hour bearer token. |
| GET | `/auth/me` | Retrieve the authenticated account. |
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
