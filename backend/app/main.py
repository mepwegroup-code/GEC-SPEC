"""GEC Specifications API. All resource actions require a valid Supabase user token."""
import json
import os
import re
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from .models import FIELDS
from .pdf_parser import parse_pdf
from .excel_handler import export_schedule, import_schedule
from .pptx_generator import export_pptx

SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
STORAGE_BUCKET = 'project-files'
MAX_FILE_BYTES = 35 * 1024 * 1024
app = FastAPI(title='GEC Lighting Specifications API', version='0.3.0')
origins = [o.strip() for o in os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',') if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=['GET','POST','PATCH','DELETE'], allow_headers=['Authorization','Content-Type'])


def db():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(503, 'Supabase backend credentials are not configured')
    try:
        from supabase import create_client
    except ImportError:
        raise HTTPException(503, "Supabase Python client is not installed")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def user_id(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Missing bearer token')
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(401, 'Missing token')
    try:
        account = db().auth.get_user(token).user
        if not account or not account.id:
            raise ValueError('No authenticated user')
        return str(account.id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, 'Invalid or expired token')


def project_owned(project_id: str, uid: str):
    try:
        uuid.UUID(project_id)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, 'Invalid project ID')
    rows = db().table('projects').select('*').eq('id', project_id).eq('owner_id', uid).limit(1).execute().data
    if not rows:
        raise HTTPException(404, 'Project not found or access denied')
    return rows[0]


def file_owned(project_id: str, uid: str, path: str):
    # Accept only predictable, normalized Supabase Storage keys. No traversal or separators.
    if not path or '\\' in path or '%' in path or any(ord(ch) < 32 for ch in path):
        raise HTTPException(403, 'Invalid storage path')
    parts = PurePosixPath(path).parts
    if len(parts) < 4 or parts[:2] != (uid, project_id) or any(part in ('.', '..', '') for part in path.split('/')):
        raise HTTPException(403, 'Storage path does not belong to project')
    return path


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)


class RecordUpdate(BaseModel):
    fields: dict[str, str]


class StorageRequest(BaseModel):
    path: str = Field(min_length=5)
    code: str = Field(default='', max_length=100)


class ScheduleImportRequest(BaseModel):
    path: str = Field(min_length=5)
    sheet: Optional[str] = None
    header_row: int = Field(default=1, ge=1, le=1000)
    excel_mapping: Optional[dict[str, str]] = None


class ExportRequest(BaseModel):
    record_ids: list[str] = Field(min_length=1, max_length=300)
    template_path: Optional[str] = None
    excel_sheet: Optional[str] = None
    excel_start_row: int = Field(default=2, ge=1)
    excel_mapping: Optional[dict[str,str]] = None


@app.get('/health')
def health():
    return {'status': 'ok', 'version': app.version}


@app.get('/projects')
def list_projects(uid: str = Depends(user_id)):
    return db().table('projects').select('*').eq('owner_id', uid).order('created_at', desc=True).execute().data


@app.post('/projects', status_code=201)
def create_project(body: ProjectCreate, uid: str = Depends(user_id)):
    return db().table('projects').insert({'name': body.name.strip(), 'owner_id':uid}).execute().data[0]


@app.get('/projects/{project_id}/records')
def list_records(project_id: str, uid: str = Depends(user_id)):
    project_owned(project_id, uid)
    return db().table('luminaires').select('*').eq('project_id',project_id).order('created_at').execute().data


def storage_bytes(path: str) -> bytes:
    result = db().storage.from_(STORAGE_BUCKET).download(path)
    if not isinstance(result, bytes):
        raise HTTPException(502, 'Storage returned invalid content')
    if len(result) > MAX_FILE_BYTES:
        raise HTTPException(413, 'File exceeds backend processing limit (35 MB)')
    return result


def check_mapping(mapping: Optional[dict[str,str]]):
    if mapping:
        if len(set(mapping.values())) != len(mapping):
            raise HTTPException(422, 'Duplicate Excel target columns')
        for field,col in mapping.items():
            if field not in FIELDS or not re.fullmatch(r'[A-Z]{1,3}',col):
                raise HTTPException(422,'Invalid Excel mapping')


@app.post('/projects/{project_id}/import-schedule')
def import_boq(project_id: str, body: ScheduleImportRequest, uid: str = Depends(user_id)):
    """Import an Excel luminaire list, ready to be enriched from manufacturer PDFs."""
    project_owned(project_id, uid)
    file_owned(project_id, uid, body.path)
    check_mapping(body.excel_mapping)
    if not body.path.lower().endswith('.xlsx'):
        raise HTTPException(422, 'Expected an .xlsx file')
    try:
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'import.xlsx'
            source.write_bytes(storage_bytes(body.path))
            items=import_schedule(source,sheet=body.sheet,header_row=body.header_row,column_map=body.excel_mapping)
        if not items:
            raise HTTPException(422,'Excel contains no luminaire codes')
        if len(items)>300:
            raise HTTPException(422,'Import maximum is 300 records per request')
        # Prevent accidental duplicate BOQ rows in project. This does not overwrite reviewed records.
        existing=db().table('luminaires').select('*').eq('project_id',project_id).execute().data
        known={str(row['data'].get('code','')).strip().casefold() for row in existing}
        imported=0;skipped=0
        for item in items:
            code=item.get('code','').strip()
            if not code or code.casefold() in known:
                skipped+=1;continue
            db().table('luminaires').insert({'project_id':project_id,'created_by':uid,'data':item}).execute()
            known.add(code.casefold());imported+=1
        return {'imported':imported,'skipped':skipped,'total':len(items)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422,f'Could not import Lighting Schedule: {type(exc).__name__}: {exc}')


@app.post('/projects/{project_id}/ingest')
def ingest(project_id: str, body: StorageRequest, uid: str = Depends(user_id)):
    project_owned(project_id, uid)
    file_owned(project_id, uid, body.path)
    if not body.path.lower().endswith('.pdf'):
        raise HTTPException(400, 'Only PDF datasheets are supported for extraction')
    try:
        content = storage_bytes(body.path)
        if not content.startswith(b'%PDF-'):
            raise HTTPException(422, 'Uploaded file is not a PDF')
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'source.pdf'
            source.write_bytes(content)
            extracted = parse_pdf(source, Path(tmp)/'images', body.code or Path(body.path).stem)
            values = extracted.values()
            image = Path(extracted.image_path)
            image_path = None
            if extracted.image_path and image.is_file():
                image_path = f'{uid}/{project_id}/images/{uuid.uuid4().hex}.png'
                db().storage.from_(STORAGE_BUCKET).upload(image_path, image.read_bytes(), {'content-type':'image/png','upsert':'false'})
            values['pdf_path'] = body.path
            values['image_path'] = image_path or ''
            # Match BOQ record by light code before creating a new record.
            # Fill missing fields only; preserve quantities and engineer-entered specifications.
            matches=[row for row in db().table('luminaires').select('*').eq('project_id',project_id).execute().data
                     if str(row['data'].get('code','')).strip().casefold()==values['code'].strip().casefold()]
            if len(matches)>1:
                raise HTTPException(409,'Multiple records have the same light code; resolve duplicates')
            if matches:
                previous=matches[0]['data']
                conflicts=[]
                merged=previous.copy()
                for field,value in values.items():
                    if field=='notes':continue
                    if field in ('pdf_path','image_path','source_pages'):
                        merged[field]=value
                    elif value and not previous.get(field):
                        merged[field]=value
                    elif value and previous.get(field) and str(value).strip()!=str(previous[field]).strip() and field!='code':
                        conflicts.append(field)
                annotation='; '.join(filter(None,[previous.get('notes',''), values.get('notes',''),
                    ('REVIEW CONFLICTS: '+', '.join(conflicts)) if conflicts else '']))
                merged['notes']=annotation[:2000]
                return db().table('luminaires').update({'data':merged}).eq('id',matches[0]['id']).eq('project_id',project_id).execute().data[0]
            result = db().table('luminaires').insert({'project_id':project_id,'created_by':uid,'data':values}).execute().data[0]
            return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, f'Could not extract PDF: {type(exc).__name__}: {exc}')


@app.patch('/projects/{project_id}/records/{record_id}')
def update_record(project_id: str,record_id: str,body: RecordUpdate, uid: str = Depends(user_id)):
    project_owned(project_id, uid)
    rows = db().table('luminaires').select('*').eq('id',record_id).eq('project_id',project_id).limit(1).execute().data
    if not rows:
        raise HTTPException(404, 'Record not found')
    if not body.fields or not set(body.fields).issubset(set(FIELDS)):
        raise HTTPException(422, 'Unknown fields in update')
    if any(not isinstance(v, str) or len(v)>2000 for v in body.fields.values()):
        raise HTTPException(422,'Invalid specification value')
    updated = {**rows[0]['data'], **body.fields}
    # Preserve verified upload references; do not allow overwriting attachment paths via editing.
    for k in ('pdf_path','image_path'):
        updated[k] = rows[0]['data'].get(k,'')
    return db().table('luminaires').update({'data':updated}).eq('id',record_id).eq('project_id',project_id).execute().data[0]


@app.delete('/projects/{project_id}/records/{record_id}',status_code=204)
def delete_record(project_id: str,record_id: str,uid: str = Depends(user_id)):
    project_owned(project_id, uid)
    db().table('luminaires').delete().eq('id',record_id).eq('project_id',project_id).execute()
    return Response(status_code=204)


@app.get('/projects/{project_id}/file-url')
def file_url(project_id: str,path: str=Query(...),uid: str=Depends(user_id)):
    project_owned(project_id, uid)
    file_owned(project_id, uid, path)
    return db().storage.from_(STORAGE_BUCKET).create_signed_url(path, 120)


def gather_records(project_id: str, uid: str, ids: list[str]):
    project_owned(project_id, uid)
    try:
        normalized_ids = [str(uuid.UUID(record_id)) for record_id in ids]
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, 'Invalid record ID')
    if len(normalized_ids) != len(set(normalized_ids)):
        raise HTTPException(422, 'Duplicate record IDs are not allowed')
    rows = db().table('luminaires').select('*').eq('project_id', project_id).in_('id',normalized_ids).execute().data
    by_id = {row['id']:row for row in rows}
    if len(by_id)!=len(set(ids)):
        raise HTTPException(403,'At least one selected record does not belong to project')
    return [by_id[rid]['data'].copy() for rid in normalized_ids]


def export_file(project_id: str,kind: str,body:ExportRequest,uid:str):
    check_mapping(body.excel_mapping)
    records = gather_records(project_id,uid,body.record_ids)
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        template=None
        if body.template_path:
            file_owned(project_id,uid,body.template_path)
            expected = '.xlsx' if kind=='excel' else '.pptx'
            if not body.template_path.lower().endswith(expected):
                raise HTTPException(422,'Template file type does not match export type')
            template=root/('template'+expected)
            template.write_bytes(storage_bytes(body.template_path))
        if kind=='pptx':
            for i,rec in enumerate(records):
                im_path=rec.get('image_path','')
                if im_path:
                    file_owned(project_id,uid,im_path)
                    target=root/f'image_{i}.png'
                    target.write_bytes(storage_bytes(im_path))
                    rec['image_path']=str(target)
            output=root/'GEC_Lighting_Specifications.pptx'
            export_pptx(records,output,template=template)
            media='application/vnd.openxmlformats-officedocument.presentationml.presentation'
        else:
            output=root/'GEC_Lighting_Schedule.xlsx'
            export_schedule(records,output,template=template,sheet=body.excel_sheet,start_row=body.excel_start_row,column_map=body.excel_mapping)
            media='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return Response(content=output.read_bytes(),media_type=media,headers={'Content-Disposition':f'attachment; filename="{output.name}"','Cache-Control':'no-store'})


@app.post('/projects/{project_id}/export/{kind}')
def download_export(project_id:str,kind:str,body:ExportRequest,uid:str=Depends(user_id)):
    if kind not in ('excel','pptx'):
        raise HTTPException(404,'Unsupported export type')
    try:
        return export_file(project_id,kind,body,uid)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422,f'Export failed: {type(exc).__name__}: {exc}')
