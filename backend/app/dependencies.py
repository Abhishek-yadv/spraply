import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Team, TeamAPIKey, TeamMember, User
from app.security import decode_token


bearer_scheme = HTTPBearer(auto_error=False)


def _create_default_team_if_needed(db: Session, user: User) -> Team:
    existing_team = db.scalar(
        select(Team).join(TeamMember, TeamMember.team_id == Team.uuid).where(TeamMember.user_id == user.uuid).order_by(Team.created_at.asc())
    )
    if existing_team:
        return existing_team

    team = Team(uuid=uuid4(), name="Default", is_default=True)
    db.add(team)
    db.flush()

    member = TeamMember(uuid=uuid4(), user_id=user.uuid, team_id=team.uuid, is_owner=True)
    db.add(member)
    api_key = TeamAPIKey(uuid=uuid4(), team_id=team.uuid, name="Default", key=f"wc_{secrets.token_urlsafe(32)}")
    db.add(api_key)
    db.commit()
    db.refresh(team)
    return team


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
        )

    try:
        token_data = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    token_type = token_data.get("type")
    if token_type != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = token_data.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.get(User, UUID(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_current_team(
    x_team_id: str | None = Header(default=None, alias="X-TEAM-ID"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> Team:
    if credentials is not None:
        user = get_current_user(credentials, db)
        if x_team_id:
            try:
                team_uuid = UUID(x_team_id)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid team ID")
            team_member = db.scalar(
                select(TeamMember).where(
                    TeamMember.user_id == user.uuid,
                    TeamMember.team_id == team_uuid,
                )
            )
            if team_member:
                team = db.get(Team, team_member.team_id)
                if team:
                    return team

        return _create_default_team_if_needed(db, user)

    if x_api_key:
        api_key = db.scalar(select(TeamAPIKey).where(TeamAPIKey.key == x_api_key))
        if not api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        api_key.last_used_at = datetime.now(UTC)
        db.add(api_key)
        db.commit()
        team = db.get(Team, api_key.team_id)
        if not team:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        return team

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def get_current_user_with_team(
    user: User = Depends(get_current_user),
    _: Team = Depends(get_current_team),
) -> User:
    return user
