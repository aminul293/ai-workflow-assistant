import {NextRequest,NextResponse} from 'next/server';
import {createHmac,timingSafeEqual} from 'node:crypto';
export const runtime='nodejs';
function equal(a:string,b:string){const x=Buffer.from(a),y=Buffer.from(b);return x.length===y.length&&timingSafeEqual(x,y)}
export async function POST(req:NextRequest){
 const secret=process.env.SESSION_SECRET||'';
 const username=process.env.APP_USERNAME||'';const password=process.env.APP_PASSWORD||'';
 if(secret.length<32||!username||!password)return NextResponse.json({detail:'Server authentication not configured'},{status:503});
 if(req.headers.get('origin')!==req.nextUrl.origin)return NextResponse.json({detail:'Invalid origin'},{status:403});
 let body:{username?:unknown;password?:unknown};
 try{body=await req.json()}catch{return NextResponse.json({detail:'Invalid JSON'},{status:400})}
 if(typeof body.username!=='string'||typeof body.password!=='string'||!equal(body.username,username)||!equal(body.password,password))
  return NextResponse.json({detail:'Invalid credentials'},{status:401,headers:{'Cache-Control':'no-store'}});
 const ts=Date.now().toString();const signature=createHmac('sha256',secret).update(ts).digest('hex');
 const result=NextResponse.json({ok:true},{headers:{'Cache-Control':'no-store'}});
 result.cookies.set('awa_session',ts+'.'+signature,{httpOnly:true,secure:process.env.NODE_ENV==='production',sameSite:'strict',path:'/',maxAge:12*60*60});
 return result;
}