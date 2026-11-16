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
    liveRefs: {}, restoredPopups: {}, transientPopups: {}, invokingPopups: {}, replayCarryOver: [],
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

    def test_history_replay_leaves_a_transient_toast_alone(self):
        self.run_script(r'''
const f = fixture();
for (const name of ['liveRowsForReplay', 'showRecentHistory']) {
  const start = source.indexOf(`  function ${name}(`);
  vm.runInContext(source.slice(start, source.indexOf('\n  }', start) + 4), f.state);
}
Object.assign(f.state, {storageFailed: false, readHistoryProc: {running: false},
  historyReadQueued: false, enqueueHistoryRead() {}});
f.state.handleNotification(notification(1, {image: '/tmp/sender/one.png'}));
f.state.handleNotification(notification(2, {hints: {transient: true}, image: '/tmp/sender/code.png'}));
f.state.showRecentHistory();
const carried = Array.from(f.state.replayCarryOver, r => r.originalId);
assert.deepEqual(carried, [1], 'only the stored toast is carried into the replay');
const cleared = Object.keys(f.state.replayClearNames);
assert.equal(cleared.length, 1);
assert.match(cleared[0], /-1\.json$/, 'the transient toast is not cleared');
''')

    def test_a_toast_that_turns_transient_during_the_history_read_stays(self):
        self.run_script(r'''
const f = fixture();
for (const name of ['liveRowsForReplay', 'showRecentHistory', 'replayHistory', 'dismissPopup']) {
  const start = source.indexOf(`  function ${name}(`);
  vm.runInContext(source.slice(start, source.indexOf('\n  }', start) + 4), f.state);
}
Object.assign(f.state, {storageFailed: false, readHistoryProc: {running: false},
  historyReadQueued: false, enqueueHistoryRead() {}, replayCarryOver: [], replayClearNames: {}});
f.rows.append = row => f.rows.push(Object.assign({}, row));
f.state.popupModel.append = f.rows.append;
const n = notification(7, {image: '/tmp/sender/seven.png'});
f.state.handleNotification(n);
f.state.showRecentHistory();            // the read is now in flight
n.hints = {transient: true};
n.summary = 'one-time code 654321';
n.hintsChanged.emit();
n.summaryChanged.emit();
f.state.replayHistory('');              // the read lands
const live = f.rows.filter(r => r.originalId === 7);
assert.equal(live.length, 1, 'no restored copy next to the live toast');
assert.equal(live[0].summary, 'one-time code 654321', 'the live, updated toast is the one kept');
assert.ok(!f.state.restoredPopups[Object.keys(f.state.transientPopups)[0]], 'not marked as restored');
''')

    def test_a_silenced_notification_that_turns_transient_is_taken_out_of_history(self):
        self.run_script(r'''
const f = fixture();
for (const name of ['writeSilenced', 'releaseSilenced', 'writeHistoryFile']) {
  const start = source.indexOf(`  function ${name}(`);
  vm.runInContext(source.slice(start, source.indexOf('\n  }', start) + 4), f.state);
}
// Hold the history write so the update lands while it is queued.
const queued = [];
f.state.enqueuePopupFileJob = (action, payload, done) => { f.jobs.push({action, payload}); queued.push(done); };
const n = notification(9, {image: '/tmp/sender/nine.png', tracked: true});
const written = f.state.snapshotOf(n);
f.state.writeSilenced(n, written);
n.hints = {transient: true};
n.summary = 'one-time code 111222';
queued.shift()();                       // the history write finishes
assert.deepEqual(f.jobs.map(j => j.action), ['history', 'forget'], 'the written entry is taken back');
assert.equal(f.jobs[1].payload.name, f.jobs[0].payload.name);
assert.equal(n.tracked, true, 'released only after the entry is gone');
queued.shift()();
assert.equal(n.tracked, false);
''')

    def test_a_toast_that_turns_transient_and_closes_during_the_history_read_stays_out(self):
        self.run_script(r'''
const f = fixture();
for (const name of ['liveRowsForReplay', 'showRecentHistory', 'replayHistory', 'dismissPopup']) {
  const start = source.indexOf(`  function ${name}(`);
  vm.runInContext(source.slice(start, source.indexOf('\n  }', start) + 4), f.state);
}
Object.assign(f.state, {storageFailed: false, readHistoryProc: {running: false},
  historyReadQueued: false, enqueueHistoryRead() {}, replayCarryOver: [], replayClearNames: {}});
f.state.popupModel.append = row => f.rows.push(Object.assign({}, row));
const n = notification(8, {image: '/tmp/sender/eight.png'});
f.state.handleNotification(n);
f.state.showRecentHistory();            // the read is now in flight
n.hints = {transient: true};
n.hintsChanged.emit();
f.state.removePopup(0, 'dismiss');      // closed before the read lands
f.state.replayHistory('');
assert.ok(!f.rows.some(r => r.originalId === 8), 'the old snapshot does not come back');
''')
