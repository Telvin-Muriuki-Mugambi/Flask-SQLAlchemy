"""Interactive terminal client for the workout tracking API."""

import argparse
from getpass import getpass
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_API_URL = "http://127.0.0.1:5555"


class ApiError(Exception):
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body
        super().__init__(self._message())

    def _message(self):
        if isinstance(self.body, dict):
            if "error" in self.body:
                return str(self.body["error"])
            if "errors" in self.body:
                return json.dumps(self.body["errors"], indent=2)
        return str(self.body or "The API returned an error.")


class ApiClient:
    def __init__(self, base_url=DEFAULT_API_URL, transport=None):
        self.base_url = base_url.rstrip("/")
        self.transport = transport or self._send_request
        self.access_token = None

    def request(self, method, path, payload=None):
        status_code, body = self.transport(method, path, payload)
        if status_code >= 400:
            raise ApiError(status_code, body)
        return body

    def login(self, username, password):
        response = self.request(
            "POST",
            "/auth/login",
            {"username": username, "password": password},
        )
        self.access_token = response["access_token"]

    def register(self, username, password):
        return self.request(
            "POST",
            "/auth/register",
            {"username": username, "password": password},
        )

    def _send_request(self, method, path, payload):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=5) as response:
                response_body = response.read()
                parsed_body = json.loads(response_body) if response_body else None
                return response.status, parsed_body
        except HTTPError as error:
            response_body = error.read()
            try:
                parsed_body = json.loads(response_body) if response_body else None
            except json.JSONDecodeError:
                parsed_body = {"error": error.reason}
            return error.code, parsed_body
        except (URLError, TimeoutError) as error:
            raise ConnectionError(
                f"Could not reach the API at {self.base_url}. "
                "Start the Flask server and try again."
            ) from error


MENU = (
    ("1", "List workouts"),
    ("2", "View workout details"),
    ("3", "Create a workout"),
    ("4", "Delete a workout"),
    ("5", "List exercises"),
    ("6", "View exercise details"),
    ("7", "Create an exercise"),
    ("8", "Delete an exercise"),
    ("9", "Add an exercise to a workout"),
    ("0", "Quit"),
)


def _show_menu(output_fn):
    output_fn("\n=== Workout Tracker ===")
    for choice, label in MENU:
        output_fn(f"{choice}. {label}")


def _choose_record(records, label, input_fn, output_fn):
    if not records:
        output_fn(f"No {label.lower()} found. Create one first.")
        return None

    output_fn(f"\n{label}:")
    for record in records:
        detail = record["name"]
        if "muscle_group" in record:
            detail += f" - {record['muscle_group']}"
        output_fn(f"  {record['id']}. {detail}")

    selected_id = input_fn(f"Enter the {label[:-1].lower()} ID (or 0 to cancel): ").strip()
    if selected_id == "0":
        return None
    try:
        selected_id = int(selected_id)
    except ValueError:
        output_fn("Please enter a listed numeric ID.")
        return None

    for record in records:
        if record["id"] == selected_id:
            return record
    output_fn("That ID is not in the list.")
    return None


def _show_workout(workout, output_fn):
    output_fn(f"\n{workout['name']} (ID {workout['id']})")
    if workout.get("description"):
        output_fn(workout["description"])
    exercises = workout.get("workout_exercises", [])
    if not exercises:
        output_fn("No exercises added yet.")
        return
    output_fn("Exercises:")
    for association in exercises:
        exercise = association["exercise"]
        if association.get("duration_seconds") is not None:
            prescription = f"{association['duration_seconds']} seconds"
        else:
            prescription = f"{association['sets']} sets x {association['reps']} reps"
        output_fn(f"  - {exercise['name']} ({exercise['muscle_group']}): {prescription}")


def _positive_integer(prompt, input_fn, output_fn):
    while True:
        value = input_fn(prompt).strip()
        try:
            number = int(value)
        except ValueError:
            output_fn("Enter a whole number greater than zero.")
            continue
        if number > 0:
            return number
        output_fn("Enter a whole number greater than zero.")


def _confirm_delete(record, input_fn, output_fn):
    confirmation = input_fn(
        f"Delete '{record['name']}'? This cannot be undone. [y/N]: "
    ).strip().lower()
    if confirmation == "y":
        return True
    output_fn("Delete cancelled.")
    return False


def _handle_choice(choice, api, input_fn, output_fn):
    if choice == "1":
        workouts = api.request("GET", "/workouts")
        if not workouts:
            output_fn("No workouts yet. Create one to get started.")
        for workout in workouts:
            exercise_count = len(workout.get("workout_exercises", []))
            output_fn(f"{workout['id']}. {workout['name']} ({exercise_count} exercises)")
    elif choice == "2":
        workout = _choose_record(
            api.request("GET", "/workouts"), "Workouts", input_fn, output_fn
        )
        if workout:
            _show_workout(
                api.request("GET", f"/workouts/{workout['id']}"), output_fn
            )
    elif choice == "3":
        name = input_fn("Workout name: ").strip()
        description = input_fn("Description (optional): ").strip()
        workout = api.request(
            "POST",
            "/workouts",
            {"name": name, "description": description or None},
        )
        output_fn(f"Created workout '{workout['name']}' (ID {workout['id']}).")
    elif choice == "4":
        workout = _choose_record(
            api.request("GET", "/workouts"), "Workouts", input_fn, output_fn
        )
        if workout and _confirm_delete(workout, input_fn, output_fn):
            api.request("DELETE", f"/workouts/{workout['id']}")
            output_fn(f"Deleted workout '{workout['name']}'.")
    elif choice == "5":
        exercises = api.request("GET", "/exercises")
        if not exercises:
            output_fn("No exercises yet. Create one to get started.")
        for exercise in exercises:
            output_fn(
                f"{exercise['id']}. {exercise['name']} - {exercise['muscle_group']}"
            )
    elif choice == "6":
        exercise = _choose_record(
            api.request("GET", "/exercises"), "Exercises", input_fn, output_fn
        )
        if exercise:
            details = api.request("GET", f"/exercises/{exercise['id']}")
            output_fn(f"\n{details['name']} (ID {details['id']})")
            output_fn(f"Muscle group: {details['muscle_group']}")
            if details.get("description"):
                output_fn(details["description"])
    elif choice == "7":
        name = input_fn("Exercise name: ").strip()
        muscle_group = input_fn("Muscle group: ").strip()
        description = input_fn("Description (optional): ").strip()
        exercise = api.request(
            "POST",
            "/exercises",
            {
                "name": name,
                "muscle_group": muscle_group,
                "description": description or None,
            },
        )
        output_fn(f"Created exercise '{exercise['name']}' (ID {exercise['id']}).")
    elif choice == "8":
        exercise = _choose_record(
            api.request("GET", "/exercises"), "Exercises", input_fn, output_fn
        )
        if exercise and _confirm_delete(exercise, input_fn, output_fn):
            api.request("DELETE", f"/exercises/{exercise['id']}")
            output_fn(f"Deleted exercise '{exercise['name']}'.")
    elif choice == "9":
        workout = _choose_record(
            api.request("GET", "/workouts"), "Workouts", input_fn, output_fn
        )
        if workout is None:
            return
        exercise = _choose_record(
            api.request("GET", "/exercises"), "Exercises", input_fn, output_fn
        )
        if exercise is None:
            return

        output_fn("Choose a prescription:")
        output_fn("1. Sets and reps")
        output_fn("2. Timed exercise")
        while True:
            prescription_type = input_fn("Choose 1 or 2 (or 0 to cancel): ").strip()
            if prescription_type in {"0", "1", "2"}:
                break
            output_fn("Please choose 1, 2, or 0 to cancel.")
        if prescription_type == "0":
            output_fn("Adding exercise cancelled.")
            return
        if prescription_type == "1":
            prescription = {
                "sets": _positive_integer("Number of sets: ", input_fn, output_fn),
                "reps": _positive_integer("Reps per set: ", input_fn, output_fn),
            }
        else:
            prescription = {
                "duration_seconds": _positive_integer(
                    "Duration in seconds: ", input_fn, output_fn
                )
            }

        api.request(
            "POST",
            f"/workouts/{workout['id']}/exercises/{exercise['id']}/workout_exercises",
            prescription,
        )
        output_fn(
            f"Added '{exercise['name']}' to '{workout['name']}'. "
            "View workout details to see the updated plan."
        )


def run_cli(api=None, input_fn=input, output_fn=print):
    api = api or ApiClient()
    output_fn("Manage workouts and reusable exercises from your terminal.")
    while True:
        _show_menu(output_fn)
        choice = input_fn("Choose an option: ").strip()
        if choice == "0":
            output_fn("Goodbye!")
            return
        if choice not in {item[0] for item in MENU}:
            output_fn("Please choose one of the listed options.")
            continue
        try:
            _handle_choice(choice, api, input_fn, output_fn)
        except ApiError as error:
            output_fn(f"API error ({error.status_code}): {error}")
        except ConnectionError as error:
            output_fn(str(error))


def main():
    parser = argparse.ArgumentParser(description="Workout tracker interactive CLI")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("WORKOUT_API_URL", DEFAULT_API_URL),
        help=f"API server URL (default: {DEFAULT_API_URL}, or WORKOUT_API_URL)",
    )
    args = parser.parse_args()
    try:
        api = ApiClient(args.base_url)
        print("1. Log in")
        print("2. Sign up")
        action = input("Choose an option: ").strip()
        if action not in {"1", "2"}:
            print("Choose 1 to log in or 2 to sign up.")
            return
        username = input("Username: ").strip()
        password = getpass("Password: ")
        if action == "2":
            api.register(username, password)
            print("Account created. Logging in...")
        api.login(username, password)
        run_cli(api)
    except ApiError as error:
        print(f"API error ({error.status_code}): {error}")
    except ConnectionError as error:
        print(str(error))
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
