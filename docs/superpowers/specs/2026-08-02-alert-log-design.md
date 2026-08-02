# Alert Log Design

## Goal

Persist every opportunity that was successfully delivered to Telegram so later conversations can inspect exactly what the bot sent, rank the options, and recommend what to do next without requiring screenshots from Telegram.

The log must also reconstruct as much as possible of the opportunities already delivered on 2026-08-02.

## Scope

This change adds a durable append-only JSON Lines journal at `data/alerts.jsonl`.

Each line represents one delivered opportunity. A Telegram digest containing several opportunities therefore produces several journal records. The implementation does not store Telegram bot tokens, chat IDs, message IDs, or other recipient data.

## Record format

Every complete record contains:

- `sent_at`: UTC ISO-8601 timestamp of successful Telegram delivery;
- `delivery`: `immediate` or `digest`;
- `opportunity_key`: stable source-and-source-ID key;
- `source` and `source_id`;
- `title`, `url`, and `summary`;
- `kind`;
- `reward_amount`, `reward_currency`, and `reward_usd`;
- `deadline`;
- `score`;
- `skills`, `categories`, `restrictions`, and `risk_flags`;
- `recovered`: whether the row was reconstructed after the original delivery;
- `recovered_incomplete`: whether full source data could not be recovered.

Incomplete reconstructed records retain every field available from `data/state.json`, including the stable key, source, source ID, delivery timestamp, reward in USD, and deadline. Missing descriptive fields are `null` or empty collections.

## Components

### AlertRecord

A serializable model responsible only for validating and converting one journal row. It exposes construction from a scored opportunity and construction of an incomplete recovered row.

### AlertLog

A small append-only store responsible for:

- loading existing record identities;
- appending one or more records as UTF-8 JSON Lines;
- suppressing duplicate records;
- writing atomically through a temporary file and rename.

A record identity is the tuple `(opportunity_key, delivery, sent_at)`. This permits a materially updated opportunity to be delivered and logged again at a later time while making workflow retries idempotent.

### Pipeline integration

The pipeline receives an optional `AlertLog` dependency.

For immediate delivery, it sends the Telegram message first. Only after the send succeeds does it mark state as delivered and append the corresponding log record.

For digest delivery, it sends the combined Telegram message first. Only after the send succeeds does it mark every included opportunity as delivered and append one journal record per opportunity, all with the same delivery timestamp.

If Telegram delivery fails, neither state nor the alert log records that delivery.

### Recovery command

A one-time CLI mode, `recover-alert-log`, reconstructs records from `data/state.json`.

It performs a fresh read from the configured sources and indexes fetched opportunities by stable key. For every state item delivered on 2026-08-02:

1. identify its immediate and/or digest delivery timestamp;
2. match the stable key against freshly fetched source items;
3. compute a current score when full data is available;
4. append a recovered complete record;
5. otherwise append an incomplete recovered record using state data.

Recovery never sends Telegram messages and is idempotent through the same record identity rule.

Because source content can change or disappear after delivery, recovered titles, summaries, deadlines, rewards, and scores are best-effort snapshots rather than guaranteed byte-for-byte copies of the original Telegram text. The original delivery time and state-held reward/deadline remain authoritative when they conflict with freshly fetched content.

## Configuration

Add `ALERT_LOG_PATH`, defaulting to `data/alerts.jsonl`.

Normal `scan` and `digest` runs use this path automatically. `recover-alert-log` uses the same state and log paths and the same source credentials, but does not require Telegram credentials.

## GitHub Actions

The workflow commits both persistent files when either changes:

- `data/state.json`;
- `data/alerts.jsonl`.

A manual workflow input adds `recover-alert-log` as a selectable mode. Scheduled behavior remains unchanged.

The commit step checks both files together, stages both, rebases, and pushes as it currently does for state alone.

## Error handling

- A Telegram failure prevents both state delivery markers and log appends for that attempted message.
- A log write failure makes the workflow fail rather than silently losing the audit trail. The Telegram message may already have been delivered in this narrow case; the next retry remains safe because the delivery marker is saved only together with the normal persistence phase and journal identities are deduplicated.
- A source failure during recovery does not abort recovery for other sources. Unmatched delivered state items become incomplete records.
- Malformed existing JSONL fails loudly with a line number so journal corruption is not silently ignored.

## Testing

Add tests for:

- complete record serialization;
- atomic append and newline-delimited formatting;
- duplicate suppression;
- logging after successful immediate delivery;
- no logging after failed immediate delivery;
- one record per digest item;
- recovery of a matched state item;
- incomplete recovery of a missing state item;
- recovery idempotency;
- CLI wiring and workflow file coverage for the new path and mode.

Existing pipeline, Telegram fan-out, state, and source tests must continue to pass.

## Success criteria

After deployment:

1. every opportunity successfully delivered to Telegram appears once in `data/alerts.jsonl` for that delivery event;
2. workflow retries do not duplicate rows;
3. no secrets or recipient identifiers appear in the log;
4. the 2026-08-02 delivery history is reconstructed as completely as current source availability permits;
5. a later request such as “Посмотри, что бот прислал сегодня” can be answered by reading the journal from GitHub.