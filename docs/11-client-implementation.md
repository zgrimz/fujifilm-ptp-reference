# 11. Implementing a recipe client

This chapter gives implementation recommendations distilled from the author's iOS client: its bank writing, RAW conversion, backup and restore, scripted camera tests, and session handling. It summarizes relevant protocol facts; their evidence remains in [bank operations](04-custom-slots.md), [conversion](05-raw-conversion.md), and [profiles](06-conversion-profile.md).

The [command-outcome and field-verification examples](../fixtures/conformance/cases.json) provide synthetic inputs and expected outcomes to adapt to a client's own tests. Passing them establishes software behavior, not camera compatibility.

## Keep intent, encoding, and observation separate

A recipe field has an intent: set a specific value, explicitly turn Off, or leave unspecified. Camera support and current applicability are separate properties. An unsupported field and a field temporarily inactive under ACROS or D-Range Priority are different cases. A missing JPEG tag is unknown; it doesn't supply an Off or zero intent. When a decoder doesn't recognize an enum value, preserve the original raw value.

Translate semantic values through the appropriate [bank encoding](03-encodings.md), [profile cell encoding](06-conversion-profile.md), or [JPEG metadata mapping](10-jpeg-recipes.md). Never send an EXIF ACROS filter number straight to a PTP property. Application choices such as filling unspecified bank fields with defaults or treating missing metadata as neutral must be explicit policies, not protocol rules.

For conversion, start from the uploaded RAF's actual profile and patch only supported, explicitly requested cells within an identified layout. An empty change set leaves every byte unchanged. Explicit zero remains a real write. Don't enlarge a short profile to write a missing cell without a separately justified host-write rule.

Track requested fields independently of the bytes that differ from that immutable base. For example, a RAF's as-shot simulation cell is `1`, the previous conversion used `11`, and the next recipe explicitly requests `1`. The next profile agrees with the base, but its simulation remains an expected field for readback. A stale read of `11` must be a mismatch; computing verification fields only from a base-versus-requested byte diff would miss it. The example illustrates intent handling, not whether a particular camera retains the previous profile.

## Lock a whole operation

The bank selector is shared camera state. Serializing individual PTP commands still permits this race:

```text
writer: select C3
probe:  select C5
writer: write grain     -> reaches C5
```

Hold one operation lock across selection, verification of the selection, dependent writes, readback, and any restoration. All paths that use the selector—including diagnostics and background refresh—must use that lock. Conversion also uses shared camera state: hold ownership through upload, profile preparation/readback, trigger, output identification, download, durable saving, and cleanup. Competing probes and batch jobs must participate in the same ownership scheme wherever they can affect that state. The lock protects one process; it can't exclude X RAW Studio or another client.

```python
async with gate.operation() as owner:
    epoch = current_session_epoch()
    original_selector, original = unavailable, unavailable
    try:
        original_selector = await read_selector()
        await select_and_verify(target)
        original = await read_required_originals()
        validate_complete_plan(original, intent)  # no settings changed yet
        await apply_dependency_ordered_changes()
        outcome = await verify_intended_fields()
    finally:
        # Includes content restoration only for an experiment, followed by
        # selector restoration. Keep each result separate from the main error.
        for step in planned_recovery(original, original_selector):
            if not recovery_context_is_safe(owner, epoch, step):
                record_unresolved_recovery(step)
                break
            if step.changes_bank_content:
                selection = await select_and_verify(target)
                if not selection.matched or not recovery_context_is_safe(owner, epoch, step):
                    record_unresolved_recovery(step)
                    break
            await step.restore_and_verify()
```

This is pseudocode: `recovery_context_is_safe` requires the same current session and operation owner, a usable session, known completion of preceding commands, and valid originals required by this step. Bank-content writes additionally require verified target selection. Missing originals remain unresolved recovery steps, not permission to substitute defaults. A selector restoration requires its own valid original selector and verifies the selected result. The recovery helpers record failures separately from the original error and recheck context after every awaited command, including commands within reselection and verification, and before each subsequent cleanup step; an unknown or stale completion stops the sequence. A late completion cannot release a newer operation's ownership.

Cancellation handling must suit the runtime. Shield or explicitly await bounded cleanup only while those conditions hold, rather than assuming a `finally` block's awaited calls can't themselves be canceled or that cleanup is always safe. A shutdown that can't finish cleanup leaves a recovery record marked unresolved.

## Report command outcomes and state verification independently

| Command outcome | Meaning |
|---|---|
| `not_attempted` | Execution never reached the send operation. |
| `accepted` | The client received a matching successful response. It doesn't establish that the value changed. |
| `refused` | The client received a matching non-OK response. Preserve its code and context. |
| `outcome_unknown` | A send might have occurred, but its response or completion is unavailable. |

Independently report verification as `matched`, `mismatched`, `unavailable`, or `not_tested`. An ignored OK is accepted/mismatched. A refused no-op can be refused/matched because the desired value was already stored. Neither pair proves that a write caused the final state.

For a partial push, retain the per-field result; don't summarize all fields as success or failure. A timeout after sending isn't “not attempted.” Don't automatically replay it after reconnect: first establish the camera, state, and whether repeating the operation is appropriate. A RAW conversion trigger or object deletion especially needs its own recovery policy.

A conservative client policy stops dependent writes, automatic rollback, and remaining batch jobs when a command's completion is unknown. Preserve which commands were not attempted. This applies to an uncertain name or property write as well as upload, profile write, trigger, and deletion. A new connection doesn't resolve whether the earlier operation completed; reconcile that operation before starting further jobs under this policy. A confirmed refusal is distinct: it supplies a known command outcome, but session usability and dependencies still determine whether anything can continue.

Failed, nil, or empty profile readback must produce unavailable verification. An empty mismatch list produced by a failed read isn't confirmation. No accepted or expected fields means not tested, not a vacuous persistence pass. The fault vectors include expected outcomes for unavailable and partial reads.

## Capture recoverable originals before experiments

A host bank snapshot differs from Fujifilm's whole-settings backup object. It covers specified properties and can't reconstruct unobserved settings or an unknown empty-bank state.

A useful local recovery record includes:

- A versioned format and immutable snapshot identifier, with capture time and connection identity.
- A locally established physical-camera binding. A model name or matching VID/PID alone doesn't distinguish two bodies. Keep any serial-derived binding local; public evidence does not need it.
- The selected bank, original selector when readable, original name with its read status, and raw original property bytes. Preserve unknown values without interpreting them as defaults.
- Separate read statuses for unsupported, failed, missing, and successful values; explicit scope for bank versus live state.
- The planned touched fields, dependencies, known restoration losses, and subsequent restoration attempts/results. Keep the initial original instead of replacing it with a later trial's modified state.

Validate an entire imported snapshot and proposed write list before changing settings: format/version, bank bounds, duplicate or ambiguously formatted property keys, byte lengths/types, allowed namespace, and recoverable original values. The generic bank probe rejects selector and live codes inside a bank-scoped write list. Selecting a bank to read its state still writes the selector; this is distinct from changing recipe content.

The 23 bank settings end at `0xD1A4`. `0xD1A5` is separately observed live state and isn't part of an ordinary bank restore. An explicit live experiment needs its own original, verification, and cleanup.

Restoration must follow the documented interlocks and applicability rules, reselect and verify the actual target, then compare fresh state against the immutable baseline. Preserve both command results and final comparison: a refusal need not mean the final value is wrong, and an OK need not mean it matches. When only semantic agreement is verified, report semantic-only restoration. The [reported grain sequences](03-encodings.md#0xd195-grain-effect) reconstruct Off's remembered size on an X-T50 fw 1.32 (maintainer measurements) and a GFX100S fw 2.13 (owner report); a rollback must use the required sequence and verify the saved raw value before claiming exact restoration. Writing only Off left the wrong remembered size in the owner's recorded GFX100S rollback. Don't manufacture an “empty bank” by writing a default recipe. Camera-menu **ERASE** and the USB property path have different capabilities and evidence.

## Develop a RAF without confusing another object for the result

Use this sequence inside the operation's ownership boundary. Validate response containers and complete delivery, and correlate responses using the transport's transaction model. On direct USB, match the response's wire transaction ID to the command's. For ImageCaptureCore, account for the reported mismatch between response IDs and client-supplied IDs on an X-T50 fw 1.32: correlate each serialized request with its specific callback/context and current session, and reject stale completions rather than comparing the response ID with the client-supplied ID. Framework renumbering is an inferred explanation for that mismatch, not a documented Apple API guarantee. For the observation and its evidence limits, see [platform notes](09-platform-notes.md#sessions-and-commands).

1. Establish the supported transport/session and upload the intended RAF. Read and validate its profile; preserve an immutable base.
2. Apply sparse intent, write the correct body-specific form, and attempt profile readback. Record matched, mismatched, or unavailable independently of later rendering.
3. After upload and profile preparation, enumerate current objects successfully immediately before triggering conversion. Keep this list as the baseline, including the uploaded input if the camera enumerates it. Validate the data length/count, reject duplicate/reserved handles, and distinguish a valid empty list from a failed or malformed response. Failure here aborts before the trigger.
4. Trigger once, then poll within a bounded budget. A disappeared connection makes the operation uncertain; reconnecting isn't permission to trigger again.
5. Compare validated handle sets. Check each candidate's `ObjectInfo`, expected format, and ownership: another client or task might also create new objects. A single new handle is only a candidate in an isolated workflow. Multiple candidates require an explicit disambiguation policy. If candidates or an interrupted session leave ownership uncertain, retain the objects and report that uncertainty.
6. Download and validate the candidate, including complete delivery, expected size, and image validity under the client's declared validation policy. Save a durable local copy before deleting any camera output: an in-memory buffer or temporary preview alone is insufficient. The copy may be the final destination or a recoverable local file retained until the final destination succeeds. Delete only an object this operation owns, while its session/operation context remains valid, under the client's cleanup policy. Never delete an object from the baseline in step 3 as part of output cleanup.

Keep saving and cleanup outcomes separate:

| Outcome | Recovery and continuation recommendation |
|---|---|
| Validation or durable local saving fails | Retain the camera output; don't authorize deletion. Report the failure and known output identity. |
| Durable recovery copy succeeds, final destination fails | Retain and expose the recovery copy. Report final-destination failure separately; cleanup may follow the declared policy because validated data is durably recoverable. |
| Cleanup is accepted | Report cleanup acceptance independently of saving and any later persistence check. |
| Cleanup is refused with a usable session | Preserve saved-output success and report the refusal. A policy may permit subsequent independent jobs, using a fresh object baseline that includes the retained output. |
| Cleanup is refused with an unusable session | Preserve saved output, report the refusal, and stop jobs until the session is reconciled. |
| Cleanup completion is unknown | Preserve saved output, report cleanup as unknown, and stop remaining jobs under the conservative policy. Don't assume the object still exists or retry deletion blindly. |

Record command success, profile readback, output metadata, pixel changes, saving, and persistence as separate outcomes. A valid JPEG alone establishes none of the others.

## Keep session and device identity explicit

Use a monotonically changing session epoch or equivalent token. Every asynchronous completion carries the epoch that started it. Closing, disconnecting, or replacing the session invalidates that token; late callbacks cannot update the next session. An idempotent close drains outstanding continuations once and releases delegates/resources without double-resuming callers.

Model lifecycle states such as disconnected, opening, ready, operating, closing, suspended, and uncertain. Apple's `ICDeviceBrowser.h` documents iOS/iPadOS background suspension as pausing device communication until foregrounding, without changing device state or closing its session; the application remains responsible for state management. The [suspension callback](https://developer.apple.com/documentation/imagecapturecore/icdevicebrowserdelegate/devicebrowserdidsuspendoperations%28_%3A%29) is available from iOS/iPadOS 14. [Published: Apple SDK header for behavior; Apple API documentation for availability] As client policy, when an outstanding command's completion is unavailable, preserve uncertainty and recovery state; a suspension notification alone doesn't resolve that outcome.

A matching, device-originated error response establishes that the device answered that exchange; it doesn't establish a usable session. When an error received through a host API has an unresolved origin, it cannot establish camera responsiveness. Reconcile session-related errors such as `0x2003`, `0x2004`, and `0x201E` according to the transport and state. See [response-origin limits](09-platform-notes.md#disconnection) and [callback handling](09-platform-notes.md#sessions-and-commands) in the platform notes.

Resolve model identity using exact normalized names and documented aliases before bounded heuristics. Preserve match confidence. Maintain separate fields for model identity, published capabilities, observed capabilities, and application permissions. Processor generation, a capability-table entry, and a successful descriptor read are not interchangeable with a successful operation on that model/firmware.

## Build tests that produce useful evidence

Use distinct test recipes, so comparing a requested value with an unchanged starting value can't be mistaken for a write test. Record the fields actually accepted, their fresh post-write reads, and the original bank snapshot. Persistence tests require a fresh read on the new connection; record the user's power-cycle confirmation separately from a USB reconnect. Record **AUTO UPDATE CUSTOM SETTING** state, bank format, ISO, simulation, and relevant lens/state gates. Unknown setup variables limit the conclusion.

Use [structured evidence](../evidence/report-schema.md) with stable operation/connection identifiers and capture times. Retain the original snapshot, not only the latest mutable state. Declare trace scope, truncation, and dropped entries. Don't describe a short trace on the latest connection as the entire multi-connection experiment.

Test a client for ignored OK, refusal, a missing response after send, partial success, malformed/empty reads, selector interleaving, revert-on-reconnect, missing backup data, failed restore, duplicate/reserved handles, ambiguous output objects, failed saving, and stale callbacks. The [supplied examples](../fixtures/conformance/cases.json) cover command outcomes and field verification; the other scenarios need tests suited to the client's implementation. Label simulated scenarios synthetic: passing them validates software behavior, not a camera's compatibility.
