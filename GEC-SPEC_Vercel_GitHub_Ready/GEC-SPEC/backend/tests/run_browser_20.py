"""Twenty headless Chromium browser workflows against test-only sandbox preview.
Runs real production FastAPI routes with mock Supabase, not the Next.js bundle.
"""
import json
import base64
import httpx
from pathlib import Path
from playwright.sync_api import sync_playwright
from tests.test_e2e_20_cycles import example_pdf

BASE='http://127.0.0.1:8765/sandbox'
PAGE_HTML=Path(__file__).with_name('sandbox_preview.html').read_text(encoding='utf-8')

def api_bridge(payload):
    method=payload['method'];url=payload['url']
    body=payload.get('body'); kwargs={}
    if isinstance(body, dict) and body.get('type')=='file':
        kwargs['files']={'file':(body['name'],base64.b64decode(body['base64']),body['mime'])}
    elif isinstance(body,str):kwargs['content']=body.encode('utf-8')
    with httpx.Client(timeout=30) as c:
        response=c.request(method,'http://127.0.0.1:8765'+url,headers=payload.get('headers',{}),**kwargs)
    return {'status':response.status_code,'headers':{'content-type':response.headers.get('content-type','application/octet-stream')},'base64':base64.b64encode(response.content).decode('ascii')}

FETCH_BRIDGE_JS = r'''
window.fetch = async (url, options={}) => {
  let body = options.body ?? null;
  if(body instanceof FormData) {
    const file = body.get('file');
    const buf = new Uint8Array(await file.arrayBuffer());
    let value='';for(let i=0;i<buf.length;i++) value+=String.fromCharCode(buf[i]);
    body = {type:'file',name:file.name,mime:file.type,base64:btoa(value)};
  }
  const result = await window.__api_bridge({url:String(url),method:options.method||'GET',headers:options.headers||{},body});
  const bin=atob(result.base64);const bytes=new Uint8Array(bin.length);
  for(let i=0;i<bin.length;i++)bytes[i]=bin.charCodeAt(i);
  return new Response(result.status===204?null:bytes, {status:result.status,headers:result.headers});
};
'''

REPORT=Path(__file__).parents[2] / 'verification' / 'browser_20_runs.json'
REPORT.parent.mkdir(exist_ok=True)
results=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
    for iteration in range(1,21):
        page=browser.new_page(accept_downloads=True,viewport={'width':1440,'height':900})
        failures=[]
        page.on('pageerror',lambda ex:failures.append(str(ex)))
        try:
            # Site source runs in Chromium. HTTP calls are bridged to the actual
            # local FastAPI server because machine-enforced Chromium policy
            # blocks URL navigation (URLBlocklist='*').
            page.expose_function('__api_bridge',api_bridge)
            page.evaluate(FETCH_BRIDGE_JS + "\ntrue;")
            page.set_content(PAGE_HTML,wait_until='load',timeout=20000)
            page.locator('#project-name').fill(f'GEC Browser QA {iteration}')
            page.locator('#create').click()
            page.get_by_role('status').get_by_text('Đã tạo dự án',exact=False).wait_for(timeout=10000)
            page.locator('#pdf').set_input_files({'name':f'LT-{iteration:03d}.pdf','mimeType':'application/pdf','buffer':example_pdf()})
            page.locator('#ingest').click()
            page.get_by_role('status').get_by_text('Đã trích xuất',exact=False).wait_for(timeout=20000)
            page.locator('#rows tr').filter(has_text=f'LT-{iteration:03d}').wait_for(timeout=10000)
            row=page.locator('#rows tr').filter(has_text=f'LT-{iteration:03d}')
            assert 'ABC-30W-930-IP66' in row.inner_text()
            assert '3000 K' in row.inner_text()
            row.get_by_role('button',name='Sửa').click()
            page.locator('#brand').fill('Signify')
            page.locator('#quantity').fill('8')
            page.locator('#editor').get_by_role('button',name='Lưu').click()
            page.locator('#rows tr').filter(has_text='Signify').wait_for(timeout=10000)
            with page.expect_download(timeout=15000) as output:page.locator('#excel').click()
            xlsx=output.value
            assert xlsx.suggested_filename.endswith('.xlsx')
            with page.expect_download(timeout=15000) as output:page.locator('#pptx').click()
            pptx=output.value
            assert pptx.suggested_filename.endswith('.pptx')
            if iteration==20:page.screenshot(path=str(REPORT.parent/'browser_preview.png'),full_page=True)
            page.locator('#rows tr').filter(has_text='Signify').get_by_role('button',name='Xóa').click()
            page.get_by_text('0 mã đèn').wait_for(timeout=10000)
            assert not failures,failures
            results.append({'round':iteration,'status':'PASS','checked':['create project','upload/parse PDF','read fields','edit','download Excel','download PPTX','delete','no page errors']})
            print(f'Browser round {iteration:02d}/20: PASS',flush=True)
        except Exception as exc:
            page.screenshot(path=str(REPORT.parent/f'browser_failed_{iteration}.png'))
            results.append({'round':iteration,'status':'FAIL','exception':str(exc),'page_errors':failures})
            print(f'Browser round {iteration:02d}/20: FAIL {str(exc)[:500]}',flush=True)
            break
        finally:page.close()
    browser.close()
REPORT.write_text(json.dumps({'expected':20,'actual':len(results),'passed':sum(r['status']=='PASS' for r in results),'results':results},indent=2,ensure_ascii=False),encoding='utf-8')
if len(results)!=20 or any(x['status']!='PASS' for x in results):raise SystemExit(1)
