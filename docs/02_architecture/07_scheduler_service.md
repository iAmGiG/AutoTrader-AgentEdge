# Scheduler Background Service Architecture

## Overview

Design for a self-managing background scheduler service that can be started/stopped from the CLI and automatically terminates when no longer needed.

**Status:** DESIGN PHASE (not yet implemented)

## Goals

1. **Start/stop from CLI** - No manual `python main.py --daemon` needed
2. **Self-terminating** - Shuts down gracefully when disabled or idle
3. **Process isolation** - Runs independently of main CLI
4. **Health monitoring** - Detects and recovers from crashes
5. **Resource efficient** - Minimal CPU/memory when idle

## Architecture Options

### Option 1: Subprocess with PID Management

**Approach:** CLI spawns subprocess, tracks PID

```python
# Start service
import subprocess
process = subprocess.Popen(['python', 'main.py', '--daemon-background'])
with open('.scheduler.pid', 'w') as f:
    f.write(str(process.pid))

# Stop service
with open('.scheduler.pid', 'r') as f:
    pid = int(f.read())
os.kill(pid, signal.SIGTERM)
```

**Pros:**
- Simple implementation
- Standard Python libraries
- Works cross-platform

**Cons:**
- PID file can become stale
- No automatic restart on crash
- Parent/child relationship issues

### Option 2: systemd/launchd Integration (Linux/Mac)

**Approach:** Register as system service

**systemd (Linux):**
```ini
# /etc/systemd/system/trading-scheduler.service
[Unit]
Description=AutoGen Trading Scheduler
After=network.target

[Service]
Type=simple
User=trader
WorkingDirectory=/path/to/AutoTrader-AgentEdge
ExecStart=/usr/bin/python main.py --daemon
Restart=on-failure
RestartSec=30s

[Install]
WantedBy=multi-user.target
```

**Control from CLI:**
```python
import subprocess
subprocess.run(['systemctl', '--user', 'start', 'trading-scheduler'])
subprocess.run(['systemctl', '--user', 'stop', 'trading-scheduler'])
subprocess.run(['systemctl', '--user', 'status', 'trading-scheduler'])
```

**Pros:**
- Automatic restart on crash
- System-level monitoring
- Proper logging integration
- Runs at boot (optional)

**Cons:**
- Platform-specific (systemd, launchd, Windows Service)
- Requires initial setup
- Elevated permissions for install

### Option 3: Supervisor Process (Recommended)

**Approach:** Dedicated supervisor daemon that manages scheduler lifecycle

```
┌─────────────────────┐
│   Trading CLI       │
│                     │
│  /schedule start    │──┐
│  /schedule stop     │  │
└─────────────────────┘  │
                         │ IPC (socket/file)
                         ↓
┌─────────────────────────────────┐
│  Supervisor Daemon              │
│  (Always running, lightweight)  │
│                                 │
│  - Monitors state file          │
│  - Spawns scheduler on demand   │
│  - Watches for crashes          │
│  - Handles shutdown signals     │
└─────────────────────────────────┘
         │
         │ spawns/monitors
         ↓
┌─────────────────────┐
│  Scheduler Worker   │
│                     │
│  - Runs routines    │
│  - Self-terminates  │
│    when disabled    │
└─────────────────────┘
```

**Implementation:**
```python
# src/cli/scheduler_supervisor.py
class SchedulerSupervisor:
    """Lightweight supervisor for scheduler lifecycle."""

    def __init__(self):
        self.state_file = Path('state/scheduler.state')
        self.pid_file = Path('state/scheduler.pid')
        self.worker_process = None

    def run(self):
        """Main supervisor loop."""
        while True:
            state = self._load_state()

            if state['enabled'] and not self._is_worker_running():
                self._start_worker()
            elif not state['enabled'] and self._is_worker_running():
                self._stop_worker()

            time.sleep(10)  # Check every 10s

    def _start_worker(self):
        """Spawn scheduler worker process."""
        self.worker_process = subprocess.Popen(
            ['python', '-m', 'src.trading.scheduler_worker'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self.pid_file.write_text(str(self.worker_process.pid))

    def _stop_worker(self, timeout=30):
        """Gracefully stop worker."""
        if self.worker_process:
            self.worker_process.terminate()
            try:
                self.worker_process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.worker_process.kill()

    def _is_worker_running(self):
        """Check if worker is alive."""
        if not self.pid_file.exists():
            return False

        pid = int(self.pid_file.read_text())
        try:
            os.kill(pid, 0)  # Doesn't kill, just checks
            return True
        except OSError:
            return False
```

**CLI Integration:**
```python
# In scheduler_cli.py
def start_service(self):
    """Start scheduler background service."""
    # Update state file to enabled=true
    state = {'enabled': True, 'start_time': datetime.now().isoformat()}
    with open('state/scheduler.state', 'w') as f:
        json.dump(state, f)

    # Supervisor will pick up change within 10s
    print("✅ Scheduler service starting...")
    print("   Supervisor will activate within 10 seconds")

def stop_service(self):
    """Stop scheduler background service."""
    state = {'enabled': False, 'stop_time': datetime.now().isoformat()}
    with open('state/scheduler.state', 'w') as f:
        json.dump(state, f)

    print("❌ Scheduler service stopping...")
    print("   Worker will terminate gracefully")
```

**Pros:**
- Cross-platform (pure Python)
- No root/admin needed
- Lightweight (supervisor sleeps most of the time)
- Automatic crash recovery
- Clean shutdown

**Cons:**
- Requires supervisor to always run
- 10s delay for state changes

## Self-Termination Logic

### Worker Self-Termination

**Trigger Conditions:**
1. Config `enabled: false` detected
2. No scheduled runs in next 24 hours
3. Consecutive failures exceed threshold
4. Manual shutdown signal

**Implementation:**
```python
# src/trading/scheduler_worker.py
class SchedulerWorker:
    """Self-managing scheduler worker."""

    async def run(self):
        """Main worker loop with self-termination."""
        while True:
            # Check if should terminate
            if self._should_terminate():
                logger.info("Worker self-terminating")
                self._cleanup_and_exit()
                break

            # Check if it's time to run
            if self._is_scheduled_time():
                await self._execute_routine()

            await asyncio.sleep(60)  # Check every minute

    def _should_terminate(self) -> bool:
        """Check termination conditions."""
        config = self._load_config()

        # 1. Disabled in config
        if not config.get('enabled', False):
            return True

        # 2. No upcoming runs (rare edge case)
        if not self._has_upcoming_runs():
            return True

        # 3. Too many consecutive failures
        if self.consecutive_failures >= config.get('max_consecutive_failures', 5):
            return True

        return False

    def _cleanup_and_exit(self):
        """Clean shutdown."""
        # Save final state
        self._save_execution_log()

        # Clear PID file
        if self.pid_file.exists():
            self.pid_file.unlink()

        # Flush logs
        logging.shutdown()

        sys.exit(0)
```

## Health Monitoring

### Heartbeat File

Worker updates heartbeat every minute:

```python
# Worker
def _update_heartbeat(self):
    heartbeat = {
        'timestamp': datetime.now().isoformat(),
        'status': 'running',
        'last_execution': self.last_execution_time,
        'next_execution': self.next_execution_time
    }
    with open('state/scheduler.heartbeat', 'w') as f:
        json.dump(heartbeat, f)

# Supervisor checks heartbeat
def _check_worker_health(self):
    if not Path('state/scheduler.heartbeat').exists():
        return False

    with open('state/scheduler.heartbeat') as f:
        heartbeat = json.load(f)

    last_beat = datetime.fromisoformat(heartbeat['timestamp'])
    age = (datetime.now() - last_beat).total_seconds()

    # Worker should update every 60s, allow 120s grace
    return age < 120
```

### Crash Recovery

Supervisor detects crash and restarts:

```python
def _monitor_worker(self):
    """Monitor and restart if crashed."""
    if not self._check_worker_health():
        logger.warning("Worker appears unhealthy, restarting...")
        self._stop_worker()
        time.sleep(5)  # Brief pause
        self._start_worker()
```

## CLI Commands

### New Scheduler CLI Commands

```
Scheduler> service start    - Start background service
Scheduler> service stop     - Stop background service
Scheduler> service status   - Show service health
Scheduler> service restart  - Restart service
```

**Example:**
```
Scheduler> service start

✅ Starting scheduler service...
   Supervisor detected state change
   Worker process spawned (PID: 12345)
   Next run: 09:20 AM ET (15h 23m)

Scheduler> service status

🟢 Service Status: RUNNING
   PID: 12345
   Uptime: 2h 15m
   Last heartbeat: 5 seconds ago
   Next execution: 09:20 AM ET (13h 8m)
   Executions today: 1 (morning_routine)
```

## Implementation Plan

### Phase 1: Basic Subprocess Control
- [ ] Add `service start` command (simple subprocess)
- [ ] Add `service stop` command (PID-based kill)
- [ ] PID file management
- [ ] Basic status checking

### Phase 2: Self-Termination
- [ ] Worker detects `enabled: false`
- [ ] Graceful shutdown with cleanup
- [ ] State persistence before exit

### Phase 3: Supervisor Pattern
- [ ] Create lightweight supervisor daemon
- [ ] State file communication
- [ ] Automatic crash recovery
- [ ] Heartbeat monitoring

### Phase 4: Production Features
- [ ] System service integration (systemd/launchd)
- [ ] Logging to syslog/journald
- [ ] Metrics collection (Prometheus-style)
- [ ] Web dashboard (optional)

## File Structure

```
state/
├── scheduler.state      # Enabled/disabled state (CLI → Supervisor)
├── scheduler.pid        # Worker process ID
├── scheduler.heartbeat  # Worker health check
├── scheduler_execution_log.json  # Execution history
└── supervisor.pid       # Supervisor process ID

config_defaults/
└── scheduler_config.yaml  # Configuration

src/
├── cli/
│   └── scheduler_cli.py  # CLI with service commands
├── trading/
│   ├── scheduler_worker.py      # Self-managing worker
│   └── scheduler_supervisor.py  # Lightweight supervisor
└── utils/
    └── process_manager.py  # PID/process utilities
```

## Security Considerations

1. **PID File Permissions:** chmod 600, owned by user
2. **State File Validation:** Schema validation on load
3. **Process Ownership:** Only start processes as current user
4. **Signal Handling:** Graceful SIGTERM, emergency SIGKILL
5. **Log Permissions:** Restrict read access to user

## Future Enhancements

- **Multi-scheduler support:** Run multiple strategies
- **Priority scheduling:** Different times for different tickers
- **Conditional execution:** Market conditions-based triggers
- **Remote control:** API/webhook-based start/stop
- **Monitoring dashboard:** Web UI for status

---

**Status:** This is a design document for future implementation.

**Related:**
- [Scheduler CLI Reference](../features/scheduler_cli_reference.md)
- [GTC Scheduler Technical](../features/03_gtc_scheduler_technical.md)
