"""Command-line interface for the Instance Operator and for development."""

import argparse
import json
import logging
from pathlib import Path

import uvicorn

from cropstar_api.app import create_app
from cropstar_api.db import migrate
from cropstar_api.settings import Settings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="cropstar-api")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="migrate the database, then serve the API")
    serve.add_argument("--no-migrate", action="store_true", help="skip database migrations")
    commands.add_parser("migrate", help="upgrade the database schema to the latest revision")
    openapi = commands.add_parser("openapi", help="write the OpenAPI schema as JSON")
    openapi.add_argument("output", type=Path)

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
