# Changes

## 1.0.4

- Notifications with the `transient` hint are shown but never written to the popup or history files.
- A sender that adds the `transient` hint in an update also has the earlier stored copy removed.
- Showing history leaves a `transient` notification on screen instead of replacing it with a copy whose images were never saved, also when it turned transient while history was loading.
- Clicking a notification whose app closes it while running the action no longer removes the toast next to it.
- A notification closed by its sender leaves the screen instead of staying until its countdown ends.
- Showing history no longer dismisses a notification that arrived while history was loading.
- The running service and the enable script now report and check 1.0.4.
- Body hyperlinks are no longer advertised, since the card does not open them.

- Show the × button's tooltip and accessible name in English, or in Chinese when the system locale is Chinese; it was always Chinese.

## 1.0.3

- Remove the exact Notification Center entry after left-clicking a popup, preserving its existing open action.
- Add an always-visible × button that removes the popup and center entry without opening anything.
- Keep right-click dismissal and automatic expiry in history.
- Send center removal after queued persistence finishes so delayed writes cannot recreate the removed source file.
- Add regression coverage for action routing, exact-key removal, real QML mouse clicks, short/long card layouts and hover pause state.

## 1.0.2

- Send notification JSON and image-copy metadata through stdin instead of process arguments.
- Centralize persistence in a private, atomic storage helper with 0700 directories and 0600 files.
- Repair existing history, image copies and legacy settings before reads/writes; refuse unsafe links.
- Keep bounded image copying, serialized jobs, history trimming, restore and DND behavior.
- Add permission migration, failure, payload round-trip and real Quickshell stdin/argv regression tests.

## 1.0.1

- Share one countdown per notification across all screens; hovering any copy pauses every view.
- Release hover registrations when a screen/delegate disappears or changes clocks.
- Identify the running implementation through a dedicated IPC response; stock pings and old versions no longer pass activation checks.
- Document the shell restart required after updating keepLoaded services.
- Add actual QML timer/lifecycle and model-wiring tests, plus helper activation regression tests.
