import uuid

import pytest

from app.api.v1.task_attachments import (
    build_content_disposition,
)
from app.core.config import settings
from app.storage.factory import get_storage
from app.storage.local import LocalStorage

def assert_status(response, expected):
    if response.status_code != expected:
        print("\nSTATUS:", response.status_code)
        print("BODY:", response.text)

    assert response.status_code == expected


def create_test_organization(client, headers):
    unique = uuid.uuid4().hex[:8]

    response = client.post(
        "/api/v1/organizations/",
        json={
            "name": f"Org {unique}",
            "slug": f"org-{unique}",
            "description": "Testing organization",
        },
        headers=headers,
    )

    assert_status(response, 201)

    return response.json()


def create_test_project(client, headers, organization_id):
    unique = uuid.uuid4().hex[:8]

    response = client.post(
        f"/api/v1/organizations/{organization_id}/projects",
        json={
            "name": f"Project {unique}",
            "slug": f"project-{unique}",
        },
        headers=headers,
    )

    assert_status(response, 201)

    return response.json()


def add_project_member(
    client,
    headers,
    organization_id,
    project_id,
    user_id,
):
    response = client.post(
        (
            f"/api/v1/organizations/"
            f"{organization_id}/projects/"
            f"{project_id}/members"
        ),
        json={
            "user_id": str(user_id),
            "role": "owner",
        },
        headers=headers,
    )

    assert_status(response, 201)


def create_test_task(
    client,
    headers,
    organization_id,
    project_id,
    title="Test Task",
):
    response = client.post(
        (
            f"/api/v1/organizations/"
            f"{organization_id}/projects/"
            f"{project_id}/tasks"
        ),
        json={
            "title": title,
        },
        headers=headers,
    )

    assert_status(response, 201)

    return response.json()


def create_attachment(
    client,
    headers,
    organization_id,
    project_id,
    task_id,
):
    content = b"%PDF-1.7\nTest attachment content"

    response = client.post(
        (
            f"/api/v1/organizations/"
            f"{organization_id}/projects/"
            f"{project_id}/tasks/"
            f"{task_id}/attachments"
        ),
        files={
            "file": (
                "test.pdf",
                content,
                "application/pdf",
            )
        },
        headers=headers,
    )

    assert_status(response, 201)

    attachment = response.json()

    return attachment, content

def setup_task(
    client,
    admin_headers,
    admin_user_id,
):
    organization = create_test_organization(
        client,
        admin_headers,
    )

    project = create_test_project(
        client,
        admin_headers,
        organization["id"],
    )

    task = create_test_task(
        client,
        admin_headers,
        organization["id"],
        project["id"],
    )

    return organization, project, task


def test_create_task_attachment(
    client,
    admin_headers,
    admin_user_id,
):

    organization, project, task = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    attachment, content = create_attachment(
        client,
        admin_headers,
        organization["id"],
        project["id"],
        task["id"],
    )

    assert attachment["file_name"] == "test.pdf"
    assert attachment["task_id"] == task["id"]
    assert attachment["file_type"] == "application/pdf"
    assert attachment["file_size"] == len(content)

    storage = get_storage()

    assert storage.exists(
        attachment["file_path"]
    )

    with storage.open(
        attachment["file_path"]
    ) as stored_file:
        assert stored_file.read() == content


def test_list_task_attachments(
    client,
    admin_headers,
    admin_user_id,
):

    organization, project, task = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    attachment, _ = create_attachment(
        client,
        admin_headers,
        organization["id"],
        project["id"],
        task["id"],
    )

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments"
        ),
        headers=admin_headers,
    )

    assert_status(response, 200)

    data = response.json()

    assert data["total"] == 1
    assert data["attachments"][0]["id"] == attachment["id"]


def test_get_task_attachment(
    client,
    admin_headers,
    admin_user_id,
):

    organization, project, task = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    attachment, _ = create_attachment(
        client,
        admin_headers,
        organization["id"],
        project["id"],
        task["id"],
    )

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments/"
            f"{attachment['id']}"
        ),
        headers=admin_headers,
    )

    assert_status(response, 200)

    assert response.json()["id"] == attachment["id"]


def test_delete_task_attachment(
    client,
    admin_headers,
    admin_user_id,
):

    organization, project, task = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    attachment, _ = create_attachment(
        client,
        admin_headers,
        organization["id"],
        project["id"],
        task["id"],
    )

    storage = get_storage()

    assert storage.exists(
        attachment["file_path"]
    )

    response = client.delete(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments/"
            f"{attachment['id']}"
        ),
        headers=admin_headers,
    )

    assert_status(response, 200)

    assert not storage.exists(
        attachment["file_path"]
    )

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments/"
            f"{attachment['id']}"
        ),
        headers=admin_headers,
    )

    assert_status(response, 404)


def test_delete_task_attachment_storage_failure(
    client,
    admin_headers,
    admin_user_id,
    monkeypatch,
):

    organization, project, task = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    attachment, _ = create_attachment(
        client,
        admin_headers,
        organization["id"],
        project["id"],
        task["id"],
    )

    storage = get_storage()

    assert storage.exists(
        attachment["file_path"]
    )

    def fail_delete(self, key):
        raise OSError(
            "Simulated storage failure"
        )

    monkeypatch.setattr(
        LocalStorage,
        "delete",
        fail_delete,
    )

    with pytest.raises(
        OSError,
        match="Simulated storage failure",
    ):
        client.delete(
            (
                f"/api/v1/organizations/"
                f"{organization['id']}/projects/"
                f"{project['id']}/tasks/"
                f"{task['id']}/attachments/"
                f"{attachment['id']}"
            ),
            headers=admin_headers,
        )

    assert storage.exists(
        attachment["file_path"]
    )

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments/"
            f"{attachment['id']}"
        ),
        headers=admin_headers,
    )

    assert_status(response, 200)

    assert response.json()["id"] == attachment["id"]

def test_download_task_attachment(
    client,
    admin_headers,
    admin_user_id,
):

    organization, project, task = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    attachment, content = create_attachment(
        client,
        admin_headers,
        organization["id"],
        project["id"],
        task["id"],
    )

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments/"
            f"{attachment['id']}/download"
        ),
        headers=admin_headers,
    )

    assert_status(response, 200)

    assert response.content == content

    assert response.headers["content-type"] == (
        "application/pdf"
    )

    assert response.headers["content-disposition"] == (
        'attachment; filename="test.pdf"; '
        "filename*=UTF-8''test.pdf"
    )

def test_download_attachment_through_another_task(
    client,
    admin_headers,
    admin_user_id,
):

    organization, project, task_one = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    task_two = create_test_task(
        client,
        admin_headers,
        organization["id"],
        project["id"],
        title="Second Task",
    )

    attachment, _ = create_attachment(
        client,
        admin_headers,
        organization["id"],
        project["id"],
        task_one["id"],
    )

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task_two['id']}/attachments/"
            f"{attachment['id']}/download"
        ),
        headers=admin_headers,
    )

    assert_status(response, 404)

    assert response.json()["message"] == (
        "Attachment not found"
    )

def test_download_missing_stored_attachment(
    client,
    admin_headers,
    admin_user_id,
):

    organization, project, task = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    attachment, _ = create_attachment(
        client,
        admin_headers,
        organization["id"],
        project["id"],
        task["id"],
    )

    storage = get_storage()

    storage.delete(
        attachment["file_path"]
    )

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments/"
            f"{attachment['id']}/download"
        ),
        headers=admin_headers,
    )

    assert_status(response, 404)

    assert response.json()["message"] == (
        "Stored attachment not found"
    )

def test_non_member_cannot_upload_attachment(
    client,
    admin_headers,
    admin_user_id,
    db,
):
    """
    A user who belongs to the organization but is not a
    project member cannot upload an attachment.
    """

    organization, project, task = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    # ---------------------------------------------------------
    # Create another user.
    # ---------------------------------------------------------

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": (
                f"attachment{uuid.uuid4().hex[:8]}"
                "@example.com"
            ),
            "username": (
                f"attachment{uuid.uuid4().hex[:8]}"
            ),
            "password": "password123",
            "first_name": "Attachment",
            "last_name": "Tester",
        },
    )

    assert_status(response, 201)

    other_user = response.json()

    # ---------------------------------------------------------
    # Retrieve the user and make the account active/verified.
    # ---------------------------------------------------------

    from app.models.user import User

    other_user_model = (
        db.query(User)
        .filter(
            User.id == other_user["id"]
        )
        .first()
    )

    assert other_user_model is not None

    other_user_model.is_active = True
    other_user_model.is_verified = True

    db.commit()
    db.refresh(other_user_model)

    # ---------------------------------------------------------
    # Give the user only projects.view.
    #
    # This deliberately does NOT grant
    # projects.members.manage.
    # ---------------------------------------------------------

    from app.models.permission import Permission
    from app.models.role import Role

    permission = (
        db.query(Permission)
        .filter(
            Permission.name == "projects.view"
        )
        .first()
    )

    assert permission is not None

    role = Role(
        name=(
            f"Attachment Tester "
            f"{uuid.uuid4().hex[:8]}"
        ),
        description="Attachment authorization test role",
    )

    role.permissions.append(permission)

    db.add(role)
    db.commit()
    db.refresh(role)

    other_user_model.roles.append(role)
    db.commit()
    db.refresh(other_user_model)

    # ---------------------------------------------------------
    # Make the user an organization member.
    #
    # This allows the request to pass organization access
    # before reaching the attachment permission check.
    # ---------------------------------------------------------

    from app.models.organization_member import OrganizationMember

    organization_role = (
        db.query(Role)
        .filter(
            Role.name == "member"
        )
        .first()
    )

    assert organization_role is not None

    organization_member = OrganizationMember(
        organization_id=organization["id"],
        user_id=other_user["id"],
        role_id=organization_role.id,
    )

    db.add(organization_member)
    db.commit()

    # ---------------------------------------------------------
    # Make the user a project member.
    #
    # They can access the project, but still don't have
    # projects.members.manage.
    # ---------------------------------------------------------

    member_response = client.post(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/members"
        ),
        json={
            "user_id": other_user["id"],
            "role": "contributor",
        },
        headers=admin_headers,
    )

    assert_status(member_response, 201)

    # ---------------------------------------------------------
    # Login as the other user.
    # ---------------------------------------------------------

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": other_user["email"],
            "password": "password123",
        },
    )

    assert_status(login_response, 200)

    other_headers = {
        "Authorization": (
            f"Bearer "
            f"{login_response.json()['access_token']}"
        )
    }

    # ---------------------------------------------------------
    # Attempt to upload an attachment.
    # ---------------------------------------------------------

    response = client.post(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments"
        ),
        files={
            "file": (
                "unauthorized.pdf",
                b"Unauthorized attachment",
                "application/pdf",
            )
        },
        headers=other_headers,
    )

    assert_status(response, 403)

    assert response.json()["message"] == (
        "Permission 'projects.members.manage' required"
    )

def test_user_without_view_permission_cannot_download_attachment(
    client,
    admin_headers,
    admin_user_id,
    db,
):
    """
    A project member without projects.view cannot
    download a task attachment.
    """

    organization, project, task = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    attachment, _ = create_attachment(
        client,
        admin_headers,
        organization["id"],
        project["id"],
        task["id"],
    )

    # ---------------------------------------------------------
    # Create another user.
    # ---------------------------------------------------------

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": (
                f"download{uuid.uuid4().hex[:8]}"
                "@example.com"
            ),
            "username": (
                f"download{uuid.uuid4().hex[:8]}"
            ),
            "password": "password123",
            "first_name": "Download",
            "last_name": "Tester",
        },
    )

    assert_status(response, 201)

    other_user = response.json()

    # ---------------------------------------------------------
    # Activate and verify the account.
    # ---------------------------------------------------------

    from app.models.user import User

    other_user_model = (
        db.query(User)
        .filter(
            User.id == other_user["id"]
        )
        .first()
    )

    assert other_user_model is not None

    other_user_model.is_active = True
    other_user_model.is_verified = True

    db.commit()
    db.refresh(other_user_model)

    # ---------------------------------------------------------
    # Give the user a role with no project-view permission.
    # ---------------------------------------------------------

    from app.models.role import Role

    role = Role(
        name=(
            f"Attachment Download Tester "
            f"{uuid.uuid4().hex[:8]}"
        ),
        description="Attachment download authorization test role",
    )

    db.add(role)
    db.commit()
    db.refresh(role)

    other_user_model.roles.append(role)
    db.commit()

    # ---------------------------------------------------------
    # Make the user an organization member.
    # ---------------------------------------------------------

    from app.models.organization_member import (
        OrganizationMember,
    )

    organization_role = (
        db.query(Role)
        .filter(
            Role.name == "member"
        )
        .first()
    )

    assert organization_role is not None

    organization_member = OrganizationMember(
        organization_id=organization["id"],
        user_id=other_user["id"],
        role_id=organization_role.id,
    )

    db.add(organization_member)
    db.commit()

    # ---------------------------------------------------------
    # Make the user a project member.
    # ---------------------------------------------------------

    member_response = client.post(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/members"
        ),
        json={
            "user_id": other_user["id"],
            "role": "contributor",
        },
        headers=admin_headers,
    )

    assert_status(member_response, 201)

    # ---------------------------------------------------------
    # Login as the other user.
    # ---------------------------------------------------------

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": other_user["email"],
            "password": "password123",
        },
    )

    assert_status(login_response, 200)

    other_headers = {
        "Authorization": (
            f"Bearer "
            f"{login_response.json()['access_token']}"
        )
    }

    # ---------------------------------------------------------
    # Attempt to download the attachment.
    # ---------------------------------------------------------

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments/"
            f"{attachment['id']}/download"
        ),
        headers=other_headers,
    )

    assert_status(response, 403)

    assert response.json()["message"] == (
        "Permission 'projects.view' required"
    )

def test_download_attachment_through_another_project(
    client,
    admin_headers,
    admin_user_id,
):
    """
    An attachment belonging to one project must not be
    downloadable through another project.
    """

    organization = create_test_organization(
        client,
        admin_headers,
    )

    project_one = create_test_project(
        client,
        admin_headers,
        organization["id"],
    )

    project_two = create_test_project(
        client,
        admin_headers,
        organization["id"],
    )

    task = create_test_task(
        client,
        admin_headers,
        organization["id"],
        project_one["id"],
    )

    attachment, _ = create_attachment(
        client,
        admin_headers,
        organization["id"],
        project_one["id"],
        task["id"],
    )

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project_two['id']}/tasks/"
            f"{task['id']}/attachments/"
            f"{attachment['id']}/download"
        ),
        headers=admin_headers,
    )

    assert_status(response, 404)

    assert response.json()["message"] == (
        "Task not found"
    )

def test_download_attachment_through_another_organization(
    client,
    admin_headers,
    admin_user_id,
):
    """
    An attachment belonging to one organization must not be
    downloadable through another organization.
    """

    organization_one = create_test_organization(
        client,
        admin_headers,
    )

    organization_two = create_test_organization(
        client,
        admin_headers,
    )

    project = create_test_project(
        client,
        admin_headers,
        organization_one["id"],
    )

    task = create_test_task(
        client,
        admin_headers,
        organization_one["id"],
        project["id"],
    )

    attachment, _ = create_attachment(
        client,
        admin_headers,
        organization_one["id"],
        project["id"],
        task["id"],
    )

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization_two['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments/"
            f"{attachment['id']}/download"
        ),
        headers=admin_headers,
    )

    assert_status(response, 404)

    assert response.json()["message"] == (
        "Project not found"
    )

def test_upload_rejects_file_exceeding_max_size(
    client,
    admin_headers,
    admin_user_id,
    monkeypatch,
):
    """
    An attachment larger than the configured maximum size
    must be rejected without leaving a database record
    or partial stored file.
    """

    organization, project, task = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    monkeypatch.setattr(
        settings,
        "MAX_ATTACHMENT_SIZE",
        10,
    )

    content = b"This file is too large"

    response = client.post(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments"
        ),
        files={
            "file": (
                "large.txt",
                content,
                "text/plain",
            )
        },
        headers=admin_headers,
    )

    assert_status(response, 400)

    assert (
        response.json()["message"]
        == "File exceeds maximum allowed size"
    )

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments"
        ),
        headers=admin_headers,
    )

    assert_status(response, 200)

    assert response.json()["total"] == 0


def test_upload_rejects_unsupported_attachment_type(
    client,
    admin_headers,
    admin_user_id,
):
    """
    An attachment with an unsupported MIME type
    must be rejected before it is stored.
    """

    organization, project, task = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    response = client.post(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments"
        ),
        files={
            "file": (
                "malicious.exe",
                b"not really an executable",
                "application/x-msdownload",
            )
        },
        headers=admin_headers,
    )

    assert_status(response, 400)

    assert response.json()["message"] == (
        "Unsupported attachment type"
    )

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments"
        ),
        headers=admin_headers,
    )

    assert_status(response, 200)

    assert response.json()["total"] == 0

def test_upload_rejects_mismatched_file_extension(
    client,
    admin_headers,
    admin_user_id,
):
    """
    An attachment whose filename extension does not match
    its declared MIME type must be rejected.
    """

    organization, project, task = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    response = client.post(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments"
        ),
        files={
            "file": (
                "malicious.exe",
                b"fake pdf content",
                "application/pdf",
            )
        },
        headers=admin_headers,
    )

    assert_status(response, 400)

    assert response.json()["message"] == (
        "File extension does not match attachment type"
    )

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments"
        ),
        headers=admin_headers,
    )

    assert_status(response, 200)

    assert response.json()["total"] == 0

def test_content_disposition_handles_quotes():
    header = build_content_disposition(
        'report "final".pdf'
    )

    assert "\r" not in header
    assert "\n" not in header
    assert 'filename="report _final_.pdf"' in header
    assert "filename*=" in header


def test_content_disposition_removes_control_characters():
    header = build_content_disposition(
        "report\r\nX-Injected-Header: true.pdf"
    )

    assert "\r" not in header
    assert "\n" not in header
    assert "X-Injected-Header" not in header


def test_content_disposition_supports_unicode_filename():
    header = build_content_disposition(
        "Résumé 2026.pdf"
    )

    assert "\r" not in header
    assert "\n" not in header
    assert "filename*=" in header
    assert "R%C3%A9sum%C3%A9%202026.pdf" in header


def test_content_disposition_handles_empty_filename():
    header = build_content_disposition("")

    assert header == (
        'attachment; filename="download"; '
        "filename*=UTF-8''download"
    )

def test_download_task_attachment_preserves_unicode_filename(
    client,
    admin_headers,
    admin_user_id,
):
    organization, project, task = setup_task(
        client,
        admin_headers,
        admin_user_id,
    )

    filename = "Résumé 2026.pdf"
    content = b"%PDF-test-content"

    response = client.post(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments"
        ),
        files={
            "file": (
                filename,
                content,
                "application/pdf",
            )
        },
        headers=admin_headers,
    )

    assert_status(response, 201)

    attachment = response.json()

    response = client.get(
        (
            f"/api/v1/organizations/"
            f"{organization['id']}/projects/"
            f"{project['id']}/tasks/"
            f"{task['id']}/attachments/"
            f"{attachment['id']}/download"
        ),
        headers=admin_headers,
    )

    assert_status(response, 200)

    assert response.content == content

    content_disposition = response.headers[
        "content-disposition"
    ]

    assert "filename*=UTF-8''" in content_disposition
    assert "R%C3%A9sum%C3%A9%202026.pdf" in (
        content_disposition
    )
