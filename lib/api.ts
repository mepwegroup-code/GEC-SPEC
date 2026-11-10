import { supabase } from './supabase';
export type Specification = Record<string, string>;
export type Project = { id: string; name: string; created_at: string };
export type LuminaireRow = {id:string;project_id:string;data:Specification;created_at:string};
export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export async function request<T>(endpoint:string, options:RequestInit={}):Promise<T>{
  const {data:{session}}=await supabase.auth.getSession();
  if(!session?.access_token)throw new Error('Bạn cần đăng nhập lại.');
  const res=await fetch(`${API_URL}${endpoint}`,{
    ...options,headers:{...options.headers,'Authorization':`Bearer ${session.access_token}`,...(options.body?{'Content-Type':'application/json'}:{})},cache:'no-store'
  });
  if(!res.ok){const payload=await res.json().catch(()=>({}));throw new Error(payload.detail||`HTTP ${res.status}`);}
  return (res.status===204?undefined:await res.json()) as T;
}
export async function download(projectId:string,kind:'excel'|'pptx',ids:string[],templatePath?:string,excelMapping?:Record<string,string>){
  const {data:{session}}=await supabase.auth.getSession();
  if(!session?.access_token)throw new Error('Đăng nhập đã hết hạn');
  const response=await fetch(`${API_URL}/projects/${projectId}/export/${kind}`,{
    method:'POST',headers:{Authorization:`Bearer ${session.access_token}`,'Content-Type':'application/json'},
    body:JSON.stringify({record_ids:ids,template_path:templatePath||null,...(kind==='excel'?{excel_mapping:excelMapping}: {})})
  });
  if(!response.ok){const detail=await response.json().catch(()=>({}));throw new Error(detail.detail||'Không thể xuất file');}
  const blob=await response.blob();const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;a.download=kind==='excel'?'GEC_Lighting_Schedule.xlsx':'GEC_Lighting_Specifications.pptx';document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
}
