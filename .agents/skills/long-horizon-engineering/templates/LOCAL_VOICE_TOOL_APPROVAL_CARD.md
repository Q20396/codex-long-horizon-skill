# Local Voice Tool Approval Card

Do not include secrets, API keys, tokens, passwords, private audio, voice
samples, transcripts, client names, legal evidence, family information,
medical information, financial information, identity documents, private
correspondence, or confidential source content.

## Contract Status

- Invocation: EXPLICIT_ONLY
- Proposal status: PROPOSAL_ONLY
- User approval: PENDING
- Permission granted: NONE
- External tool invoked: NO
- This card is not permission to install, download, run, configure, connect,
  authenticate, capture audio, read audio, clone a voice, write files, upload,
  publish, or delete anything.

## Default Automation Controls

- Automatic installation: NO
- Automatic model download: NO
- Automatic MCP configuration: NO
- Automatic endpoint connection: NO
- Automatic audio-path, capture, or transcript-history access: NO

## Candidate Identity

- Tool or provider:
- Exact version, immutable tag, checksum, or reviewed commit:
- Source URL:
- License and model-license review:
- Maintainer or owner:
- Local or lower-risk alternative:

## Bounded Purpose

- User-approved outcome:
- Explicit non-goals:
- Why a voice tool is needed:
- One-time or limited duration:

## Proposed Action

- Action type: public-source review / acquisition / model download / runtime
  start / MCP connection / speech / transcription / output handling / cloud use
- Exact command, endpoint, or tool call for review:
- Client configuration path, if any:
- Expected process, port, and duration:
- Network behavior and destination: none / pending approval / exact destination

## Approved Input And Voice Scope

- Text input classification: public / user-supplied non-sensitive / sensitive
  (stop)
- Exact approved text or path class:
- Audio-path access: NO
- Capture or transcript-history access: NO
- Voice type: built-in preset / cloned voice / unknown
- Speaker consent for a cloned or reference voice: not applicable / PENDING /
  documented separately
- Personality rewrite: NO
- Microphone, system-audio, browser-audio, or screen capture: NO

## Output And Retention

- Playback behavior:
- Output path or destination:
- Generated-audio retention period:
- Cloud sync, backup, telemetry, or account use: NO
- Sharing or publication: NO

## Separate Approval Gates

| Gate | Required? | User decision | Notes |
| --- | --- | --- | --- |
| Public-source review or network metadata | yes / no | PENDING |  |
| Acquisition or installation | yes / no | PENDING |  |
| Model download | yes / no | PENDING |  |
| Runtime start | yes / no | PENDING |  |
| Exact MCP configuration or connection | yes / no | PENDING |  |
| Exact text or audio input | yes / no | PENDING |  |
| Voice identity or clone use | yes / no | PENDING |  |
| Output save, playback, sharing, or deletion | yes / no | PENDING |  |
| Cloud, account, or external transfer | yes / no | PENDING |  |

## Safety Review

- Loopback-only binding confirmed: yes / no / unknown
- Authentication and local-process trust boundary reviewed: yes / no / unknown
- Broad file, shell, updater, or background-service permissions reviewed:
  yes / no / unknown
- Model source, size, storage, and license reviewed: yes / no / unknown
- Sensitive data excluded:
- Stop condition:

## Minimal Customer Approval Wording

Use one of these statements only after the user selects the named, bounded
action. Each statement leaves every other gate closed.

- Public-source review only: "I approve reviewing the named public source only.
  Do not install, download models, configure MCP, connect a tool, or read
  audio."
- One local speech pilot: "I approve one local speech pilot using the approved
  non-sensitive text and built-in preset voice. Do not download models,
  configure MCP, connect a tool, read audio or history, or retain output beyond
  the approved destination."

## Validation, Fallback, And Rollback

- Lowest-risk check, if separately approved:
- Expected result:
- Validation evidence:
- Local fallback:
- Exact configuration or setting to reverse:
- Manual rollback steps:
- Rollback validation:

## Review Record

- Reviewer:
- Exact approved action and scope:
- Approved at:
- Invalidation condition: Any changed version, endpoint, command, input scope,
  voice identity, output destination, or effect class requires a new review.
