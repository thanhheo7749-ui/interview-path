import argparse
import secrets
import sys

from sqlalchemy import func

from app.database.database import SessionLocal
from app.database.migrate import run_migrations
from app.database.sql_models import Company, CompanyMember, KbChunk, KbNode, User

REEMBED_BATCH_SIZE = 64


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

    reembed_parser = commands.add_parser("reembed", help="Regenerate knowledge base vectors with the current embedding slot")
    reembed_parser.add_argument("--company", help="Company slug. Defaults to every company.")

    seed_parser = commands.add_parser(
        "seed-samples", help="Create the two fictional sample companies and run their documents through the pipeline"
    )
    seed_parser.add_argument("--auto-approve", action="store_true", help="Publish everything. Sample companies only.")
    seed_parser.add_argument("--only", help="Seed one sample company by slug.")

    commands.add_parser("retention", help="Anonymize every application past its retention date")
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
            user = User(
                email=email,
                full_name=args.hr_name,
                hashed_password=get_password_hash(temporary_password),
                must_change_password=True,
            )
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


def _reembed_rows(rows, texts, company_id) -> None:
    from app.ai import gateway
    from app.brain import vectors

    for start in range(0, len(rows), REEMBED_BATCH_SIZE):
        batch = rows[start:start + REEMBED_BATCH_SIZE]
        result = gateway.embed(texts[start:start + REEMBED_BATCH_SIZE], "document", "kb_reembed", company_id)
        for row, vector in zip(batch, result.vectors):
            row.embedding = vectors.encode(vector)
            row.embedding_model = result.model
            row.embedding_dim = result.dimension


def reembed(args) -> int:
    from app.brain import retriever

    db = SessionLocal()
    try:
        query = db.query(Company).order_by(Company.id)
        if args.company:
            query = query.filter(Company.slug == args.company)
        companies = query.all()
        if args.company and not companies:
            print(f"No company with the slug '{args.company}'.", file=sys.stderr)
            return 1

        for company in companies:
            chunks = db.query(KbChunk).filter(KbChunk.company_id == company.id).order_by(KbChunk.id).all()
            nodes = (
                db.query(KbNode)
                .filter(KbNode.company_id == company.id, KbNode.status != "rejected")
                .order_by(KbNode.id)
                .all()
            )
            _reembed_rows(chunks, [chunk.text for chunk in chunks], company.id)
            _reembed_rows(nodes, [retriever.node_text(node) for node in nodes], company.id)
            # One commit per company, so a failed vendor call leaves its old vectors and version in place.
            company.kb_version = Company.kb_version + 1
            db.commit()
            print(f"Re-embedded {len(chunks)} chunks and {len(nodes)} nodes for '{company.slug}'.")
        return 0
    finally:
        db.close()


def seed_samples(args) -> int:
    from app.brain import seed

    try:
        seed.seed_samples(auto_approve=args.auto_approve, only=args.only)
    except (seed.SeedError, PermissionError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def retention_command(_args) -> int:
    from app.hiring import retention

    db = SessionLocal()
    try:
        print(f"Anonymized {retention.run(db)} applications.")
        return 0
    finally:
        db.close()


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "migrate":
        run_migrations()
    elif args.command == "create-company":
        return create_company(args)
    elif args.command == "reembed":
        return reembed(args)
    elif args.command == "seed-samples":
        return seed_samples(args)
    elif args.command == "retention":
        return retention_command(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
