"""Command-line interface for the Instance Operator and for development."""

import argparse
import getpass
import json
import logging
import sys
from datetime import timedelta
from pathlib import Path

import uvicorn
from sqlalchemy.orm import Session

from cropstar_api.app import create_app
from cropstar_api.auth.provider import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    PasswordAuthProvider,
)
from cropstar_api.db import create_db_engine, migrate
from cropstar_api.seed import seed_demo
from cropstar_api.settings import Settings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="cropstar-api")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="migrate the database, then serve the API")
    serve.add_argument("--no-migrate", action="store_true", help="skip database migrations")
    commands.add_parser("migrate", help="upgrade the database schema to the latest revision")
    openapi = commands.add_parser("openapi", help="write the OpenAPI schema as JSON")
    openapi.add_argument("output", type=Path)
    reset = commands.add_parser(
        "reset-password", help="set a user's password and sign them out everywhere"
    )
    reset.add_argument("email")
    reset.add_argument(
        "--password-stdin", action="store_true", help="read the new password from stdin"
    )
    seed = commands.add_parser(
        "seed-demo", help="development only: a demo Farm with real INVEKOS Fields and Plots"
    )
    seed.add_argument("--email", default="demo@cropstar.local")
    seed.add_argument("--password", default="cropstar-demo")

    args = parser.parse_args(argv)
    # Makes Alembic report which migrations ran.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
    settings = Settings()

    if args.command == "serve":
        if not args.no_migrate:
            migrate(settings.database_url)
        uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
    elif args.command == "migrate":
        migrate(settings.database_url)
    elif args.command == "openapi":
        schema = create_app(settings).openapi()
        args.output.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
    elif args.command == "reset-password":
        sys.exit(_reset_password(settings, args.email, args.password_stdin))
    elif args.command == "seed-demo":
        sys.exit(_seed_demo(settings, args.email, args.password))


def _seed_demo(settings: Settings, email: str, password: str) -> int:
    if settings.environment != "development":
        print("Refusing to add demo data: set CROPSTAR_ENVIRONMENT=development.", file=sys.stderr)
        return 1
    auth = PasswordAuthProvider(timedelta(days=settings.session_lifetime_days))
    engine = create_db_engine(settings.database_url)
    try:
        with Session(engine) as db, db.begin():
            farm = seed_demo(db, auth, email, password)
            print(f"Demo Farm '{farm.name}' ready. Sign in as {email} / {password}.")
    finally:
        engine.dispose()
    return 0


def _reset_password(settings: Settings, email: str, from_stdin: bool) -> int:
    if from_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("New password: ")
        if password != getpass.getpass("Repeat it: "):
            print("The passwords do not match.", file=sys.stderr)
            return 1
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        print(
            f"The password needs {MIN_PASSWORD_LENGTH} to {MAX_PASSWORD_LENGTH} characters.",
            file=sys.stderr,
        )
        return 1
    auth = PasswordAuthProvider(timedelta(days=settings.session_lifetime_days))
    engine = create_db_engine(settings.database_url)
    try:
        with Session(engine) as db, db.begin():
            if not auth.set_password(db, email, password):
                print(f"No user with the email {email}.", file=sys.stderr)
                return 1
    finally:
        engine.dispose()
    print(f"Password set for {email}; all their sessions were signed out.")
    return 0
