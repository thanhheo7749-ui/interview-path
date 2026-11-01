from app.auth.security import verify_password
from app.cli import main
from app.database.sql_models import Company, CompanyMember, User


def test_create_company_makes_the_first_hr_user_and_prints_a_password_once(db, capsys):
    code = main(["create-company", "--slug", "sori", "--name", "Sori Labs", "--hr-email", "hr@sori.test", "--hr-name", "Sori HR", "--sample"])
    assert code == 0
    company = db.query(Company).filter_by(slug="sori").one()
    assert company.is_sample is True
    user = db.query(User).filter_by(email="hr@sori.test").one()
    member = db.query(CompanyMember).filter_by(company_id=company.id, user_id=user.id).one()
    assert member.role == "hr"
    output = capsys.readouterr().out
    password = next(line.split()[-1] for line in output.splitlines() if "password" in line.lower())
    assert verify_password(password, user.hashed_password)


def test_create_company_for_an_existing_user_keeps_their_password(db, capsys):
    user = User(email="hr@sori.test", full_name="HR", hashed_password="existing-hash")
    db.add(user)
    db.commit()
    assert main(["create-company", "--slug", "sori", "--name", "Sori", "--hr-email", "hr@sori.test", "--hr-name", "HR"]) == 0
    db.expire_all()
    assert db.get(User, user.id).hashed_password == "existing-hash"
    assert "password" not in capsys.readouterr().out.lower()


def test_duplicate_slug_fails_clearly(db, capsys):
    args = ["create-company", "--slug", "sori", "--name", "Sori", "--hr-email", "hr@sori.test", "--hr-name", "HR"]
    assert main(args) == 0
    assert main(args) != 0
    assert "sori" in capsys.readouterr().err
