from dataclasses import dataclass, asdict
from pathlib import Path

FIELDS = ['code','model','brand','description','power','flux','cct','cri','beam','voltage','ip','ik','size','driver','dimming','lifetime','quantity','pdf_path','image_path','source_pages','notes']
LABELS = dict(zip(FIELDS,['Code','Model','Brand','Description','Power (W)','Flux (lm)','CCT (K)','CRI','Beam angle','Voltage','IP','IK','Dimensions','Driver','Dimming','Lifetime','Quantity','Source PDF','Product image','Source pages','Notes']))
@dataclass
class Luminaire:
    code:str=''
    model:str=''
    brand:str=''
    description:str=''
    power:str=''
    flux:str=''
    cct:str=''
    cri:str=''
    beam:str=''
    voltage:str=''
    ip:str=''
    ik:str=''
    size:str=''
    driver:str=''
    dimming:str=''
    lifetime:str=''
    quantity:str='1'
    pdf_path:str=''
    image_path:str=''
    source_pages:str=''
    notes:str=''
    def values(self): return asdict(self)
