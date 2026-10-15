import test from 'node:test';
import assert from 'node:assert/strict';
import {isAllowedOrigin} from '../lib/request-origin.mjs';

test('explicit frontend origin permits loopback and HTTPS requests', () => {
  assert.equal(isAllowedOrigin('http://127.0.0.1:52749', 'http://127.0.0.1:52749'), true);
  assert.equal(isAllowedOrigin('https://app.example', 'https://app.example/'), true);
});
test('untrusted origin, scheme and port are rejected', () => {
  for (const origin of ['https://evil.example', 'http://app.example', 'https://app.example:444']) {
    assert.equal(isAllowedOrigin(origin, 'https://app.example'), false);
  }
});
test('missing or malformed origins fail closed', () => {
  for (const origin of [null, '', 'null', 'not a URL']) assert.equal(isAllowedOrigin(origin, 'https://app.example'), false);
  assert.equal(isAllowedOrigin('https://app.example', undefined), false);
});
test('configuration cannot include credentials, paths or query strings', () => {
  for (const expected of ['file:///tmp/x', 'https://u:p@app.example', 'https://app.example/path', 'https://app.example?x=1']) {
    assert.equal(isAllowedOrigin('https://app.example', expected), false);
  }
});
test('Origin header must be an origin, not a URL with extra components', () => {
  for (const origin of ['https://app.example/path', 'https://u:p@app.example', 'https://app.example#fragment']) {
    assert.equal(isAllowedOrigin(origin, 'https://app.example'), false);
  }
});
