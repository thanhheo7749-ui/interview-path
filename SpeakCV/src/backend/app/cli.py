import argparse
import secrets
import sys

from sqlalchemy import func

from app.database.database import SessionLocal
from app.database.migrate import run_migrations
from app.database.sql_models import Company, CompanyMember, User


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="Upgrade the database schema to the latest revision")

    create_company_parser = commands.add_parser("create-company", help="Create a company and its first HR member")
    create_company_parser.add_argument("--slug", required=True)
    create_company_parser.add_argument("--name", required=True)
    create_company_parser.add_argument("--hr-email", required=True)
    create_company_parser.add_argument("--hr-name", required=True)
    create_company_parser.add_argument("--sample", action="store_true")
    create_company_parser.add_argument("--locale", default="en")
    return parser


def create_company(args) -> int:
    # Imported here because it requires SECRET_KEY, which `migrate` does not need.
    from app.auth.security import get_password_hash

    db = SessionLocal()
    try:
        if db.query(Company.id).filter(Company.slug == args.slug).first():
            print(f"A company with the slug '{args.slug}' already exists.", file=sys.stderr)
            return 1

        company = Company(slug=args.slug, name=args.name, is_sample=args.sample, default_locale=args.locale)
        db.add(company)
        db.flush()

        email = args.hr_email.strip().lower()
        user = db.query(User).filter(func.lower(User.email) == email).first()
        temporary_password = None
        if user is None:
            temporary_password = secrets.token_urlsafe(12)
            user = User(email=email, full_name=args.hr_name, hashed_password=get_password_hash(temporary_password))
            db.add(user)
            db.flush()

        db.add(CompanyMember(company_id=company.id, user_id=user.id, role="hr"))
        db.commit()
        from app.brain import org_sync

        org_sync.sync_org_nodes(db, company.id)
        print(f"Created company '{args.slug}' with HR member {email}.")
        if temporary_password:
            print(f"Temporary password for {email}: {temporary_password}")
        return 0
    finally:
        db.close()


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "migrate":
        run_migrations()
    elif args.command == "create-company":
        return create_company(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
