"""20 isolated full HTTP API exercises, covering actual PDF, XLSX and PPTX bytes.
Supabase is replaced by an in-memory storage/database, not network access.
"""
import io
import uuid
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font
from pptx import Presentation
from pptx.util import Inches
from PIL import Image

import app.main as main

UID = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'

class Query:
    def __init__(self, db, table):
        self.db=db;self.table=table;self.filters=[];self.update_data=None
        self.operation='select';self.in_filter=None;self.limit_count=None;self.order_key=None;self.reverse=False
    def select(self,*a): self.operation='select';return self
    def insert(self, data): self.operation='insert';self.update_data=data;return self
    def update(self,data): self.operation='update';self.update_data=data;return self
    def delete(self): self.operation='delete';return self
    def eq(self,key,value): self.filters.append((key,value));return self
    def in_(self,key,values): self.in_filter=(key,values);return self
    def limit(self,n): self.limit_count=n;return self
    def order(self,key,desc=False): self.order_key=key;self.reverse=desc;return self
    def execute(self):
        rows=self.db.tables[self.table]
        if self.operation=='insert':
            item={'id':str(uuid.uuid4()),'created_at':'2026-10-31T00:00:00Z', **deepcopy(self.update_data)}
            rows.append(item);return SimpleNamespace(data=[deepcopy(item)])
        target=[r for r in rows if all(r.get(k)==v for k,v in self.filters) and (self.in_filter is None or r.get(self.in_filter[0]) in self.in_filter[1])]
        if self.order_key:target=sorted(target,key=lambda r:r.get(self.order_key,''),reverse=self.reverse)
        if self.limit_count is not None:target=target[:self.limit_count]
        if self.operation=='update':
            for row in target:row.update(deepcopy(self.update_data))
        if self.operation=='delete':
            for row in target:rows.remove(row)
        return SimpleNamespace(data=deepcopy(target))

class MockStorage:
    def __init__(self):self.objects={}
    def from_(self,bucket): assert bucket=='project-files';return self
    def download(self,path):return self.objects[path]
    def upload(self,path,content,metadata=None):
        assert path not in self.objects
        self.objects[path]=content
        return {'path':path}
    def create_signed_url(self,path,expires):
        assert path in self.objects
        return {'signedURL':'https://storage.test/'+path}

class MockDB:
    def __init__(self):self.tables={'projects':[],'luminaires':[]};self.storage=MockStorage()
    def table(self,name):return Query(self,name)

@pytest.fixture
def client_db(monkeypatch):
    db=MockDB()
    main.app.dependency_overrides[main.user_id]=lambda:UID
    monkeypatch.setattr(main,'db',lambda:db)
    try: yield TestClient(main.app),db
    finally:main.app.dependency_overrides.clear()


def example_pdf():
    document=fitz.open();page=document.new_page(width=600,height=800)
    lines=['Model: ABC-30W-930-IP66','Rated power: 30 W','Luminous flux: 3200 lm',
           'CCT: 3000 K','CRI: 90','Beam angle: 36°','Input voltage: 220-240 V',
           'IP66','IK08','Lifetime: 50000 h']
    for index,line in enumerate(lines):page.insert_text((40,45+index*30),line,fontsize=13)
    image=Image.new('RGB',(170,180),'#3378aa');buf=io.BytesIO();image.save(buf,format='PNG')
    page.insert_image(fitz.Rect(335,150,550,410),stream=buf.getvalue())
    return document.tobytes()

def excel_template():
    wb=Workbook();ws=wb.active;ws.title='BOQ';ws['A5']='CODE';ws['D5']='POWER';ws['A6'].font=Font(name='Arial',size=11,bold=True)
    stream=io.BytesIO();wb.save(stream);return stream.getvalue()

def pptx_template():
    pres=Presentation();slide=pres.slides.add_slide(pres.slide_layouts[6]);shape=slide.shapes.add_textbox(Inches(1),Inches(1),Inches(5),Inches(.5));shape.name='SPEC_code'
    other=slide.shapes.add_textbox(Inches(1),Inches(2),Inches(5),Inches(.5));other.name='SPEC_power'
    image=slide.shapes.add_shape(1, Inches(6), Inches(1), Inches(3), Inches(3));image.name='SPEC_IMAGE'
    stream=io.BytesIO();pres.save(stream);return stream.getvalue()

@pytest.mark.parametrize('round_number',range(1,21))
def test_twenty_complete_api_cycles(round_number,client_db):
    client,db=client_db
    assert client.get('/health').json()['version']=='0.3.0'
    p=client.post('/projects',json={'name':f'GBIA test {round_number}'})
    assert p.status_code==201,p.text
    project=p.json()['id'];assert len(client.get('/projects').json())==1
    path=f'{UID}/{project}/pdf/{uuid.uuid4()}.pdf'
    db.storage.objects[path]=example_pdf()
    resp=client.post(f'/projects/{project}/ingest',json={'path':path,'code':f'LT-{round_number:03d}'})
    assert resp.status_code==200,resp.text
    record=resp.json();rid=record['id'];data=record['data']
    assert data['model']=='ABC-30W-930-IP66',data
    assert data['power']=='30 W' and data['flux']=='3200 lm',data
    assert data['cct']=='3000 K' and data['ip']=='IP66',data
    assert data['image_path'] and data['image_path'] in db.storage.objects
    assert client.get(f'/projects/{project}/file-url',params={'path':path}).status_code==200
    assert client.get(f'/projects/{project}/records').json()[0]['id']==rid
    edit=client.patch(f'/projects/{project}/records/{rid}',json={'fields':{'brand':'Signify','quantity':'4'}})
    assert edit.status_code==200 and edit.json()['data']['brand']=='Signify',edit.text
    assert edit.json()['data']['pdf_path']==path
    post={'record_ids':[rid]}
    excel=client.post(f'/projects/{project}/export/excel',json=post)
    assert excel.status_code==200,excel.text
    book=load_workbook(io.BytesIO(excel.content));assert book.active['A2'].value==f'LT-{round_number:03d}'
    assert book.active['C2'].value=='Signify' and book.active['Q2'].value=='4'
    deck=client.post(f'/projects/{project}/export/pptx',json=post)
    assert deck.status_code==200,deck.text
    ppt=Presentation(io.BytesIO(deck.content));assert len(ppt.slides)==1
    assert any('LT-' in shape.text for shape in ppt.slides[0].shapes if shape.has_text_frame)
    assert any(shape.shape_type==13 for shape in ppt.slides[0].shapes)  # raster product image
    templ_excel=f'{UID}/{project}/excel/{uuid.uuid4()}.xlsx'
    templ_pptx=f'{UID}/{project}/pptx/{uuid.uuid4()}.pptx'
    db.storage.objects[templ_excel]=excel_template();db.storage.objects[templ_pptx]=pptx_template()
    custom=client.post(f'/projects/{project}/export/excel',json={**post,'template_path':templ_excel,'excel_start_row':6,'excel_sheet':'BOQ','excel_mapping':{'code':'A','power':'D'}})
    assert custom.status_code==200,custom.text
    w=load_workbook(io.BytesIO(custom.content));assert w['BOQ']['A6'].value==f'LT-{round_number:03d}'
    assert w['BOQ']['D6'].value=='30 W' and w['BOQ']['A6'].font.bold
    customdeck=client.post(f'/projects/{project}/export/pptx',json={**post,'template_path':templ_pptx})
    assert customdeck.status_code==200,customdeck.text
    pres=Presentation(io.BytesIO(customdeck.content));assert len(pres.slides)==1
    assert any(shp.text==f'LT-{round_number:03d}' for shp in pres.slides[0].shapes if shp.has_text_frame)
    assert any(shp.shape_type==13 for shp in pres.slides[0].shapes)
    assert client.delete(f'/projects/{project}/records/{rid}').status_code==204
    assert client.get(f'/projects/{project}/records').json()==[]


def test_security_guards(client_db):
    client,db=client_db;project=client.post('/projects',json={'name':'Private'}).json()['id']
    assert client.post(f'/projects/{project}/ingest',json={'path':f'{OTHER}/{project}/pdf/other.pdf'}).status_code==403
    assert client.post(f'/projects/{project}/ingest',json={'path':f'{UID}/{project}/pdf/../file.pdf'}).status_code==403
    assert client.post(f'/projects/{project}/ingest',json={'path':f'{UID}/{project}/pdf//file.pdf'}).status_code==403
    assert client.post(f'/projects/{project}/export/excel',json={'record_ids':['not-a-uuid']}).status_code==422
    assert client.post(f'/projects/{project}/export/excel',json={'record_ids':[str(uuid.uuid4())], 'excel_mapping': {'code':'A','model':'A'}}).status_code==422
    path=f'{UID}/{project}/pdf/{uuid.uuid4()}.pdf';db.storage.objects[path]=b'fake'
    assert client.post(f'/projects/{project}/ingest',json={'path':path}).status_code==422


def test_formula_is_written_as_text(client_db):
    client,db=client_db;project=client.post('/projects',json={'name':'Formula'}).json()['id']
    # A spreadsheet formula arriving from a PDF must not be executable in exported XLSX.
    row=db.table('luminaires').insert({'project_id':project,'data':{'code':'LT=1','model':'=HYPERLINK("evil")'},'created_by':UID}).execute().data[0]
    excel=client.post(f'/projects/{project}/export/excel',json={'record_ids':[row['id']]})
    assert excel.status_code==200
    cell=load_workbook(io.BytesIO(excel.content)).active['B2']
    assert cell.data_type!='f' and cell.value.startswith("'=")


def test_import_boq_and_merge_conflicts_without_overwriting_reviewed_values(client_db):
    client,db=client_db
    project=client.post('/projects',json={'name':'Excel BOQ merge'}).json()['id']
    wb=Workbook(); ws=wb.active;ws['A1']='Code';ws['B1']='Power';ws['C1']='Quantity'
    ws.append(['LT-77','35 W','6']);stream=io.BytesIO();wb.save(stream)
    excel_path=f'{UID}/{project}/excel/boq.xlsx';db.storage.objects[excel_path]=stream.getvalue()
    path_pdf=f'{UID}/{project}/pdf/source.pdf';db.storage.objects[path_pdf]=example_pdf()
    r=client.post(f'/projects/{project}/import-schedule',json={'path':excel_path,'excel_mapping':{'code':'A','power':'B','quantity':'C'}})
    assert r.status_code==200,r.text
    assert r.json()=={'imported':1,'skipped':0,'total':1}
    again=client.post(f'/projects/{project}/import-schedule',json={'path':excel_path,'excel_mapping':{'code':'A','power':'B','quantity':'C'}})
    assert again.json()['skipped']==1
    record=client.get(f'/projects/{project}/records').json()[0]
    ingested=client.post(f'/projects/{project}/ingest',json={'path':path_pdf,'code':'LT-77'})
    assert ingested.status_code==200,ingested.text
    updated=ingested.json()
    assert updated['id']==record['id']  # no duplicate creation
    assert updated['data']['power']=='35 W'  # existing BOQ value retained
    assert updated['data']['model']=='ABC-30W-930-IP66'
    assert updated['data']['quantity']=='6'
    assert 'REVIEW CONFLICTS: power' in updated['data']['notes']
    assert len(client.get(f'/projects/{project}/records').json())==1
    wrong=client.post(f'/projects/{project}/import-schedule',json={'path':path_pdf})
    assert wrong.status_code==422
