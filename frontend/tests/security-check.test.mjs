import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read=(path)=>readFileSync(new URL(path,import.meta.url),'utf8');
test('signed session is checked in middleware',()=>{
 const x=read('../middleware.ts');
 assert.match(x,/crypto\.subtle\.sign/);
 assert.match(x,/12\*60\*60\*1000/);
 assert.match(x,/req\.cookies\.get/);
});
test('unsafe requests use browser Origin and server-configured APP_ORIGIN',()=>{
 const x=read('../middleware.ts');
 assert.match(x,/const origin=process\.env\.APP_ORIGIN/);
 assert.match(x,/isAllowedOrigin\(req\.headers\.get\('origin'\),origin\)/);
 assert.match(x,/Invalid request origin/);
});
test('anonymous page redirects use public rather than internal origin',()=>{
 const x=read('../middleware.ts');
 assert.match(x,/NextResponse\.redirect\(new URL\('\/login',origin\)\)/);
 assert.doesNotMatch(x,/new URL\('\/login',req\.url\)/);
});
test('login validates credentials and issues HTTP-only session cookie',()=>{
 const x=read('../app/api/auth/login/route.ts');
 assert.match(x,/timingSafeEqual/);assert.match(x,/httpOnly:true/);assert.match(x,/sameSite:'strict'/);
});
test('logout clears session',()=>{assert.match(read('../app/api/auth/logout/route.ts'),/maxAge:0/)});
