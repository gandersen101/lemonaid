# Minor

#### Added

- **`brief handoff --to` the lemon's own harness gives it a fresh session in the same pane.** The new session takes the brief, the inbox name and the pins, as a handoff to the other harness does.
- **`/clear` in a Claude lemon moves the brief, the inbox name and the pins to the new session, and archives the old row.** The new session's push scout starts at once. This needs the `SessionEnd` hook (`lemonaid claude hooks --session-end`) and both `SessionStart` hooks (`lemonaid claude hooks` and `lemonaid hooks install`).

#### Fixed

- **`--channel` on `brief` commands accepts a Claude channel with the whole session ID**, such as `claude:6f3198c7-1111-4222-8333-444444444444`. It used to accept only the first 8 characters.
