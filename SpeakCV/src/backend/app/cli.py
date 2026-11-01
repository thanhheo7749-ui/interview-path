import argparse

from app.database.migrate import run_migrations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="Upgrade the database schema to the latest revision")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "migrate":
        run_migrations()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
