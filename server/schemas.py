from marshmallow import RAISE, Schema, ValidationError, fields, validates, validates_schema


class RequestSchema(Schema):
    class Meta:
        unknown = RAISE


class WorkoutExerciseSchema(RequestSchema):
    id = fields.Int(dump_only=True)
    workout_id = fields.Int(dump_only=True)
    exercise_id = fields.Int(dump_only=True)
    sets = fields.Int(strict=True, allow_none=True, load_default=None)
    reps = fields.Int(strict=True, allow_none=True, load_default=None)
    duration_seconds = fields.Int(strict=True, allow_none=True, load_default=None)
    exercise = fields.Nested("ExerciseSchema", dump_only=True)

    @validates("sets")
    @validates("reps")
    @validates("duration_seconds")
    def validate_positive_integer(self, value, **_kwargs):
        if value is not None and value <= 0:
            raise ValidationError("Value must be a positive integer.")

    @validates_schema
    def validate_prescription(self, data, **_kwargs):
        timed = data.get("duration_seconds") is not None
        repetitions = data.get("sets") is not None and data.get("reps") is not None
        if timed == repetitions:
            raise ValidationError(
                "Provide either duration_seconds or both sets and reps."
            )


class WorkoutSchema(RequestSchema):
    id = fields.Int(dump_only=True)
    name = fields.String(required=True)
    description = fields.String(allow_none=True, load_default=None)
    workout_exercises = fields.Nested(
        WorkoutExerciseSchema,
        many=True,
        dump_only=True,
    )

    @validates("name")
    def validate_name(self, value, **_kwargs):
        if not value.strip() or len(value) > 120:
            raise ValidationError("Name must contain 1 to 120 non-whitespace characters.")

    @validates("description")
    def validate_description(self, value, **_kwargs):
        if value is not None and len(value) > 500:
            raise ValidationError("Description must be at most 500 characters.")


class ExerciseSchema(RequestSchema):
    id = fields.Int(dump_only=True)
    name = fields.String(required=True)
    muscle_group = fields.String(required=True)
    description = fields.String(allow_none=True, load_default=None)

    @validates("name")
    def validate_name(self, value, **_kwargs):
        if not value.strip() or len(value) > 120:
            raise ValidationError("Name must contain 1 to 120 non-whitespace characters.")

    @validates("muscle_group")
    def validate_muscle_group(self, value, **_kwargs):
        if not value.strip() or len(value) > 80:
            raise ValidationError("Muscle group must contain 1 to 80 non-whitespace characters.")

    @validates("description")
    def validate_description(self, value, **_kwargs):
        if value is not None and len(value) > 500:
            raise ValidationError("Description must be at most 500 characters.")
