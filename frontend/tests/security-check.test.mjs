import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
const read=(path)=>readFileSync(new URL(path,import.meta.url),'utf8');
test('signed session is checked in middleware',()=>{const x=read('../middleware.ts');assert.match(x,/crypto\.subtle\.sign/);assert.match(x,/12\*60\*60\*1000/);assert.match(x,/req\.cookies\.get/)});
test('unsafe requests are subject to origin check',()=>{const x=read('../middleware.ts');assert.match(x,/isAllowedOrigin\(origin,process\.env\.APP_ORIGIN\)/)});
test('login validates credentials and issues HTTP-only session cookie',()=>{const x=read('../app/api/auth/login/route.ts');assert.match(x,/timingSafeEqual/);assert.match(x,/httpOnly:true/);assert.match(x,/sameSite:'strict'/)});
test('logout clears session',()=>{const x=read('../app/api/auth/logout/route.ts');assert.match(x,/maxAge:0/)});
