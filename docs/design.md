# Design notes

## Threading model

- The HTTP server (`ThreadingHTTPServer`) runs in a background thread, spawning a handler thread per request.
- `bpy` is main-thread-only, so all script execution happens via `bpy.app.timers` (which fires callbacks on the main thread).
- HTTP threads enqueue jobs into a thread-safe queue. The executor (timer callback on the main thread) pulls and runs them.
- **Sync POST**: the HTTP handler thread blocks on a `threading.Condition` until the executor signals completion, then builds and sends the response.
- **SSE stream**: the HTTP handler thread waits on the condition with timeout, sending new events as they arrive, until the job reaches a terminal status.

## Why timer-driven, not threads?

`bpy` operations crash if called from a non-main thread. Timers are Blender's idiomatic way to run code "later" on the main thread without blocking other operations. The interval between ticks is exactly when Blender redraws and processes UI events — which is the responsiveness we want.

## Why generators?

A generator script makes "step" a first-class concept without imposing decorators or framework boilerplate. The author writes ordinary Python and just `yield`s between logical steps. The yielded value is a step label — surfaced as a `step` event for live UIs.

## Why SSE over WebSocket?

- SSE is one-way (server → client), which matches the data flow.
- SSE is just chunked HTTP — works with `curl -N`, no extra dependencies.
- Cancel is a separate `DELETE` request, not a message on the socket.

## Limitations (v0.1)

- One job runs at a time. Additional submissions queue.
- Cancel is cooperative — the script only stops between yields. A long, non-yielding step still blocks until it finishes.
- Result capture in generator mode is not yet implemented (returns `null`). Sync mode captures the last expression.
- No authentication. Server binds to `127.0.0.1` by default — do **not** expose to a network without adding auth.
- No persistence — events are kept in memory; restarting the server loses history.
- Trim policy: at most 50 jobs retained in memory; older entries dropped.
