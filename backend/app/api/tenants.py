from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DatabaseSession
from app.services.tenant_access import get_accessible_tenants


router = APIRouter(
    prefix="/api/tenants",
    tags=["Mandanten"],
)


@router.get("/my")
def my_tenants(
    user: CurrentUser,
    db: DatabaseSession,
):
    memberships = get_accessible_tenants(db, user)

    return [
        {
            "id": tenant.id,
            "code": tenant.code,
            "name": tenant.name,
            "tenant_type": tenant.tenant_type,
            "role": role,
        }
        for tenant, role in memberships
    ]
