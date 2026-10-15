import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read=p=>readFileSync(new URL(p, import.meta.url),'utf8');
test('production build command is configured',()=>{
 const pkg=JSON.parse(read('../package.json'));
 assert.equal(pkg.scripts.build,'next build');
 assert.equal(pkg.version,'1.0.0');
});
test('middleware adds basic security response headers and protects mutation routes',()=>{
 const middleware=read('../middleware.ts');
 for(const header of ['X-Content-Type-Options','Referrer-Policy','X-Frame-Options'])assert.ok(middleware.includes(header));
 assert.match(middleware,/Invalid request origin/);
 assert.match(middleware,/Authentication required/);
});
test('client remains confined to synthetic data and avoids direct backend secrets',()=>{
 const page=read('../app/page.tsx');
 assert.match(page,/sample\.test/);
 assert.doesNotMatch(page,/NEXT_PUBLIC_BACKEND_API_KEY/);
 assert.match(page,/No external sending or CRM writes/);
});
