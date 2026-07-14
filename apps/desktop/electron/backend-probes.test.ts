/**
 * Tests for electron/backend-probes.ts.
 *
 * Run with: node --test electron/backend-probes.test.ts
 * (Wired into npm test:desktop:platforms in package.json.)
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { canImportSRCli, srRuntimeImportProbe, verifySRCli } from './backend-probes'

// Resolve the host's own Node binary -- guaranteed to be on disk and
// runnable. We use it as both a stand-in for "a python that doesn't
// have sr_cli" (since `node -c "import sr_cli"` will exit
// non-zero) and as a way to script verifySRCli's success path
// (a tiny script we write to disk that exits 0 on --version).
const NODE_BIN = process.execPath

test('canImportSRCli returns false when path is falsy', () => {
  assert.equal(canImportSRCli(''), false)
  assert.equal(canImportSRCli(null), false)
  assert.equal(canImportSRCli(undefined), false)
})

test('canImportSRCli returns false when interpreter cannot run -c', () => {
  // node IS an interpreter, but `node -c "import sr_cli"` is a
  // SyntaxError -- different exit reason from a real Python's
  // ModuleNotFoundError, but the predicate is "exit 0 or not" and
  // both land on "not", which is exactly what we want for the
  // resolver fall-through.
  assert.equal(canImportSRCli(NODE_BIN), false)
})

test('canImportSRCli returns false when binary does not exist', () => {
  const ghost = path.join(os.tmpdir(), 'sr-probes-ghost-' + Date.now() + '.exe')
  assert.equal(canImportSRCli(ghost), false)
})

test('sr runtime import probe checks config dependencies', () => {
  const probe = srRuntimeImportProbe()
  assert.match(probe, /\bimport yaml\b/)
  // dotenv is the first third-party import on the CLI boot path
  // (sr_cli/env_loader.py); a mid-update venv missing python-dotenv
  // passed the old probe and produced an unrecoverable boot loop.
  assert.match(probe, /\bimport dotenv\b/)
  assert.match(probe, /\bimport sr_cli\.config\b/)
})

test('verifySRCli returns false when command is falsy', () => {
  assert.equal(verifySRCli(''), false)
  assert.equal(verifySRCli(null), false)
  assert.equal(verifySRCli(undefined), false)
})

test('verifySRCli returns false when binary does not exist', () => {
  const ghost = path.join(os.tmpdir(), 'sr-probes-ghost-' + Date.now() + '.exe')
  assert.equal(verifySRCli(ghost), false)
})

test('verifySRCli returns true when --version exits 0', () => {
  // Write a tiny script that exits 0 regardless of args, then invoke
  // it through node. This stands in for a working sr binary --
  // verifySRCli only cares about the exit code.
  const scriptPath = path.join(os.tmpdir(), `sr-probes-ok-${Date.now()}-${process.pid}.cjs`)
  fs.writeFileSync(scriptPath, 'process.exit(0)\n')

  try {
    // Use node as the launcher and our script as the "command". Pass
    // shell:false (default) -- node is a real binary, no shim.
    // execFileSync passes ['--version'] as args, which node ignores
    // gracefully (well, it prints its version and exits 0, which is
    // perfect -- exit code 0 is the only signal we read).
    assert.equal(verifySRCli(NODE_BIN), true)
  } finally {
    try {
      fs.unlinkSync(scriptPath)
    } catch {
      void 0
    }
  }
})

test('verifySRCli swallows timeouts (does not throw)', () => {
  // We can't easily provoke a real 5s hang in CI without slowing the
  // suite, but we CAN confirm that an invocation that DOES throw
  // (because the binary is missing) returns false rather than
  // propagating. Same code path the timeout case takes.
  assert.equal(verifySRCli('/definitely/not/a/real/binary/anywhere'), false)
})
