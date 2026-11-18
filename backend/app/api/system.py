from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update, func, text
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DatabaseSession, SystemAdmin
from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_tenant import UserTenant
from app.models.session import UserSession
from app.models.user import UserRole
from app.core.security import hash_password


router = APIRouter(
    prefix="/api/system",
    tags=["Systemverwaltung"],
)


class TenantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    tenant_type: str = Field(pattern="^(unternehmen|vermieter)$")


def serialize_tenant(tenant: Tenant):
    return {
        "id": tenant.id,
        "code": tenant.code,
        "name": tenant.name,
        "tenant_type": tenant.tenant_type,
        "is_active": tenant.is_active,
    }


@router.get("/tenants")
def list_tenants(
    db: DatabaseSession,
    user: SystemAdmin,
):
    tenants = db.scalars(
        select(Tenant).order_by(Tenant.id)
    ).all()

    return [serialize_tenant(tenant) for tenant in tenants]


@router.post("/tenants", status_code=201)
def create_tenant(
    data: TenantCreate,
    db: DatabaseSession,
    user: SystemAdmin,
):
    code = data.code.strip()
    name = data.name.strip()

    if not code or not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mandantencode und Name duerfen nicht leer sein.",
        )

    tenant = Tenant(
        code=code,
        name=name,
        tenant_type=data.tenant_type,
        is_active=True,
    )

    db.add(tenant)

    try:
        db.flush()

        # Eigene Grundkonfiguration fuer den neuen Mandanten.
        # Keine Uebernahme von Bestandsdaten oder Zugangsdaten.
        db.execute(
            text("""
                INSERT INTO company_settings
                    (tenant_id, settings)
                VALUES
                    (:tenant_id, CAST(:settings AS jsonb))
            """),
            {
                "tenant_id": tenant.id,
                "settings": "{}",
            },
        )

        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mandantencode oder Mandantenkonfiguration bereits vorhanden.",
        )

    db.refresh(tenant)

    return serialize_tenant(tenant)




class TenantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


@router.patch("/tenants/{tenant_id}")
def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    db: DatabaseSession,
    admin: SystemAdmin,
):
    tenant = db.get(Tenant, tenant_id)

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mandant nicht gefunden.",
        )

    changes = data.model_fields_set

    if "code" in changes:
        if data.code is None or not data.code.strip():
            raise HTTPException(status_code=422, detail="Mandantencode ungueltig.")
        tenant.code = data.code.strip()

    if "name" in changes:
        if data.name is None or not data.name.strip():
            raise HTTPException(status_code=422, detail="Mandantenname ungueltig.")
        tenant.name = data.name.strip()

    if "is_active" in changes:
        if data.is_active is None:
            raise HTTPException(status_code=422, detail="Aktivierungsstatus ungueltig.")
        tenant.is_active = data.is_active

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mandantencode bereits vorhanden.",
        )

    db.refresh(tenant)
    return serialize_tenant(tenant)


# BUHA V1.2.0: Benutzerverwaltung
def serialize_system_user(db, user: User):
    memberships = db.execute(
        select(UserTenant, Tenant)
        .join(Tenant, Tenant.id == UserTenant.tenant_id)
        .where(UserTenant.user_id == user.id)
        .order_by(Tenant.name)
    ).all()

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
        "tenants": [
            {
                "tenant_id": tenant.id,
                "tenant_code": tenant.code,
                "tenant_name": tenant.name,
                "tenant_type": tenant.tenant_type,
                "role": membership.role,
            }
            for membership, tenant in memberships
        ],
    }


@router.get("/users")
def list_users(
    db: DatabaseSession,
    admin: SystemAdmin,
):
    users = db.scalars(
        select(User).order_by(User.id)
    ).all()

    return [serialize_system_user(db, user) for user in users]


@router.get("/users/{user_id}")
def get_user(
    user_id: int,
    db: DatabaseSession,
    admin: SystemAdmin,
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Benutzer nicht gefunden.",
        )

    return serialize_system_user(db, user)



class UserTenantAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: int = Field(gt=0)
    role: str = Field(pattern="^(admin|user)$")


class SystemUserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=1024)
    tenants: list[UserTenantAssignment] = Field(min_length=1)


@router.post("/users", status_code=201)
def create_system_user(
    data: SystemUserCreate,
    db: DatabaseSession,
    admin: SystemAdmin,
):
    username = data.username.strip().lower()
    email = data.email.strip().lower()

    if not username or not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Benutzername oder E-Mail-Adresse ungueltig.",
        )

    tenant_ids = [assignment.tenant_id for assignment in data.tenants]

    if len(tenant_ids) != len(set(tenant_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Doppelte Mandantenzuordnung.",
        )

    tenants = db.scalars(
        select(Tenant).where(
            Tenant.id.in_(tenant_ids),
            Tenant.is_active.is_(True),
        )
    ).all()

    if len(tenants) != len(tenant_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mindestens ein Mandant existiert nicht oder ist deaktiviert.",
        )

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(data.password),
        role=UserRole.USER,
        is_active=True,
    )

    db.add(user)

    try:
        db.flush()

        for assignment in data.tenants:
            db.add(
                UserTenant(
                    user_id=user.id,
                    tenant_id=assignment.tenant_id,
                    role=assignment.role,
                )
            )

        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Benutzername, E-Mail-Adresse oder Zuordnung bereits vorhanden.",
        )

    db.refresh(user)

    return serialize_system_user(db, user)



class SystemUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    is_active: bool | None = None
    tenants: list[UserTenantAssignment] | None = None


@router.patch("/users/{user_id}")
def update_system_user(
    user_id: int,
    data: SystemUserUpdate,
    db: DatabaseSession,
    admin: SystemAdmin,
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Benutzer nicht gefunden.",
        )

    if user.role == UserRole.SYSTEM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Systemadministratoren koennen hier nicht bearbeitet werden.",
        )

    changes = data.model_fields_set

    if "username" in changes:
        if data.username is None or not data.username.strip():
            raise HTTPException(status_code=422, detail="Benutzername ungueltig.")
        user.username = data.username.strip().lower()

    if "email" in changes:
        if data.email is None or "@" not in data.email.strip():
            raise HTTPException(status_code=422, detail="E-Mail-Adresse ungueltig.")
        user.email = data.email.strip().lower()

    if "is_active" in changes:
        if data.is_active is None:
            raise HTTPException(status_code=422, detail="Aktivierungsstatus ungueltig.")
        user.is_active = data.is_active

    if "tenants" in changes:
        if data.tenants is None:
            raise HTTPException(status_code=422, detail="Mandantenzuordnungen ungueltig.")

        tenant_ids = [item.tenant_id for item in data.tenants]

        if len(tenant_ids) != len(set(tenant_ids)):
            raise HTTPException(status_code=422, detail="Doppelte Mandantenzuordnung.")

        if tenant_ids:
            valid_tenants = db.scalars(
                select(Tenant).where(
                    Tenant.id.in_(tenant_ids),
                    Tenant.is_active.is_(True),
                )
            ).all()

            if len(valid_tenants) != len(tenant_ids):
                raise HTTPException(
                    status_code=422,
                    detail="Mindestens ein Mandant ist ungueltig oder deaktiviert.",
                )

        existing = db.scalars(
            select(UserTenant).where(UserTenant.user_id == user.id)
        ).all()

        for membership in existing:
            db.delete(membership)

        db.flush()

        for item in data.tenants:
            db.add(
                UserTenant(
                    user_id=user.id,
                    tenant_id=item.tenant_id,
                    role=item.role,
                )
            )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Benutzername, E-Mail-Adresse oder Zuordnung bereits vorhanden.",
        )

    db.refresh(user)
    return serialize_system_user(db, user)



class SystemUserPasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=12, max_length=1024)


@router.patch("/users/{user_id}/password")
def reset_system_user_password(
    user_id: int,
    data: SystemUserPasswordReset,
    db: DatabaseSession,
    admin: SystemAdmin,
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Benutzer nicht gefunden.",
        )

    if user.role == UserRole.SYSTEM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Passwort eines Systemadministrators kann hier nicht geaendert werden.",
        )

    user.password_hash = hash_password(data.password)

    # Alle bisherigen Sitzungen dieses Benutzers widerrufen.
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id)
        .values(revoked_at=func.now())
    )

    db.commit()

    return {
        "message": "Passwort erfolgreich aktualisiert.",
        "user_id": user.id,
    }
