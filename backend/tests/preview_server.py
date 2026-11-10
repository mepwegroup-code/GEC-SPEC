"""TEST-ONLY FastAPI sandbox site with an in-memory Supabase stand-in.
Do not deploy as production! Main API endpoints are real; Supabase side effects are mocked.
"""
import uuid
from pathlib import Path
from fastapi import File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from tests.test_e2e_20_cycles import MockDB, UID
import app.main as main

store = MockDB()
main.db = lambda: store
main.app.dependency_overrides[main.user_id] = lambda: UID
app = main.app

@app.get('/sandbox', response_class=HTMLResponse, include_in_schema=False)
def sandbox():
    return Path(__file__).with_name('sandbox_preview.html').read_text(encoding='utf-8')

@app.post('/sandbox/upload/{project_id}', include_in_schema=False)
async def sandbox_upload(project_id: str, file: UploadFile = File(...)):
    main.project_owned(project_id,UID)
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(422,'Only PDF files are supported')
    content = await file.read(main.MAX_FILE_BYTES + 1)
    if len(content) > main.MAX_FILE_BYTES:
        raise HTTPException(413,'File too big')
    path=f'{UID}/{project_id}/pdf/{uuid.uuid4().hex}.pdf'
    store.storage.objects[path]=content
    return {'path':path}
