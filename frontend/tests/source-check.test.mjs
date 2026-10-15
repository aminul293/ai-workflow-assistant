import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const ui=readFileSync(new URL('../app/page.tsx', import.meta.url),'utf8');
const proxy=readFileSync(new URL('../app/api/proxy/[...path]/route.ts',import.meta.url),'utf8');
const css=readFileSync(new URL('../app/style.css',import.meta.url),'utf8');
test('sample loader refreshes after checking HTTP response',()=>{
 assert.match(ui,/if\(!r\.ok\)throw new Error\('Seed failed'\);await refresh\(\)/);
});
test('UI exposes ready/unavailable backend state',()=>{
 assert.match(ui,/api\/ready/);assert.match(ui,/Backend unavailable/);
});
test('server proxy keeps secrets server side and disables caching',()=>{
 assert.match(proxy,/process\.env\.BACKEND_API_KEY/);
 assert.doesNotMatch(proxy,/NEXT_PUBLIC_/);assert.match(proxy,/no-store/);
});
test('mobile navigation and focus visibility rules exist',()=>{
 assert.match(css,/@media\(max-width:590px\)/);assert.match(css,/:focus-visible/);
});
