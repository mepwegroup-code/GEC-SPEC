"""Template writer. Mapping keys are field names; values are Excel column letters."""
from pathlib import Path
from copy import copy
import json
from openpyxl import load_workbook,Workbook
from openpyxl.styles import Font,PatternFill
from openpyxl.utils import column_index_from_string,get_column_letter
from .models import FIELDS,LABELS

DEFAULT_MAP={k:get_column_letter(i+1) for i,k in enumerate(FIELDS[:17])}

def import_schedule(path, sheet=None, header_row=1, column_map=None):
    wb=load_workbook(path,read_only=True,data_only=True)
    try:
        ws=wb[sheet] if sheet else wb.active
        mapping=column_map or DEFAULT_MAP
        result=[]
        for row in range(header_row+1,ws.max_row+1):
            obj={k:'' for k in FIELDS}
            for k,col in mapping.items():
                if k in obj:
                    v=ws[f'{col}{row}'].value
                    obj[k]=str(v).strip() if v is not None else ''
            if obj['code'] or obj['model']:result.append(obj)
        return result
    finally:wb.close()

def export_schedule(records, output, template=None, sheet=None, start_row=2, column_map=None):
    mapping=column_map or DEFAULT_MAP
    if template:
        wb=load_workbook(template)
        ws=wb[sheet] if sheet else wb.active
    else:
        wb=Workbook();ws=wb.active;ws.title='Lighting Schedule';start_row=2
        for k,col in mapping.items():
            cell=ws[f'{col}1'];cell.value=LABELS.get(k,k);cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='193B5A')
            ws.column_dimensions[col].width=max(14,min(28,len(LABELS.get(k,k))+5))
        ws.freeze_panes='C2'
    for offset,rec in enumerate(records):
        row=start_row+offset
        if template and row>start_row:
            for col in mapping.values():
                src=ws[f'{col}{start_row}'];dst=ws[f'{col}{row}']
                if src.has_style: dst._style=copy(src._style)
                if src.number_format:dst.number_format=src.number_format
                dst.alignment=copy(src.alignment)
            if ws.row_dimensions[start_row].height:ws.row_dimensions[row].height=ws.row_dimensions[start_row].height
        for key,col in mapping.items():
            if key in rec:
                value = rec[key]
                # Prevent generated XLSX cells interpreting model/description as formulas.
                if isinstance(value, str) and value.lstrip().startswith('='):
                    value = "'" + value
                ws[f'{col}{row}'] = value
    wb.save(output)
    return output
