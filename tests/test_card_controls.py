import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('quickshell') and Path('/usr/share/omarchy/shell/Ui').exists(),
                     'Omarchy and Quickshell are required')
class CardControlTests(unittest.TestCase):
    def test_close_button_does_not_activate_card(self):
        with tempfile.TemporaryDirectory(prefix='nc-card-') as directory:
            base = Path(directory)
            for name in ('Commons', 'Ui'):
                (base / name).symlink_to('/usr/share/omarchy/shell/' + name, target_is_directory=True)
            capture = os.environ.get('NOTIFICATION_TEST_CAPTURE', '')
            (base / 'shell.qml').write_text('''import QtQuick
import QtTest
import Quickshell
import "%s/components" as Plugin
ShellRoot {
 FloatingWindow {
  id: window
  visible: true
  implicitWidth: 430
  implicitHeight: 210
  color: "#1f1f28"
  property bool ready: false
  Timer { interval: 200; running: true; onTriggered: window.ready = true }
  Plugin.NotificationCard {
   id: card
   x: 20; y: 20
   width: implicitWidth; height: implicitHeight
   summary: "通知測試：左鍵開啟，× 直接移除"
   body: "右鍵與自動逾時仍會保留在通知中心。"
   lifetime: 8000; remainingLifetime: 0.65
   property int opened: 0
   property int dismissed: 0
   property int removed: 0
   onCardClicked: opened++
   onCloseRequested: dismissed++
   onRemoveRequested: removed++
  }
  TestCase {
   name: "NotificationCardControls"
   when: window.ready
   onCompletedChanged: if (completed) console.log("CARD_CONTROLS", qtest_results.failCount, "failed")
   function test_close_and_body_are_separate() {
    var button = findChild(card, "removeNotification")
    verify(button !== null)
    verify(button.visible && button.width >= 24 && button.height >= 24)
    mouseClick(button, button.width / 2, button.height / 2, Qt.LeftButton)
    compare(card.removed, 1); compare(card.opened, 0); compare(card.dismissed, 0)
    mouseClick(card, 10, card.height / 2, Qt.LeftButton)
    compare(card.opened, 1); compare(card.removed, 1)
    mouseClick(card, 10, card.height / 2, Qt.RightButton)
    compare(card.dismissed, 1); compare(card.removed, 1)
    mouseMove(button, button.width / 2, button.height / 2)
    tryCompare(card, "hovered", true)
    var point = button.mapToItem(card, 0, 0)
    verify(point.x >= 0 && point.x + button.width <= card.width)
    verify(point.y >= 0 && point.y + button.height <= card.height)
    var capture = %s
    if (capture) {
     var saved = false
     verify(card.grabToImage(function(image) { saved = image.saveToFile(capture) }))
     tryVerify(function() { return saved })
    }
    card.body = ""; card.summary = "短通知"; wait(50)
    verify(button.visible)
    mouseClick(button, button.width / 2, button.height / 2, Qt.LeftButton)
    compare(card.removed, 2); compare(card.opened, 1)
   }
  }
 }
}
''' % (ROOT.as_uri(), json.dumps(capture)))
            runtime = base / 'run'
            runtime.mkdir(mode=0o700)
            env = dict(os.environ, HOME=str(base / 'home'), XDG_RUNTIME_DIR=str(runtime),
                       XDG_CONFIG_HOME=str(base / 'config'), XDG_STATE_HOME=str(base / 'state'),
                       XDG_CACHE_HOME=str(base / 'cache'), QT_QPA_PLATFORM='offscreen',
                       QT_QUICK_BACKEND='software', QT_QPA_PLATFORMTHEME='', QT_STYLE_OVERRIDE='Fusion')
            for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'HYPRLAND_INSTANCE_SIGNATURE'):
                env.pop(key, None)
            result = subprocess.run(['dbus-run-session', '--', 'quickshell', '-p', str(base), '--no-color'],
                                    env=env, text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('CARD_CONTROLS 0 failed', result.stdout + result.stderr)
