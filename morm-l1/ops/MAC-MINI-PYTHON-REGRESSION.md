# Mac Mini Python 3.11.15 / macOS Tahoe regression — physical 3-node test blocked

## Symptom

Running `morm_l1.cli node` on the Mac Mini (192.168.2.122, macOS 25.4.0
Darwin "Tahoe", Python 3.11.15 from Homebrew) **silently fails to bind RPC**:

- The Python process starts and is alive (`ps` shows it).
- A producer thread runs and writes blocks to `state.db` (the WAL grows).
- TCP socket appears momentarily then transitions to `CLOSED`.
- `stdout`/`stderr` produce **zero output** — not even the `[node] running ...`
  print line that comes before `serve_forever()`.
- Reproducible via three launch paths: `nohup ... &disown`, foreground SSH,
  `launchctl` LaunchAgent.

When launched via LaunchAgent, the err.log captures:

```
Exception ignored error evaluating path:
Traceback (most recent call last):
  File "<frozen getpath>", line 353, in <module>
InterruptedError: [Errno 4] Interrupted system call
Fatal Python error: error evaluating path
Python runtime state: core initialized
```

Same Python binary, same venv, runs `morm_l1.cli keygen` and arbitrary
imports just fine. Only the long-lived `node` command (which constructs
`ThreadingHTTPServer`) trips the failure.

## Hypothesis

Python 3.11.x `<frozen getpath>` issues `os.scandir` during interpreter
startup. On macOS Sequoia/Tahoe + APFS + Apple Silicon there's a known
class of EINTR delivery against filesystem syscalls when SIGCHLD or
similar signals fire concurrently. The producer thread we start before
`server.serve_forever()` may be triggering exactly that race.

Fixed in Python 3.12+ (signal-handling robustness in startup paths).
Not fixed in 3.11.15.

## Workarounds (untried — for next session)

1. **Upgrade to Python 3.12** on Mac Mini and rebuild the venv:
   ```sh
   ssh user@192.168.2.122 'brew install python@3.12'
   ssh user@192.168.2.122 'cd ~/Desktop/MORM/morm-l1 && rm -rf .venv && \
     /opt/homebrew/bin/python3.12 -m venv .venv && .venv/bin/pip install cryptography'
   ```
2. **Build Python from source** with the EINTR retry patch.
3. **Use a different bind path**: bind the socket *first* (before producer
   thread starts), then call `start_producer()` and `serve_forever()`. The
   relevant edit is in `morm-l1/morm_l1/cli.py:cmd_node` — swap the order:

   ```python
   server = RpcServer((args.host, args.port), Handler)
   server.node = node
   node.start_producer()           # ← move down
   print(f"[node] running. ...")
   server.serve_forever()
   ```

## Impact

- Phase 23a is fully validated on **localhost** (3 processes), per
  `3NODE-TESTNET.md`.
- Cross-machine LAN gossip is **not yet validated** with the latest code.
  The previously claimed "MacBook + Mac Mini 2-node sync" in the project
  memory was on pre-Phase 18 code (the `0x` address era) and has not been
  reproduced after this session's fixes.
- Three-physical-machine demo deferred until either Python upgrade or the
  cli ordering fix lands and is verified on Mac Mini.
