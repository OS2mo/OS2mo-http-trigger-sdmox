# SPDX-FileCopyrightText: Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Path, Query, Request
from os2mo_helpers.mora_helpers import MoraHelper

from app.dependencies import _verify_ou_ok, get_date
from app.models import (MOTriggerPayload, MOTriggerPayloadAddressCreate,
                        MOTriggerPayloadAddressEdit, MOTriggerPayloadOUCreate,
                        MOTriggerPayloadOUEdit, MOTriggerRegister, RequestType, EventType)
from app.util import get_mora_helper_default

router = APIRouter()


def verify_ou_ok_trigger(
    payload: MOTriggerPayload,
    mora_helper: MoraHelper = Depends(get_mora_helper_default),
):
    uuid = payload.uuid
    data = payload.request["data"]

    at = data["validity"]["from"]
    _verify_ou_ok(uuid, at, mora_helper)


verify_ou_ok_trigger.responses = _verify_ou_ok.responses


@router.get(
    "/",
    summary="List triggers to be registered.",
    response_model=List[MOTriggerRegister],
    response_description=(
        "Successful Response" + "<br/>" + "List of triggers to register."
    ),
)
def triggers(request: Request) -> List[MOTriggerRegister]:
    """List triggers to be registered."""
    # All our triggers are ON_BEFORE
    triggers = [
        (RequestType.CREATE, "org_unit"),
        (RequestType.EDIT, "org_unit"),
        (RequestType.CREATE, "address"),
        (RequestType.EDIT, "address"),
    ]
    return [
        MOTriggerRegister(
            event_type=EventType.ON_BEFORE,
            request_type=request_type,
            role_type=role_type,
            url="triggers/" + str(role_type) + "/" + str(request_type.value),
        )
        for request_type, role_type in triggers
    ]


@router.post(
    "/org_unit/" + str(RequestType.CREATE.value),
    summary="Create an organizational unit.",
)
async def triggers_ou_create(
    payload: MOTriggerPayloadOUCreate,
    dry_run: Optional[bool] = Query(False, description="Dry run the operation."),
    mora_helper=Depends(get_mora_helper_default),
):
    """Create an organizational unit."""
    print("/triggers/ou/create called")
    print(payload.json(indent=4))

    # We will never create a top level organization unit with SDMox.
    # Thus we cannot accept requests with no parent set, or the parent set to the
    # root organization.
    parent_uuid = payload.request.get("parent", {}).get("uuid")
    o_uuid = mora_helper.read_organisation()
    if not parent_uuid or parent_uuid == o_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create an organizational unit at top-level.",
        )

    # We will never create an organization under a non-triggered uuid.
    at = datetime.strptime(payload.request["validity"]["from"], "%Y-%m-%d").date()
    _verify_ou_ok(parent_uuid, at, mora_helper)

    # Preconditions have been checked, time to try to create the organizational unit
    uuid = str(payload.uuid)
    unit_data = payload.request
    parent_data = mora_helper.read_ou(parent_uuid, at=at)
    mox: SDMoxInterface = SDMox(from_date=at)
    await mox.create_unit(uuid, unit_data, parent_data, dry_run=dry_run)

    return {"status": "OK"}


@router.post(
    "/org_unit/" + str(RequestType.EDIT.value),
    responses=verify_ou_ok_trigger.responses,
    dependencies=[Depends(verify_ou_ok_trigger)],
    summary="Rename or move an organizational unit.",
)
async def triggers_ou_edit(
    payload: MOTriggerPayloadOUEdit,
    dry_run: Optional[bool] = Query(False, description="Dry run the operation."),
):
    """Rename or move an organizational unit."""
    print("/triggers/ou/edit called")
    print(payload.json(indent=4))

    uuid = str(payload.uuid)
    data = payload.request["data"]

    at = datetime.strptime(data["validity"]["from"], "%Y-%m-%d").date()

    if "name" in data:
        new_name = data["name"]
        await _ou_edit_name(uuid, new_name, at, dry_run=dry_run)

    if "parent" in data:
        new_parent_obj = data["parent"]
        new_parent_uuid = new_parent_obj["uuid"]
        await _ou_edit_parent(uuid, new_parent_uuid, at, dry_run=dry_run)
    return {"status": "OK"}


@router.post(
    "/address/" + str(RequestType.CREATE.value),
    summary="Create an addresses.",
)
async def triggers_address_create(
    payload: MOTriggerPayloadAddressCreate,
    dry_run: Optional[bool] = Query(False, description="Dry run the operation."),
    mora_helper=Depends(get_mora_helper_default),
):
    """Create an addresses."""
    print("/triggers/address/create called")
    print(payload.json(indent=4))

    unit_uuid = payload.request.get("org_unit", {}).get("uuid")
    if not unit_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing organization unit UUID when adding address.",
        )
    # We will never create an addresses for units outside non-triggered uuid.
    # TODO: Consider whether we should block inserts in these cases, probably not
    at = datetime.strptime(payload.request["validity"]["from"], "%Y-%m-%d").date()
    _verify_ou_ok(unit_uuid, at, mora_helper)

    # Preconditions have been checked, time to try to create the organizational unit
    address_uuid = str(payload.uuid)
    address_data = payload.request
    mox: SDMoxInterface = SDMox(from_date=at)
    await mox.create_address(unit_uuid, address_uuid, address_data, at, dry_run=dry_run)

    return {"status": "OK"}


@router.post(
    "/address/" + str(RequestType.EDIT.value),
    summary="Edit an address.",
)
async def triggers_address_edit(
    payload: MOTriggerPayloadAddressEdit,
    dry_run: Optional[bool] = Query(False, description="Dry run the operation."),
    mora_helper=Depends(get_mora_helper_default),
):
    """Edit an address."""
    print("/triggers/address/edit called")
    print(payload.json(indent=4))

    unit_uuid = payload.request.get("org_unit", {}).get("uuid")
    if not unit_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing organization unit UUID when adding address.",
        )
    # We will never create an addresses for units outside non-triggered uuid.
    # TODO: Consider whether we should block inserts in these cases, probably not
    at = datetime.strptime(
        payload.request["data"]["validity"]["from"], "%Y-%m-%d"
    ).date()
    _verify_ou_ok(unit_uuid, at, mora_helper)

    # Preconditions have been checked, time to try to create the organizational unit
    address_uuid = str(payload.uuid)
    address_data = payload.request["data"]
    mox: SDMoxInterface = SDMox(from_date=at)
    await mox.create_address(unit_uuid, address_uuid, address_data, at, dry_run=dry_run)

    return {"status": "OK"}
