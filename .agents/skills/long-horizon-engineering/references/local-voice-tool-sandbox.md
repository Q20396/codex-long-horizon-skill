# Local Voice Tool Sandbox

Use this optional, explicit-only protocol when a user asks to evaluate or use
a local text-to-speech, speech-to-text, voice-cloning, or voice-enabled MCP
tool. It is a review and approval protocol, not an integration, installer,
model manager, or audio runtime.

## Status And Scope

- Invocation: `EXPLICIT_ONLY`
- Proposal status: `PROPOSAL_ONLY`
- Default permission: `NONE`
- Default network access: `DENY`
- Default external voice or audio action: `DENY`

This protocol does not install, update, download, start, configure, connect,
authenticate, invoke, or remove a voice tool. It does not read microphones,
system audio, audio files, voice profiles, capture history, or cloud accounts.
It does not create an MCP configuration or grant a tool access to Codex.

Use `external-tool-provider-protocol.md`,
`external-app-runtime-boundary.md`, and
`approved-tool-contract-card.md` before proposing an external tool. Use
`templates/LOCAL_VOICE_TOOL_APPROVAL_CARD.md` only when a written review
record would reduce risk.

## Why Voice Tools Need A Separate Boundary

Audio can reveal identity, health, location, relationships, employer context,
and private conversations. A local endpoint can still expose data to other
processes on the same machine, persist transcripts or recordings, download
models, start a background service, or later enable cloud features.

Treat the following as sensitive by default:

- microphone or system-audio capture
- audio files and absolute audio paths
- transcripts, capture history, and generated-audio history
- cloned voices, reference samples, and voice profiles
- personality prompts, voice preferences, and pronunciation dictionaries
- model caches, diagnostics, cloud links, account identifiers, and telemetry

Do not put any of these items in project memory, task logs, working state,
handoff reports, public commits, public PRs, or reusable examples.

## Separate Approval Gates

One approval never covers another. Ask for the smallest applicable action:

1. **Public-source review**: inspect a named source, release, license, or
   immutable commit. Network access still needs approval.
2. **Acquisition**: download or install the exact reviewed version.
3. **Model download**: download named models after reviewing size, license,
   storage path, source, and network destination.
4. **Runtime start**: start one local process for one bounded task.
5. **MCP connection**: add one exact local endpoint or command to a named
   client configuration.
6. **Input access**: provide a precise, user-approved text or audio input.
7. **Voice identity**: use a preset voice, or separately document the
   speaker's consent for a cloned or reference voice.
8. **Output handling**: play, save, retain, share, or delete generated audio.
9. **Cloud or account use**: sign in, sync, back up, upload, or contact a
   provider.

A changed product, version, endpoint, command, input scope, voice identity,
or output destination invalidates prior approval.

## Safe Defaults

Do not propose or perform any of the following without a separate, explicit
approval that names the action and scope:

- microphone, system-audio, browser-audio, or screen capture
- reading arbitrary `audio_path` values or enumerating local capture history
- listing transcripts, voice profiles, or stored recordings
- voice cloning, reference-audio enrollment, impersonation, or speaker
  likeness generation
- rewriting text through a personality model before speech
- background services, persistent listeners, automatic updates, or automatic
  model downloads
- non-loopback bindings, LAN exposure, remote control, or unauthenticated
  local endpoints
- cloud login, synchronization, backup, telemetry, or transfer of text, audio,
  transcripts, profiles, or model diagnostics

Never assume that a tool is private merely because it is described as local.
Verify its runtime binding, storage behavior, model source, optional cloud
features, and security documentation for the reviewed version.

## Lowest-Risk Pilot

When the user has approved a pilot, propose only one narrow, visible action:

- a user-supplied, non-sensitive sentence
- a built-in preset voice, not a cloned or reference voice
- plain speech with no personality rewrite
- a named local output behavior and retention choice
- no account, cloud, browser, microphone, audio-path, history, or profile
  access
- no background listener or persistent MCP connection

State the exact product/version, command or tool call, text classification,
network behavior, destination, expected effect, validation, and rollback.
If any of these facts are unknown, stop and ask rather than guessing.

## Candidate Review Rules

Popularity, star counts, screenshots, benchmark claims, or "local-first"
marketing do not establish safety or compatibility. Prefer an immutable tag or
commit, primary documentation, license review, dependency review, and a
minimal doctor or `--help` check after acquisition is separately approved.

Do not copy external source code, prompts, models, voices, or documentation
into this skill package. Do not add a provider-specific runtime integration
unless a future task explicitly approves that exact implementation.

## Validation And Rollback

Before a permitted action, define:

- the exact configuration path or command that could change
- the expected local process, port, file path, and output behavior
- how completion will be observed without reading unrelated audio or history
- the stop condition if network access, unapproved input access, or a broader
  permission request appears
- the manual rollback for the exact MCP configuration or local setting

Do not automatically uninstall a tool, delete models, erase recordings, or
remove configuration during rollback. Those are separate destructive actions
that require exact-path approval.
