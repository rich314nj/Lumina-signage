# Issue #19 Implementation Brief: Scheduled Display Power Control

Repository: https://github.com/rich314nj/Lumina-signage

Issue: https://github.com/rich314nj/Lumina-signage/issues/19

## Objective

Implement safe scheduled display sleep and wake control for Raspberry Pi signage installations.

The Raspberry Pi must remain powered and network-accessible at all times. This feature controls only the attached display. It must never shut down the Pi as part of a display schedule.

Display power scheduling must be disabled by default on both new and upgraded installations.

## Core safety decisions

1. Keep the Raspberry Pi running continuously. HDMI-CEC standby should turn off only the television or display.
2. Do not reuse the existing device `shutdown` action for display scheduling.
3. Do not silently fall back from HDMI-CEC to Wayland output blanking. These have different behavior and must be selected explicitly.
4. Never enable the feature merely because a CEC executable or `/dev/cec*` device exists.
5. Require a successful operator-confirmed sleep/wake compatibility test before scheduled CEC control can be enabled.
6. If Lumina cannot trust the device clock, fail open: keep or wake the display and suspend scheduled sleeping.

## Control methods

Implement a backend interface that can support multiple control methods.

### HDMI-CEC

This is the preferred method because it can put the actual panel into standby and wake it later.

CEC behavior varies by display. HDMI switches, splitters, extenders, HDMI-to-DVI adapters, cables without a working CEC conductor, AVR equipment, and television settings can prevent it from working. Manufacturers may call CEC Anynet+, Simplink, Bravia Sync, VIERA Link, or another brand-specific name.

Wake may require an image-view-on command followed by active-source after a short delay. Some displays accept standby but cannot wake from deep standby. Therefore, capability detection alone is insufficient.

Be consistent about the selected Linux tooling:

- Debian `cec-utils` provides `cec-client`.
- `cec-ctl` is supplied by `v4l-utils`.
- Do not install one package and implement commands intended for the other.

Support explicit CEC adapter selection because Raspberry Pi 4 and 5 systems can expose more than one HDMI/CEC adapter.

### Wayland output blanking

Treat this as a separate, explicitly selected experimental method. It is not an automatic fallback for CEC.

Suggested UI label:

> Blank HDMI output — experimental. This may not turn off the display or its backlight.

`wlr-randr` requires the active compositor to implement the wlroots output-management protocol. Lumina supports both Cage appliance installations and desktop autostart installations, so it cannot be assumed to work everywhere.

The helper must run `wlr-randr` in the kiosk user's Wayland session with the correct `XDG_RUNTIME_DIR`, `WAYLAND_DISPLAY`, permissions, and validated output name. Do not accept an arbitrary command or output name from the web request.

Disabling HDMI output can cause some displays to enter standby, remain fully lit on a No Signal page, or fail to wake when the signal returns. The compatibility test must cover both directions.

### Displays without usable CEC

There is no generic HDMI command that can reliably turn every non-CEC display back on.

Supported guidance should mention these alternatives:

- The display's built-in weekly power timer.
- Vendor network APIs on commercial displays.
- RS-232 control on commercial panels.
- A managed relay or smart plug powering only the display.
- Explicit Wayland output blanking when that exact display has been tested.

A smart plug must never cut power to the Raspberry Pi. It is appropriate only when the display has separate power and has been verified to turn on automatically after AC power is restored.

## User interface

Add a master setting:

```text
Display power scheduling: Disabled
Control method: None
```

This must be the default for new and upgraded installations.

When disabled, Lumina performs no scheduled display power actions. If the feature is disabled while Lumina believes the display is off, first attempt to wake it using the previously configured backend, then clear the scheduling state.

The settings UI should show:

- Master enabled/disabled toggle.
- Selected control method: None, HDMI-CEC, or Wayland blanking.
- Detected adapters or outputs.
- Capability and compatibility-test status.
- Desired state: on or sleeping.
- Observed state: on, standby, or unknown.
- Last command time and result.
- Next scheduled transition.
- Active manual override, if any.

Manual actions:

- Wake now.
- Sleep now.
- Resume schedule.

Recommended override behavior: a manual wake or sleep remains active until the next scheduled transition. The UI must clearly show this and provide Resume schedule.

## Compatibility test

Provide a Test sleep and wake workflow before allowing CEC scheduling to be enabled:

1. Detect candidate adapters.
2. Select the intended adapter/output.
3. Verify that a television responds if the backend supports status queries.
4. Before sending the sleep command, independently schedule a wake command through the system service. Do not depend on the browser remaining connected.
5. Put the display to sleep for approximately 15 seconds.
6. Wake it.
7. Ask the operator to confirm that both sleep and wake physically worked.
8. Record the successful test for that backend and adapter.

The wake safety action must survive the admin browser disconnecting and the display becoming unavailable.

## Architecture

Do not implement the scheduler as a Flask background thread.

Lumina currently runs Gunicorn with two workers. An in-process scheduler could run twice, lose state during deployments, or behave inconsistently between workers.

Use a single dedicated service, for example:

```text
Admin UI/API
    -> SQLite display-power configuration
    -> lumina-display-scheduler.service
    -> validated lumina-power helper
    -> CEC or explicitly selected output backend
```

A dedicated long-running service or a systemd timer invoking one scheduler process every 30 to 60 seconds is acceptable. There must be exactly one scheduler owner.

The scheduler should run unprivileged as the Lumina application user where possible. It may invoke the existing narrowly scoped privileged helper for hardware operations. The root helper must expose only fixed actions and validate any adapter/output identifiers against detected devices.

Suggested fixed helper actions:

```text
display-probe
display-status
display-on
display-off
restart-display
reboot
shutdown
```

Serialize display commands with a lock so scheduled operations, manual operations, tests, and startup reconciliation cannot race.

## Data model

Prefer a new singleton table rather than modifying the existing content schedule table. The project currently initializes schema with `db.create_all()` and does not have a full schema migration framework, so adding a new table is safer for existing installations.

Suggested persistent fields:

```text
enabled = false
driver = none | cec | wayland
cec_adapter
wayland_output
weekly_hours
manual_override = none | on | off
compatibility_tested_at
compatibility_test_backend
compatibility_test_target
last_desired_state
last_command_at
last_command_result
```

Runtime-only status can be stored in a small file under `/run/lumina/`, while configuration and manual overrides must survive restarts in SQLite.

Use weekly operating hours independent of content schedules. Reuse the existing tested time parsing and overnight-interval concepts where appropriate, but do not couple display power rows to playlists.

Clearly define behavior for days with no operating hours. The preferred interpretation is that the display remains asleep for that entire day when scheduling is enabled.

## Scheduler behavior

The scheduler must calculate desired state from the current local time rather than relying solely on one-time transition jobs.

On service start, reboot, update, or recovery:

1. Read configuration.
2. Validate the clock.
3. Calculate whether the display should currently be on or sleeping.
4. Reconcile the actual/last-known state.
5. Record the result and next transition.

This handles missed transitions, restarts during a transition, power failures, daylight-saving changes, and overnight schedules.

Commands must be idempotent. Send commands only when state changes, during startup reconciliation, or during bounded retry handling. Do not broadcast CEC commands every minute indefinitely.

Use bounded retries and timeouts. A recommended policy is up to three wake attempts with short delays, followed by a persistent visible error.

If the selected backend disappears while Lumina believes the display is asleep, attempt a wake using the previously selected backend before allowing the configuration to be changed or disabled.

## Clock and schedule safety

Display scheduling depends on correct local time. Integrate with the existing timezone and clock status functionality.

If the system clock is clearly invalid or unsynchronized after boot:

- Do not put the display to sleep.
- Attempt to wake it if it may be sleeping.
- Report `Schedule suspended: device time is not trusted`.
- Resume normal reconciliation once time becomes trustworthy.

Because desired state is recalculated from the current local time, daylight-saving transitions should not cause duplicate unsafe operations.

## Health reporting

Health must distinguish these states:

- Intentionally sleeping according to schedule.
- Intentionally sleeping due to manual override.
- Expected on and player heartbeat healthy.
- Expected on but player heartbeat stale.
- Display command failed.
- Physical display state unknown.

A player browser heartbeat does not prove that the physical panel is on. Chromium may continue reporting while a CEC television is in standby. Conversely, output blanking may throttle browser execution.

The scheduler's desired state and last command result should be authoritative. CEC power status can supplement it but must be allowed to return unknown.

The existing player heartbeat is held in process memory while Gunicorn runs two workers. Move it to shared storage or a status file under `/run/lumina/` so health results are consistent across workers and restarts.

An intentionally sleeping display must not appear as failed or unhealthy.

## Error handling and observability

Record at least:

- Backend and target adapter/output.
- Requested action.
- Desired state.
- Command start and completion time.
- Exit status and sanitized error.
- Retry count.
- Whether the action came from schedule, manual control, startup reconciliation, or compatibility testing.

Expose the most recent result through the admin API and UI. Do not report success merely because a process produced no parseable output.

CEC status can legitimately be unknown. Unknown is different from success and different from failure.

## Installation and upgrade requirements

Add the selected CEC and Wayland packages to both:

- The normal Raspberry Pi installer apt package list.
- `image/pi-gen/stage-lumina/01-lumina/00-packages`.

Ensure in-app upgrades install newly required system packages and provision the scheduler unit, helper changes, sudoers grant, runtime directory, and kiosk-session configuration.

The updater must restore the previous helper and service configuration during rollback.

## Security requirements

- Admin role required for configuration and manual display controls.
- No arbitrary commands from API input.
- Validate adapter and output identifiers against enumerated hardware.
- Use fixed helper subcommands.
- Do not expose the Wayland socket broadly.
- Do not let the privileged helper execute paths or shell fragments taken from the database or request.
- Serialize operations to avoid state races.
- Sanitize command output before showing it in the UI.

## Tests

Create a fake display-power backend so tests do not require CEC hardware or Wayland.

At minimum test:

- Feature defaults to disabled after a new install and upgrade.
- Disabled scheduling performs no power action.
- Invalid backend and target identifiers are rejected.
- Editor/viewer roles cannot control display power.
- Manual wake, sleep, and resume-schedule behavior.
- Compatibility test schedules wake before sleep.
- Failed compatibility test cannot enable scheduling.
- Weekday and overnight interval resolution.
- Days with no configured operating hours.
- Startup reconciliation during scheduled-on and scheduled-off periods.
- Missed transitions while the service was stopped.
- Manual override expiration at the next transition.
- Untrusted clock causes fail-open behavior.
- CEC status unknown is handled without a false success/failure.
- Bounded command retries.
- Simultaneous manual and scheduled actions are serialized.
- Intentional sleep does not appear as failed health.
- Shared heartbeat/status works consistently with multiple Gunicorn workers.
- Disabling or changing the backend while asleep attempts wake first.

## Recommended delivery sequence

### Phase 1: Manual control and compatibility testing

- Backend interface and fake backend.
- CEC detection, status, wake, and standby.
- Explicit experimental Wayland backend only if it can be tested reliably.
- Fixed privileged helper actions.
- Admin status UI.
- Manual wake/sleep.
- Timed compatibility test with independent safety wake.
- Package and image changes.
- Unit and API tests.

### Phase 2: Scheduling and health integration

- Dedicated scheduler service or timer.
- Weekly operating hours.
- Manual overrides and Resume schedule.
- Startup/missed-transition reconciliation.
- Clock fail-open behavior.
- Health state integration.
- Shared player heartbeat/status.
- Logging, next-transition display, and failure reporting.

## Acceptance criteria

The implementation is complete only when all of the following are true:

- Display scheduling is disabled by default.
- No display schedule can shut down or remove power from the Raspberry Pi.
- CEC scheduling cannot be enabled until a complete sleep/wake test is confirmed.
- CEC and Wayland methods are explicit choices; there is no silent fallback.
- A non-CEC display receives honest UI guidance rather than a false claim of power control.
- The Pi remains remotely reachable while the display is asleep.
- The scheduler has exactly one process owner and survives app/browser restarts.
- Rebooting during an off period returns the display to the correct desired state.
- A missed wake transition is reconciled when the scheduler returns.
- Invalid device time suspends sleeping and fails open.
- Manual overrides have defined and visible behavior.
- Intentional sleep is represented correctly in health reporting.
- Hardware command failures and unknown states are visible to the administrator.
- New and upgraded Raspberry Pi images contain all required packages and services.
- Tests cover scheduling, failure, security, upgrade, and multi-worker health behavior.

## Implementation instruction for Claude Code

Review the repository before changing code and adapt this design to its existing conventions. Implement the work incrementally, preserve existing behavior, and do not make unrelated changes. Start with Phase 1 unless explicitly instructed to implement both phases. Run the complete existing test suite plus all new tests. Report any hardware-dependent behavior that cannot be verified without a real Raspberry Pi and display, and provide a precise on-device validation checklist.
