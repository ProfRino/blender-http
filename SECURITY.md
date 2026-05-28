# Security Policy

## What this add-on does

Blender HTTP runs a small HTTP server inside Blender. **Anyone who can send a `POST` to the server can execute arbitrary Python inside Blender** — including reading and writing files anywhere the Blender process can reach, calling shell commands via `subprocess`, and modifying any open `.blend` file.

That is the add-on's purpose. It is not a sandbox. Treat the server as if it were a remote shell.

## Threat model

| Who | Can do |
|---|---|
| Anyone with TCP access to the server's bound address and port | Execute Python in Blender, read/write files, exfiltrate data, modify the open scene |
| Anyone who can send you a script to "just run" | Same as above, once you POST it |
| Anyone on the local machine (other user accounts, malware) | Reach `127.0.0.1:9876` like any other localhost service |

There is **no authentication, no script sandboxing, no allow-list, no rate limit**. Network isolation and your judgement are the only defences.

## Safe defaults (and how to keep them safe)

- **The server binds to `127.0.0.1` by default.** This restricts access to processes on the same machine. Do **not** change the host to `0.0.0.0` or a LAN address unless you understand the consequences.
- **The default port `9876` has no protection.** Anything on your machine that opens a TCP connection to it gets full code execution.
- **`OUTPUT` is a convention, not a boundary.** Scripts can write anywhere the Blender process has permission. The `OUTPUT` path is just a sensible default — it's not enforced.

## Recommended practice

1. **Keep the host as `127.0.0.1`.** If you need remote access, use SSH port-forwarding or a VPN — do not expose the port directly.
2. **Don't run Blender as Administrator / root.** A compromise inherits Blender's privileges.
3. **Review scripts before sending them.** Treat code from an agent the same way you'd treat code from a stranger.
4. **Disable the add-on when not in use.** Stop the server (N-panel → HTTP → Stop) or disable the add-on entirely if you're not actively using it.
5. **Don't commit scripts that hardcode credentials or absolute paths to private files.**
6. **Be careful with `OUTPUT`.** Audits, snapshots, and saved `.blend` files land there — make sure that directory does not contain anything sensitive you don't want overwritten.

## Reporting a vulnerability

If you find a security issue, please **do not open a public GitHub issue**.

Use [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) on this repo, or email the maintainer listed in `blender_http/blender_manifest.toml`.

I'll respond as time permits — this is a personal project, not a commercial product. No bounty.

## Supported versions

| Version | Supported |
|---|---|
| 0.4.x | ✅ current |
| < 0.4 | ❌ not maintained |

## Out of scope

The following are **not** considered vulnerabilities and won't be addressed:

- Arbitrary code execution via the documented HTTP API (this is the API's purpose)
- DoS via heavy scripts (Blender is single-threaded; submit lighter scripts)
- The add-on writing files outside `OUTPUT` when a script tells it to (the script is in control)
- A user setting the host to `0.0.0.0` and getting exploited (don't do that)
