from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from .models import User, db


def issue_access_token(user):
    expires_in = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user.id), "iat": now, "exp": now + timedelta(seconds=expires_in)},
        current_app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    return token


def authentication_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token:
            return (
                jsonify({"error": "A valid bearer token is required."}),
                401,
                {"WWW-Authenticate": "Bearer"},
            )

        try:
            claims = jwt.decode(
                token,
                current_app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"],
                options={"require": ["exp", "sub"]},
            )
            user_id = int(claims["sub"])
        except (jwt.InvalidTokenError, TypeError, ValueError):
            return (
                jsonify({"error": "A valid bearer token is required."}),
                401,
                {"WWW-Authenticate": "Bearer"},
            )

        user = db.session.get(User, user_id)
        if user is None:
            return (
                jsonify({"error": "A valid bearer token is required."}),
                401,
                {"WWW-Authenticate": "Bearer"},
            )

        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @authentication_required
    def wrapped(*args, **kwargs):
        if g.current_user.role != "admin":
            return jsonify({"error": "Administrator access is required."}), 403
        return view(*args, **kwargs)

    return wrapped
