from app.auth.security import create_access_token
from app.database.sql_models import User


def make_user(db, email, role="user"):
    user = User(email=email, full_name=email.split("@")[0], hashed_password="not-a-real-hash", role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_header(email):
    return {"Authorization": f"Bearer {create_access_token({'sub': email})}"}


def iter_routes(app):
    """Yield every concrete route, including those nested in included routers (FastAPI 0.162+)."""
    def walk(routes):
        for route in routes:
            if hasattr(route, "effective_candidates"):
                yield from walk(route.effective_candidates())
            else:
                yield route
    yield from walk(app.routes)


def route_path(route):
    """A websocket or plain route nested in an included router keeps its path on starlette_route."""
    return getattr(route, "path", "") or getattr(getattr(route, "starlette_route", None), "path", "")
