import {NextRequest,NextResponse} from 'next/server';
const COOKIE='awa_session';
const encoder=new TextEncoder();
function constantTimeEqual(a:string,b:string){let d=a.length^b.length;for(let i=0;i<Math.max(a.length,b.length);i++)d|=(a.charCodeAt(i)||0)^(b.charCodeAt(i)||0);return d===0;}
async function validSession(value:string,secret:string):Promise<boolean>{
 const parts=value.split('.');if(parts.length!==2 || !/^\d{10,13}$/.test(parts[0]) || !/^[a-f0-9]{64}$/.test(parts[1]))return false;
 const ts=Number(parts[0]);const now=Date.now();if(ts>now+60000 || now-ts>12*60*60*1000)return false;
 const key=await crypto.subtle.importKey('raw',encoder.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);
 const signature=await crypto.subtle.sign('HMAC',key,encoder.encode(parts[0]));
 const hex=Array.from(new Uint8Array(signature)).map(b=>b.toString(16).padStart(2,'0')).join('');
 return constantTimeEqual(hex,parts[1]);
}
export async function middleware(req:NextRequest){
 const secret=process.env.SESSION_SECRET;
 if(!secret || secret.length<32 || !process.env.APP_USERNAME || !process.env.APP_PASSWORD)
  return new NextResponse('Configure APP_USERNAME, APP_PASSWORD and SESSION_SECRET (32+ chars)',{status:503});
 const path=req.nextUrl.pathname;
 const publicPath=path==='/login'||path==='/api/auth/login';
 if(publicPath){
  if(path==='/api/auth/login' && req.method!=='POST')return NextResponse.json({detail:'Method not allowed'},{status:405});
  return NextResponse.next();
 }
 const authenticated=await validSession(req.cookies.get(COOKIE)?.value||'',secret);
 if(!authenticated){
  if(path.startsWith('/api/'))return NextResponse.json({detail:'Authentication required'},{status:401});
  return NextResponse.redirect(new URL('/login',req.url));
 }
 if(!['GET','HEAD','OPTIONS'].includes(req.method)){
  const origin=req.headers.get('origin');
  if(!origin || origin!==req.nextUrl.origin)return NextResponse.json({detail:'Invalid request origin'},{status:403});
 }
 const result=NextResponse.next();
 result.headers.set('X-Content-Type-Options','nosniff');
 result.headers.set('Referrer-Policy','no-referrer');
 result.headers.set('X-Frame-Options','DENY');
 return result;
}
export const config={matcher:['/((?!_next/static|_next/image|favicon.ico).*)']};