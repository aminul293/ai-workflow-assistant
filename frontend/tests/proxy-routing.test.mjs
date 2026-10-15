import test from 'node:test';
import assert from 'node:assert/strict';
import {buildBackendUrl} from '../lib/backend-url.mjs';

test('dashboard API paths reach backend with exactly one /api prefix', () => {
  assert.equal(buildBackendUrl('http://127.0.0.1:8000', ['api', 'inbox']), 'http://127.0.0.1:8000/api/inbox');
  assert.equal(buildBackendUrl('http://127.0.0.1:8000/', ['api', 'ready']), 'http://127.0.0.1:8000/api/ready');
});
test('processing and workflow trace paths are preserved', () => {
  assert.equal(buildBackendUrl('https://backend.example', ['api', 'inbox', 'sample-id', 'process']), 'https://backend.example/api/inbox/sample-id/process');
  assert.equal(buildBackendUrl('https://backend.example', ['api', 'workflow-runs', 'run-id']), 'https://backend.example/api/workflow-runs/run-id');
});
test('non-API paths are rejected', () => {
  for (const path of [[], ['api'], ['admin', 'users'], ['inbox']]) assert.throws(() => buildBackendUrl('http://localhost:8000', path));
});
test('traversal and encoded URL tricks are rejected', () => {
  for (const segment of ['..', '.', '%2e%2e', 'x/y', 'x?y', 'x#y', 'https:']) assert.throws(() => buildBackendUrl('http://localhost:8000', ['api', segment]));
});
test('backend must be a plain server-controlled HTTP(S) origin', () => {
  for (const base of ['file:///tmp/x', 'https://user:password@example.test', 'https://example.test/prefix', 'https://example.test?key=secret']) assert.throws(() => buildBackendUrl(base, ['api', 'inbox']));
});
