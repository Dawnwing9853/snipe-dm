---
name: snipe-dm
description: Send a Facebook/Messenger/Instagram DM from the user's normal Edge at an exact GMT+7 time by pressing the real Enter key on time. Usage /snipe-dm 00.00 (pre-typed message) or /snipe-dm "message" "00.00" (script types it). /snipe-dm feedback = report last run.
argument-hint: "[\"message\"] <time GMT+7, e.g. 00.00> | feedback"
disable-model-invocation: true
---

# snipe-dm

Presses Enter at an exact GMT+7 time into the user's normal Microsoft Edge, so a message they already typed is sent on the dot. Script: `<skill dir>\press_at.py`.

`<skill dir>` below means the "Base directory for this skill" path shown when this skill loads; substitute it literally (terminal commands can't expand variables).

What the script does: fixes the PC clock against time.google.com (NTP), re-measures 15 s before, measures one-way delay to the active tab's chat server (`edge-chat.instagram.com` for an Instagram tab, else `edge-chat.messenger.com`) and presses that much early, busy-waits the last second. Refuses to type or press unless the focused window is Edge and its active tab is Facebook, Messenger or Instagram (DMs). It can't see which person's chat is open, so remind the user to check the chat header. No Playwright, no login.

## Steps

1. Parse `$ARGUMENTS`. Time is always GMT+7, next occurrence (`00.00`, `0:00`, `23:05`, `23:05:30`).
   - `feedback` (or ผล / result): don't arm anything, go straight to step 4 for the latest run's terminal tab.
   - `<time>` only (default): the user typed the message in Edge themself; the script only presses Enter.
   - `"message" "time"` (quotes optional: last token that looks like a time is the time, everything before it is the message): the script types the message itself 10 s before, then presses Enter on time.
     Write the message exactly as given (UTF-8, newlines kept) with the Write tool to
     `<skill dir>\message.txt` (overwrite).
     Terminal commands must be ASCII, so never put the message on the command line.
   - No time given: ask for it.
2. Load `mcp__terminal__run_in_terminal` with ToolSearch if needed, then start it in a terminal tab:
   `python "<skill dir>\press_at.py" <time>`
   With a message, add: `--msg-file "<skill dir>\message.txt"`
   Extra flag only if the user asks: `--early 0` (never send before the time) or `--early <ms>`.
3. Read the tab once (`read_terminal`, wait ~4 s), then write this to the user right away as text (it shows while the turn keeps running), in Thai, short:
   - target time and how many minutes away (warn if under 2 min: not enough time to switch)
   - with a message: show the message the script read (the `Message:` line) so they can check it
   - now: go to Edge, open the chat, click inside the message box (default mode: message already typed; message mode: box can be empty, whatever is in it gets replaced), leave Edge in front, don't touch the PC or let it sleep/lock until after the time
   - say you'll post the result here by yourself right after it sends.
   Don't end the turn. A running turn doesn't take focus from Edge.
   Before starting, close finished tabs from earlier runs (`stop_terminal_tab` with `close: true`); the app refuses new tabs past 6.
4. Keep calling `read_terminal` on that tab (`wait_for_output_ms` up to 280000, since the call times out at 300 s; repeat until done) until a line starting with `Enter pressed` or `Stopped:` appears, or the shell prompt comes back. Then report without being asked: `Enter pressed` time, estimated arrival (press + early ms), clock offset, the server delay was measured to, and the window/tab it pressed into, as a short table. If `Stopped:`, explain why (front window wasn't Edge, or active tab wasn't a chat site) and offer to re-arm.
   If the target is more than ~60 min away, tell the user you'll stop watching, end the turn, and they can run `/snipe-dm feedback` later.

## Notes for the report
- Estimated arrival = time the Meta server got it, which is the timestamp both sides see. Server processing adds a few tens of ms we can't measure.
- Delay to the recipient's device (their network, app closed/push) is outside our control.
- Exact server time: Facebook "Download your information" → Messages JSON → `timestamp_ms`.
