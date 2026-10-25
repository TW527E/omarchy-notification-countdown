from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node.js is required')
class HandledNotificationTests(unittest.TestCase):
    def test_click_removes_only_its_entry_after_archiving(self):
        root = Path(__file__).resolve().parents[1]
        script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('../Service.qml', 'utf8');
function fixture(restored = false) {
  const clicked = {timestamp: 100, originalId: 1, app: 'Chat', execArgv: ''};
  const rows = [clicked, {timestamp: 200, originalId: 2, app: 'Chat'}];
  const jobs = [], ipc = [], actions = [], focused = [], dismissed = [];
  const ref = {tracked: true, actions: [], dismiss() { dismissed.push(1); },
    expire() { dismissed.push('expired'); }};
  const state = vm.createContext({
    NotificationLogic: require('../NotificationLogic.js'),
    popupModel: {get count() { return rows.length; }, get(i) { return rows[i]; },
      remove(i) { rows.splice(i, 1); }},
    liveRefs: {1: ref}, restoredPopups: restored ? {'100-1.json': true} : {},
    historyLimit: 10, console,
    enqueuePopupFileJob(action, payload, done) { jobs.push({action, payload, done}); },
    Quickshell: {execDetached(argv) { ipc.push(Array.from(argv)); }},
    Util: {execArgv(argv) { actions.push(Array.from(argv)); }},
    focusApp(entry) { focused.push(entry); }
  });
  for (const name of ['isRestoredRow', 'dismissPopup', 'expirePopup', 'removePopup',
                      'invokePopupDefault', 'archivePopupFileFor']) {
    const start = source.indexOf(`  function ${name}(`);
    assert.notEqual(start, -1);
    vm.runInContext(source.slice(start, source.indexOf('\n  }', start) + 4), state);
  }
  return {state, clicked, rows, jobs, ipc, actions, focused, dismissed, ref};
}
for (const mode of ['argv', 'live', 'focus', 'restored']) {
  const f = fixture(mode === 'restored');
  if (mode === 'argv' || mode === 'restored') f.clicked.execArgv = '["open-app","a b"]';
  f.ref.actions = [{identifier: 'default', invoke() { f.actions.push(['live']); }}];
  if (mode === 'focus') f.ref.actions = [];
  f.state.invokePopupDefault(0);
  assert.equal(f.rows.length, 1);
  assert.equal(f.rows[0].originalId, 2);
  assert.equal(f.ipc.length, 0, 'wait for queued persistence');
  assert.equal(f.jobs[0].payload.name, '100-1.json');
  f.jobs[0].done();
  assert.deepEqual(f.ipc, [['omarchy-shell', '-q', 'foamy.notification-center.store', 'remove', '100-1']]);
  assert.equal(f.focused.length, mode === 'focus' ? 1 : 0);
  assert.deepEqual(f.actions, mode === 'focus' ? [] : [mode === 'live' ? ['live'] : ['open-app', 'a b']]);
  assert.equal(f.dismissed.length, mode === 'restored' ? 0 : 1);
}
for (const method of ['dismissPopup', 'expirePopup']) {
  const f = fixture();
  f.state[method](0);
  assert.equal(f.jobs[0].action, 'archive');
  assert.equal(f.jobs[0].done, null);
  assert.equal(f.ipc.length, 0);
}
const removed = fixture();
removed.state.removePopup(0, 'handled');
removed.jobs[0].done();
assert.equal(removed.ipc[0][4], '100-1');
assert.equal(removed.actions.length, 0, 'the close button must not open the notification');
assert.equal(removed.focused.length, 0);
const f = fixture();
f.state.invokePopupDefault(-1);
f.state.invokePopupDefault(2);
assert.equal(f.jobs.length, 0);
f.clicked.originalId = -1;
f.state.invokePopupDefault(0);
assert.equal(f.jobs[0].done, null, 'empty-history placeholder is not a stored notification');
'''
        result = subprocess.run(['node', '-e', script], cwd=root / 'tests',
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
