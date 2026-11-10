import { NextRequest, NextResponse } from 'next/server';
import { createServerClient } from '@supabase/ssr';
export async function GET(request:NextRequest){
  const url=new URL(request.url);const code=url.searchParams.get('code');
  const response=NextResponse.redirect(new URL('/',url.origin));
  if(code){
    const supabase=createServerClient(process.env.NEXT_PUBLIC_SUPABASE_URL!,process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,{
      cookies:{getAll(){return request.cookies.getAll()},setAll(cookies){cookies.forEach(({name,value,options})=>response.cookies.set(name,value,options))}}
    });
    const result=await supabase.auth.exchangeCodeForSession(code);
    if(result.error)return NextResponse.redirect(new URL('/?error=auth',url.origin));
  }
  return response;
}
