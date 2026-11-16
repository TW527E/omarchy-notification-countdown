from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node.js is required')
class LiveNotificationPathTests(unittest.TestCase):
    """Runs the real handleNotification/refreshPopup/invokePopupDefault code."""

    def run_script(self, body):
        root = Path(__file__).resolve().parents[1]
        script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('../Service.qml', 'utf8');
function signal() {
  const slots = [];
  return {connect(f) { slots.push(f); }, emit() { for (const f of slots.slice()) f(); }};
}
function notification(id, fields = {}) {
  const n = {id, appName: 'Chat', summary: 'hi', body: '', hints: {}, expireTimeout: 0,
    tracked: false, actions: [], closed: signal(), dismiss() { n.closed.emit(); }};
  for (const name of ['summaryChanged', 'bodyChanged', 'hintsChanged']) n[name] = signal();
  return Object.assign(n, fields);
}
function fixture() {
  const rows = [], jobs = [], ipc = [];
  const state = vm.createContext({
    NotificationLogic: require('../NotificationLogic.js'),
    NotificationUrgency: {Normal: 1, Critical: 2},
    Qt: {callLater(f) { f(); }},
    popupModel: {get count() { return rows.length; }, get(i) { return rows[i]; },
      remove(i) { rows.splice(i, 1); }, insert(i, row) { rows.splice(i, 0, Object.assign({}, row)); },
      setProperty(i, k, v) { rows[i][k] = v; }},
    liveRefs: {}, restoredPopups: {}, transientPopups: {}, invokingPopups: {},
    doNotDisturb: false, historyLimit: 10, imagesDir: '/tmp/images/', console,
    updateSignals: ['summaryChanged', 'bodyChanged', 'hintsChanged'],
    enqueuePopupFileJob(action, payload, done) { jobs.push({action, payload}); if (done) done(); },
    Quickshell: {execDetached(argv) { ipc.push(Array.from(argv)); }},
    Util: {execArgv() {}}, focusApp() {}
  });
  vm.runInContext('var service = this', state);
  for (const name of ['shouldBypassDnd', 'snapshotOf', 'isTransient', 'isEphemeral',
                      'handleNotification', 'watchForUpdates', 'refreshPopup', 'isRestoredRow',
                      'removePopupsByOriginalId', 'removeClosedPopup', 'removePopup',
                      'invokePopupDefault', 'persistPopupFile', 'deletePopupFileFor',
                      'archivePopupFileFor']) {
    const start = source.indexOf(`  function ${name}(`);
    assert.notEqual(start, -1, name);
    vm.runInContext(source.slice(start, source.indexOf('\n  }', start) + 4), state);
  }
  return {state, rows, jobs, ipc};
}
''' + body
        result = subprocess.run(['node', '-e', script], cwd=root / 'tests',
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_clicking_a_live_default_action_removes_only_that_popup(self):
        self.run_script(r'''
const f = fixture();
const first = notification(1), second = notification(2);
f.state.handleNotification(first);
f.state.handleNotification(second);   // newest first: rows = [2, 1]
// Quickshell closes a non-resident notification while the action runs.
second.actions = [{identifier: 'default', invoke() { second.closed.emit(); }}];
f.state.invokePopupDefault(0);
assert.deepEqual(f.rows.map(r => r.originalId), [1], 'the other toast stays');
const removed = f.ipc.filter(a => a[3] === 'remove').map(a => a[4]);
assert.equal(removed.length, 1);
assert.match(removed[0], /-2$/, 'the clicked notification is removed as handled');
''')

    def test_a_replacement_that_turns_transient_is_not_kept_on_disk(self):
        self.run_script(r'''
const f = fixture();
const n = notification(5);
f.state.handleNotification(n);
const name = f.jobs.find(j => j.action === 'popup').payload.name;
n.hints = {transient: true};
n.summary = 'one-time code 123456';
n.hintsChanged.emit();
n.summaryChanged.emit();
assert.ok(f.jobs.some(j => j.action === 'delete' && j.payload.name === name), 'earlier file deleted');
const after = f.jobs.slice(f.jobs.findIndex(j => j.action === 'delete'));
assert.ok(!after.some(j => j.action === 'popup'), 'new content never written');
assert.equal(f.rows[0].summary, 'one-time code 123456', 'still shown');
f.state.removePopup(0, 'dismiss');
assert.ok(!f.jobs.some(j => j.action === 'archive'), 'nothing archived to history');
''')
