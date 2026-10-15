import {NextRequest,NextResponse} from 'next/server';
export const dynamic = 'force-dynamic';
async function relay(req:NextRequest,ctx:{params:Promise<{path:string[]}>}){
 const base=process.env.BACKEND_URL || 'http://127.0.0.1:8000';
 const secret=process.env.BACKEND_API_KEY;
 if(!secret || !process.env.APP_USERNAME || !process.env.APP_PASSWORD)
  return NextResponse.json({detail:'Server configuration incomplete'},{status:503});
 const {path}=await ctx.params;
 if(!path.length || path.some(p=>!/^[-_a-zA-Z0-9]+$/.test(p)))
  return NextResponse.json({detail:'Invalid path'},{status:400});
 const url=base.replace(/\/$/,'')+'/api/'+path.join('/');
 try{
  const result=await fetch(url,{method:req.method,headers:{'X-API-Key':secret,'Content-Type':'application/json'},
   body:['POST','PATCH'].includes(req.method)?await req.text():undefined,
   cache:'no-store',signal:AbortSignal.timeout(12000)});
  return new NextResponse(await result.text(),{status:result.status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
 }catch{return NextResponse.json({detail:'Backend unavailable'},{status:502});}
}
export {relay as GET,relay as POST,relay as PATCH};