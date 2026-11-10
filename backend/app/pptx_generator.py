"""1-slide-per-luminaire PowerPoint; accepts optional template with named shapes.
Template contract: first slide is the design slide. Text boxes named SPEC_code etc;
image frame named SPEC_IMAGE. If absent, fallback overlay layout is used.
"""
from pathlib import Path
from io import BytesIO
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from PIL import Image
from .models import LABELS

DISPLAY=['code','model','brand','power','flux','cct','cri','beam','voltage','ip','ik','size','driver','dimming','lifetime']

def _replace(shape,text):
    if shape.has_text_frame:shape.text=str(text)

def _fit_image(slide,path,left,top,width,height):
    with Image.open(path) as im:w,h=im.size
    scale=min(width/w,height/h)
    iw,ih=int(w*scale),int(h*scale)
    slide.shapes.add_picture(str(path),int(left+(width-iw)/2),int(top+(height-ih)/2),width=iw,height=ih)

def _text(slide,text,x,y,w,h,size=12,bold=False,color=(34,45,60)):
    shape=slide.shapes.add_textbox(int(x),int(y),int(w),int(h));tf=shape.text_frame;tf.word_wrap=True
    tf.text=str(text)
    for para in tf.paragraphs:
        para.font.size=Pt(size);para.font.bold=bold;para.font.color.rgb=RGBColor(*color)
    return shape

def _default_slide(prs,rec):
    slide=prs.slides.add_slide(prs.slide_layouts[6]);sw,sh=prs.slide_width,prs.slide_height
    _text(slide,'GENERAL E&C | LIGHTING SPECIFICATIONS',Inches(.35),Inches(.2),sw-Inches(.7),Inches(.3),14,True,(20,72,111))
    _text(slide,rec.get('code','')+'  |  '+rec.get('model',''),Inches(.35),Inches(.62),sw-Inches(.7),Inches(.55),22,True)
    left=Inches(.35);top=Inches(1.38);iw=int(sw*.43);ih=int(sh-Inches(1.75))
    if rec.get('image_path') and Path(rec['image_path']).is_file():_fit_image(slide,rec['image_path'],left,top,iw,ih)
    else:_text(slide,'PRODUCT IMAGE\n(Not available)',left,top,iw,ih,14)
    x=int(sw*.49);y=Inches(1.3);line=Inches(.35)
    for k in DISPLAY[2:]:
        v=rec.get(k,'')
        _text(slide,f'{LABELS[k]}:  {v if v else "—"}',x,y,sw-x-Inches(.3),line,11)
        y+=line
        if y+line>sh-Inches(.25):break
    return slide

def _duplicate_template_slide(prs):
    # Copy XML elements and relationship targets with dedicated new slide.
    from copy import deepcopy
    source=prs.slides[0]
    target=prs.slides.add_slide(source.slide_layout)
    for shape in list(target.shapes):
        sp=shape._element;sp.getparent().remove(sp)
    for shape in source.shapes:
        target.shapes._spTree.insert_element_before(deepcopy(shape._element),'p:extLst')
    for rel in source.part.rels.values():
        if rel.reltype.endswith('/notesSlide'):continue
        if rel.is_external:target.part.rels.get_or_add_ext_rel(rel.reltype,rel.target_ref)
        else:target.part.rels.get_or_add(rel.reltype,rel.target_part)
    return target

def export_pptx(records,output,template=None):
    if template:
        prs=Presentation(template)
        if len(prs.slides)!=1:raise ValueError('PPTX template must contain exactly one design slide')
        for rec in records:
            slide=_duplicate_template_slide(prs)
            frames=[]
            for shape in slide.shapes:
                name=shape.name.strip()
                if name.lower()=='spec_image':frames.append(shape)
                elif name.lower().startswith('spec_'):
                    field=name[5:].lower();_replace(shape,rec.get(field,''))
            if not any(s.name.lower().startswith('spec_') for s in slide.shapes):
                raise ValueError('Template needs SPEC_<field> text shapes and SPEC_IMAGE image frame')
            if frames and rec.get('image_path') and Path(rec['image_path']).is_file():
                for frame in frames:
                    _fit_image(slide,rec['image_path'],frame.left,frame.top,frame.width,frame.height)
                    node=frame._element;node.getparent().remove(node)
        # Remove original design slide (relationships handled by python-pptx).
        sld_id=prs.slides._sldIdLst[0];prs.part.drop_rel(sld_id.rId);prs.slides._sldIdLst.remove(sld_id)
    else:
        prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
        for rec in records:_default_slide(prs,rec)
    prs.save(output);return output
