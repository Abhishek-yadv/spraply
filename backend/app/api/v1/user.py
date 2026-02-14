import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies import get_current_team, get_current_user
from app.models import Team, TeamAPIKey, TeamInvitation, TeamMember, User
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


router = APIRouter()


class InstallRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    newsletter_confirmed: bool = False
    analytics_confirmed: bool = False


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = ""
    last_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    refresh: str
    access: str


class RefreshRequest(BaseModel):
    refresh: str


class VerifyTokenRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=8)


class OAuthRequest(BaseModel):
    provider: str
    token: str


class ProfileResponse(BaseModel):
    uuid: UUID
    email: EmailStr
    first_name: str
    last_name: str
    email_verified: bool
    privacy_confirmed_at: datetime | None
    terms_confirmed_at: datetime | None
    newsletter_confirmed: bool
    created_at: datetime


class ProfilePatchRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    password: str | None = Field(default=None, min_length=8)
    privacy_confirmed: bool | None = None
    terms_confirmed: bool | None = None
    newsletter_confirmed: bool | None = None


class TeamResponse(BaseModel):
    uuid: UUID
    name: str
    is_default: bool


class TeamCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class TeamInvitationRequest(BaseModel):
    email: EmailStr


class TeamInvitationResponse(BaseModel):
    uuid: UUID
    email: EmailStr
    created_at: datetime


class APIKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class APIKeyResponse(BaseModel):
    uuid: UUID
    name: str
    key: str
    created_at: datetime
    last_used_at: datetime | None


class TeamMemberUserResponse(BaseModel):
    uuid: UUID
    email: EmailStr
    first_name: str
    last_name: str
    email_verified: bool


class TeamMemberResponse(BaseModel):
    uuid: UUID
    user: TeamMemberUserResponse
    is_owner: bool


class RequestEmailVerificationRequest(BaseModel):
    email: EmailStr


class InvitationAcceptResponse(BaseModel):
    new_user: bool
    email: str
    invitation_code: str


def _create_team_for_user(db: Session, user: User, name: str, is_default: bool, is_owner: bool) -> Team:
    team = Team(uuid=uuid4(), name=name, is_default=is_default)
    db.add(team)
    db.flush()

    team_member = TeamMember(uuid=uuid4(), user_id=user.uuid, team_id=team.uuid, is_owner=is_owner)
    db.add(team_member)

    api_key = TeamAPIKey(
        uuid=uuid4(),
        name="Default",
        team_id=team.uuid,
        key=f"wc_{secrets.token_urlsafe(32)}",
    )
    db.add(api_key)
    db.commit()
    db.refresh(team)
    return team


def issue_tokens(user_id: UUID) -> TokenResponse:
    refresh = create_refresh_token(user_id)
    access = create_access_token(user_id)
    return TokenResponse(refresh=refresh, access=access)


@router.post("/install/", status_code=status.HTTP_204_NO_CONTENT)
def install(payload: InstallRequest, db: Session = Depends(get_db)) -> Response:
    installed = db.scalar(select(func.count()).select_from(User))
    if installed and installed > 0:
        raise HTTPException(status_code=400, detail="Already installed")

    user = User(
        uuid=uuid4(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        email_verified=True,
        is_active=True,
        is_staff=True,
        is_superuser=True,
        newsletter_confirmed=payload.newsletter_confirmed,
    )
    db.add(user)
    db.flush()
    _create_team_for_user(db, user, name="Default", is_default=True, is_owner=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/register/", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> ProfileResponse:
    if not settings.is_signup_active:
        raise HTTPException(status_code=403, detail="Signup is disabled")

    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    user = User(
        uuid=uuid4(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return ProfileResponse(**user.__dict__)


@router.get("/auth/invitation/{invitation_code}/")
def verify_invitation(invitation_code: str, db: Session = Depends(get_db)) -> InvitationAcceptResponse:
    invitation = db.scalar(
        select(TeamInvitation).where(
            TeamInvitation.invitation_token == invitation_code,
            TeamInvitation.activated.is_(False),
        )
    )
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    existing = db.scalar(select(User).where(User.email == invitation.email.lower()))
    return InvitationAcceptResponse(
        new_user=existing is None,
        email=invitation.email,
        invitation_code=invitation_code,
    )


@router.post("/auth/invitation/{invitation_code}/", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def accept_invitation(
    invitation_code: str,
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> ProfileResponse:
    invitation = db.scalar(
        select(TeamInvitation).where(
            TeamInvitation.invitation_token == invitation_code,
            TeamInvitation.activated.is_(False),
        )
    )
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.email.lower() != payload.email.lower():
        raise HTTPException(status_code=400, detail="Emails do not match")

    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=400, detail="You already have an account")

    user = User(
        uuid=uuid4(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        email_verified=True,
    )
    db.add(user)
    db.flush()
    team_member = TeamMember(uuid=uuid4(), user_id=user.uuid, team_id=invitation.team_id, is_owner=False)
    db.add(team_member)
    invitation.activated = True
    invitation.invitation_token = None
    db.add(invitation)
    db.commit()
    db.refresh(user)
    return ProfileResponse(**user.__dict__)


@router.post("/auth/login/", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if not settings.is_login_active:
        raise HTTPException(status_code=403, detail="Login is disabled")

    user = db.scalar(select(User).where(User.email == payload.email.lower(), User.is_active.is_(True)))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid email or password")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Email is not verified")
    return issue_tokens(user.uuid)


@router.post("/auth/token/refresh/", response_model=TokenResponse)
def refresh_token(payload: RefreshRequest) -> TokenResponse:
    try:
        token_data = decode_token(payload.refresh)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if token_data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return issue_tokens(UUID(token_data["sub"]))


@router.post("/auth/token/verify/")
def verify_token(payload: VerifyTokenRequest) -> dict:
    try:
        decode_token(payload.token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"valid": True}


@router.post("/auth/oauth/", response_model=TokenResponse)
def oauth_login(payload: OAuthRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = f"{payload.provider}-{payload.token[:8]}@oauth.spraply.local".lower()
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(
            uuid=uuid4(),
            email=email,
            password_hash=None,
            first_name=payload.provider,
            last_name="",
            email_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return issue_tokens(user.uuid)


@router.get("/auth/reset-password/{token}/", status_code=status.HTTP_204_NO_CONTENT)
def validate_reset_token(token: str, db: Session = Depends(get_db)) -> Response:
    user = db.scalar(
        select(User).where(
            User.reset_password_token == token,
            User.reset_password_expires_at.is_not(None),
            User.reset_password_expires_at > datetime.now(UTC),
        )
    )
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/reset-password/{token}/", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(token: str, payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> Response:
    user = db.scalar(
        select(User).where(
            User.reset_password_token == token,
            User.reset_password_expires_at.is_not(None),
            User.reset_password_expires_at > datetime.now(UTC),
        )
    )
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    user.password_hash = hash_password(payload.password)
    user.reset_password_token = None
    user.reset_password_expires_at = None
    db.add(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/resend-verify-email/", status_code=status.HTTP_204_NO_CONTENT)
def resend_verify_email(payload: RequestEmailVerificationRequest, db: Session = Depends(get_db)) -> Response:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user:
        user.email_verification_token = secrets.token_urlsafe(48)
        db.add(user)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/verify-email/{token}/", response_model=TokenResponse)
def verify_email(token: str, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email_verification_token == token))
    if not user:
        raise HTTPException(status_code=404, detail="Invalid verification token")
    user.email_verified = True
    user.email_verification_token = None
    db.add(user)
    db.commit()
    return issue_tokens(user.uuid)


@router.get("/profile/", response_model=ProfileResponse)
def profile(current_user: User = Depends(get_current_user)) -> ProfileResponse:
    return ProfileResponse(**current_user.__dict__)


@router.patch("/profile/", response_model=ProfileResponse)
def update_profile(
    payload: ProfilePatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    if payload.first_name is not None:
        current_user.first_name = payload.first_name
    if payload.last_name is not None:
        current_user.last_name = payload.last_name
    if payload.password is not None:
        current_user.password_hash = hash_password(payload.password)
    if payload.privacy_confirmed:
        current_user.privacy_confirmed_at = datetime.now(UTC)
    if payload.terms_confirmed:
        current_user.terms_confirmed_at = datetime.now(UTC)
    if payload.newsletter_confirmed is not None:
        current_user.newsletter_confirmed = payload.newsletter_confirmed
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return ProfileResponse(**current_user.__dict__)


@router.get("/teams/", response_model=list[TeamResponse])
def list_teams(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TeamResponse]:
    rows = db.execute(
        select(Team).join(TeamMember, TeamMember.team_id == Team.uuid).where(TeamMember.user_id == current_user.uuid)
    ).scalars().all()
    return [TeamResponse(uuid=item.uuid, name=item.name, is_default=item.is_default) for item in rows]


@router.post("/teams/", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(payload: TeamCreateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> TeamResponse:
    team = _create_team_for_user(db, current_user, name=payload.name, is_default=False, is_owner=True)
    return TeamResponse(uuid=team.uuid, name=team.name, is_default=team.is_default)


@router.get("/teams/{team_uuid}/", response_model=TeamResponse)
def retrieve_team(team_uuid: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> TeamResponse:
    team = db.scalar(
        select(Team).join(TeamMember, TeamMember.team_id == Team.uuid).where(Team.uuid == team_uuid, TeamMember.user_id == current_user.uuid)
    )
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return TeamResponse(uuid=team.uuid, name=team.name, is_default=team.is_default)


@router.get("/teams/current/", response_model=TeamResponse)
def get_current_team_route(team: Team = Depends(get_current_team)) -> TeamResponse:
    return TeamResponse(uuid=team.uuid, name=team.name, is_default=team.is_default)


@router.patch("/teams/current/", response_model=TeamResponse)
def update_current_team(payload: TeamCreateRequest, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> TeamResponse:
    team.name = payload.name
    db.add(team)
    db.commit()
    db.refresh(team)
    return TeamResponse(uuid=team.uuid, name=team.name, is_default=team.is_default)


@router.post("/teams/current/invite", status_code=status.HTTP_200_OK)
def invite_to_current_team(payload: TeamInvitationRequest, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> dict:
    existing_member = db.scalar(
        select(User).join(TeamMember, TeamMember.user_id == User.uuid).where(TeamMember.team_id == team.uuid, User.email == payload.email.lower())
    )
    if existing_member:
        raise HTTPException(status_code=400, detail="User is already a member of the team")

    invitation = db.scalar(select(TeamInvitation).where(TeamInvitation.team_id == team.uuid, TeamInvitation.email == payload.email.lower()))
    if invitation:
        invitation.activated = False
        invitation.invitation_token = secrets.token_urlsafe(32)
    else:
        invitation = TeamInvitation(
            uuid=uuid4(),
            team_id=team.uuid,
            email=payload.email.lower(),
            activated=False,
            invitation_token=secrets.token_urlsafe(32),
        )
    db.add(invitation)
    db.commit()
    return {"invited": True}


@router.get("/teams/current/invitations", response_model=list[TeamInvitationResponse])
def current_team_invitations(team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> list[TeamInvitationResponse]:
    rows = db.execute(
        select(TeamInvitation).where(TeamInvitation.team_id == team.uuid, TeamInvitation.activated.is_(False)).order_by(TeamInvitation.created_at.desc())
    ).scalars().all()
    return [
        TeamInvitationResponse(uuid=item.uuid, email=item.email, created_at=item.created_at)
        for item in rows
    ]


@router.get("/profile/invitations/", response_model=list[TeamInvitationResponse])
def my_invitations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TeamInvitationResponse]:
    rows = db.execute(
        select(TeamInvitation).where(TeamInvitation.email == current_user.email, TeamInvitation.activated.is_(False)).order_by(TeamInvitation.created_at.desc())
    ).scalars().all()
    return [TeamInvitationResponse(uuid=item.uuid, email=item.email, created_at=item.created_at) for item in rows]


@router.post("/profile/invitations/{invitation_uuid}/accept", status_code=status.HTTP_204_NO_CONTENT)
def accept_my_invitation(
    invitation_uuid: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    invitation = db.scalar(
        select(TeamInvitation).where(
            TeamInvitation.uuid == invitation_uuid,
            TeamInvitation.email == current_user.email,
            TeamInvitation.activated.is_(False),
        )
    )
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation.activated = True
    invitation.invitation_token = None
    db.add(invitation)
    exists = db.scalar(
        select(TeamMember).where(TeamMember.team_id == invitation.team_id, TeamMember.user_id == current_user.uuid)
    )
    if not exists:
        db.add(TeamMember(uuid=uuid4(), team_id=invitation.team_id, user_id=current_user.uuid, is_owner=False))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api-keys/", response_model=list[APIKeyResponse])
def list_api_keys(team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> list[APIKeyResponse]:
    rows = db.execute(select(TeamAPIKey).where(TeamAPIKey.team_id == team.uuid).order_by(TeamAPIKey.created_at.desc())).scalars().all()
    return [
        APIKeyResponse(
            uuid=item.uuid,
            name=item.name,
            key=item.key,
            created_at=item.created_at,
            last_used_at=item.last_used_at,
        )
        for item in rows
    ]


@router.post("/api-keys/", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(payload: APIKeyCreateRequest, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> APIKeyResponse:
    item = TeamAPIKey(
        uuid=uuid4(),
        name=payload.name,
        team_id=team.uuid,
        key=f"wc_{secrets.token_urlsafe(32)}",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return APIKeyResponse(
        uuid=item.uuid,
        name=item.name,
        key=item.key,
        created_at=item.created_at,
        last_used_at=item.last_used_at,
    )


@router.delete("/api-keys/{api_key_uuid}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_key(api_key_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> Response:
    api_key = db.scalar(select(TeamAPIKey).where(TeamAPIKey.uuid == api_key_uuid, TeamAPIKey.team_id == team.uuid))
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    db.delete(api_key)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/teams/current/members/", response_model=list[TeamMemberResponse])
def list_team_members(team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> list[TeamMemberResponse]:
    rows = db.execute(select(TeamMember).where(TeamMember.team_id == team.uuid).order_by(TeamMember.created_at.asc())).scalars().all()
    result: list[TeamMemberResponse] = []
    for item in rows:
        user = db.get(User, item.user_id)
        if not user:
            continue
        result.append(
            TeamMemberResponse(
                uuid=item.uuid,
                is_owner=item.is_owner,
                user=TeamMemberUserResponse(
                    uuid=user.uuid,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    email_verified=user.email_verified,
                ),
            )
        )
    return result


@router.delete("/teams/current/members/{member_uuid}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_member(member_uuid: UUID, team: Team = Depends(get_current_team), db: Session = Depends(get_db)) -> Response:
    member = db.scalar(select(TeamMember).where(TeamMember.uuid == member_uuid, TeamMember.team_id == team.uuid))
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.is_owner:
        raise HTTPException(status_code=403, detail="You can not delete the owner of the team")
    db.execute(delete(TeamMember).where(TeamMember.uuid == member.uuid))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/forgot-password/", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> Response:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user:
        user.reset_password_token = secrets.token_urlsafe(48)
        user.reset_password_expires_at = datetime.now(UTC) + timedelta(hours=1)
        db.add(user)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
