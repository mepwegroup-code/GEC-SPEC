from fastapi.testclient import TestClient
from app.main import app, file_owned
from fastapi import HTTPException
from app.models import FIELDS

def test_health():
    result = TestClient(app).get('/health')
    assert result.status_code == 200
    assert result.json()['status'] == 'ok'

def test_auth_required():
    assert TestClient(app).get('/projects').status_code == 401

def test_reject_foreign_storage_path():
    try:
        file_owned('project-a','user-a','user-b/project-a/catalogue.pdf')
        assert False
    except HTTPException as ex:
        assert ex.status_code == 403

def test_fields():
    assert {'code','model','power','flux','cct','beam','ip','ik'}.issubset(FIELDS)
