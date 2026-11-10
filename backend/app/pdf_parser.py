"""Conservative, traceable extraction. Never infer missing specifications."""
import re
from pathlib import Path
import fitz
from .models import Luminaire

PATTERNS={
 'power':[r'(?im)^\s*(?:rated\s+)?(?:input\s+)?(?:system\s+)?power(?:\s+consumption)?\s*[:\-]?\s*(\d+(?:[.,]\d+)?\s*W)\b',r'(?i)\b(\d+(?:[.,]\d+)?\s*W)\b'],
 'flux':[r'(?im)^\s*(?:luminous\s+flux|luminaire\s+flux|light\s+output|quang\s+th[oô]ng)\s*[:\-]?\s*([\d., ]+\s*lm)\b'],
 'cct':[r'(?im)^\s*(?:correlated\s+color\s+temperature|colour\s+temperature|color\s+temperature|CCT)\s*[:\-]?\s*(\d{4}(?:\s*[-/]\s*\d{4})?\s*K)\b',r'(?i)\b(2700|3000|3500|4000|5000|5700|6500)\s*K\b'],
 'cri':[r'(?im)^\s*(?:CRI|Ra|color\s+rendering\s+index|colour\s+rendering\s+index)\s*[:\-]?\s*(?:≥|>=|>)?\s*(\d{2,3})\b'],
 'beam':[r'(?im)^\s*(?:beam\s+angle|beam\s+spread|g[oó]c\s+chi[eế]u)\s*[:\-]?\s*([\d.,]+\s*(?:°|deg|degrees))'],
 'voltage':[r'(?im)^\s*(?:input\s+voltage|rated\s+voltage|supply\s+voltage|voltage)\s*[:\-]?\s*([\d]+\s*(?:[-–~]\s*\d+)?\s*V(?:AC|DC)?)\b'],
 'ip':[r'(?i)\b(IP\s*[0-6][0-9])\b'],
 'ik':[r'(?i)\b(IK\s*0?[0-9]{1,2})\b'],
 'size':[r'(?im)^\s*(?:dimensions?|size|k[ií]ch\s+th[ướơ]c)\s*[:\-]?\s*([^\n]{4,65})'],
 'lifetime':[r'(?im)^\s*(?:lifetime|rated\s+life|service\s+life)\s*[:\-]?\s*([\d,. ]+\s*(?:h|hrs|hours))\b'],
 'dimming':[r'(?im)^\s*(?:dimming|control\s+interface)\s*[:\-]?\s*([^\n]{2,45})'],
 'driver':[r'(?im)^\s*(?:driver|control\s+gear)\s*[:\-]?\s*([^\n]{2,50})'],
}

def _match(text, patterns):
    for pat in patterns:
        m = re.search(pat,text)
        if m:
            value = ' '.join(m.group(1).split())
            if len(value)<90: return value
    return ''

def parse_pdf(pdf_path, output_dir, code=''):
    p=Path(pdf_path)
    if p.suffix.lower()!='.pdf': raise ValueError('File must be PDF')
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    doc=fitz.open(str(p))
    try:
        if len(doc)==0: raise ValueError('PDF has no pages')
        # Scope to first 12 pages to reduce unrelated catalogue cross-model leakage.
        pages=[doc[i].get_text('text',sort=True) for i in range(min(len(doc),12))]
        if not any(x.strip() for x in pages):
            raise ValueError('Image-only/scanned PDF: OCR is required; no specifications guessed')
        data=Luminaire(code=code or p.stem, model="", pdf_path=str(p))
        # A temporary upload filename (source.pdf) is NOT a manufacturer model.
        # Only populate model when the datasheet explicitly labels one.
        model_match = re.search(r"(?im)^\s*(?:model(?:\s+number|\s+no\.?)?|product\s+code)\s*[:#-]\s*([^\n]{2,100})$", "\n".join(pages[:2]))
        if model_match:
            candidate = model_match.group(1).strip()
            if not re.search(r"[,;/]|\s(?:or|to)\s", candidate, re.I):
                data.model = candidate
        # Avoid combining properties from multiple unrelated product pages.
        text='\n'.join(pages[:2])
        for field,patterns in PATTERNS.items():setattr(data,field,_match(text,patterns))
        data.source_pages='1-'+str(min(2,len(pages)))
        data.notes = 'Auto-extracted, engineer must verify exact model/variant and each value against manufacturer PDF.'
        # Choose the largest *displayed* raster image excluding very small icons.
        candidates=[]
        for page_no in range(min(len(doc),2)):
            page=doc[page_no]
            for im in page.get_image_info(xrefs=True):
                rect=fitz.Rect(im['bbox']); area=rect.width*rect.height
                if im.get('xref',0)>0 and im['width']>=150 and im['height']>=150 and area>2500:
                    candidates.append((area,page_no,im['xref']))
        if candidates:
            _,_,xref=max(candidates)
            pix=fitz.Pixmap(doc,xref)
            if pix.n>4 or pix.alpha: pix=fitz.Pixmap(fitz.csRGB,pix)
            path=output_dir/(re.sub(r'[^A-Za-z0-9_-]','_',data.code)+'_product.png')
            pix.save(str(path));data.image_path=str(path)
        return data
    finally:doc.close()
