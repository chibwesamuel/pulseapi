import uuid

import pytest

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
    content = b"Test attachment content"

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
        'attachment; filename="test.pdf"'
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
