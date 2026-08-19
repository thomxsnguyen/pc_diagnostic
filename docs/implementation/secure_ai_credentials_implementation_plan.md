# Secure AI Credentials Implementation Plan

## Goal

Add secure AI provider credential management to the desktop application. Users
will manage OpenAI, Gemini, or Anthropic tokens from **Settings → AI Provider**.
Secrets will be stored only in the operating system credential vault through
Python `keyring` and retrieved only when required for AI diagnostics.

## Scope

- Add `keyring` as an application dependency.
- Add a credential-service abstraction for OpenAI, Gemini, and Anthropic tokens.
- Add a focused AI Provider card to the existing Settings view.
- Support save, replace, test, and remove operations.
- Use a stored token when running an AI diagnosis.
- Preserve the existing `.env` lookup as a development fallback.
- Preserve the local rule-based analyzer when no usable token exists.
- Add automated tests and update credential-related documentation.

## Out of Scope

- Adding or removing AI providers.
- Model selection or model parameter controls.
- Changes to prompts, evidence collection, recommendations, or reports.
- Cloud synchronization or credential export.
- General Settings features such as refresh rate or hardware configuration.
- Plaintext credential storage of any kind.

## Existing Integration Points

| Area | Current location | Required change |
| --- | --- | --- |
| Dependencies | `pyproject.toml` | Add `keyring` |
| Settings view | `src/pc_diagnostic/gui/views/__init__.py` | Add the AI Provider card only |
| Diagnostic entry point | `src/pc_diagnostic/diagnostics/crew.py` | Resolve and temporarily expose the selected credential |
| GUI diagnosis runner | `src/pc_diagnostic/gui/views/diagnostics_view.py` | Pass provider selection without passing a token through widgets |
| Configuration docs | `docs/configuration.md` | Document secure storage and `.env` fallback precedence |
| Troubleshooting docs | `docs/troubleshooting.md` | Document vault and connection-test failures |

## Credential Contract

Use the stable keyring service name `pc-diagnostic`.

| Provider | Keyring account | Environment fallback |
| --- | --- | --- |
| OpenAI | `openai_api_key` | `OPENAI_API_KEY` |
| Gemini | `gemini_api_key` | `GEMINI_API_KEY` |
| Anthropic | `anthropic_api_key` | `ANTHROPIC_API_KEY` |

Introduce a provider identifier with only these three supported values. Keep the
provider-to-account and provider-to-environment mappings in the credential
service rather than duplicating them in the GUI or diagnostic code.

The credential service should expose:

```python
save_token(provider, token) -> None
get_token(provider) -> str | None
delete_token(provider) -> None
has_token(provider) -> bool
test_token(provider) -> CredentialTestResult
```

The service must convert backend-specific exceptions into sanitized application
errors. Error messages must never contain the token, request authorization
headers, or a provider response body that could echo credentials.

## Implementation Phases

### Phase 1: Credential Service

1. Add `keyring` to the runtime dependencies in `pyproject.toml`.
2. Add a dedicated credential module under `src/pc_diagnostic/`.
3. Define the supported provider identifiers and their account/environment
   mappings.
4. Implement save, retrieve, existence, and delete operations using:

   ```python
   keyring.set_password("pc-diagnostic", account, token)
   keyring.get_password("pc-diagnostic", account)
   keyring.delete_password("pc-diagnostic", account)
   ```

5. Reject blank tokens before calling the credential backend.
6. Treat missing credentials as an expected state rather than an exception.
7. Detect an unavailable or unusable keyring backend and return a sanitized
   `Secure storage unavailable` error. Do not create a file fallback.

Deliverable: a GUI-independent, unit-tested credential service.

### Phase 2: Diagnostic Credential Resolution

1. Update the diagnostic entry point to accept the selected provider identifier.
2. Resolve credentials in this order:
   1. Operating system credential vault.
   2. The selected provider's existing environment variable.
   3. Local rule-based analyzer.
3. If CrewAI requires an environment variable, temporarily set only the selected
   provider's variable immediately before the CrewAI call.
4. Restore the previous environment value, or remove the temporary value, in a
   `finally` block.
5. Do not place the token in the evidence packet, worker signals, logs, exception
   text, report output, or telemetry cache.
6. Preserve current fallback behavior when CrewAI is unavailable or its request
   fails.

Deliverable: stored credentials can power the existing diagnosis workflow
without changing diagnostic content.

### Phase 3: Settings → AI Provider UI

1. Replace only the AI-related placeholder area in the Settings view with an
   **AI Provider** card matching the application's existing clean card design.
2. Add:
   - Provider selector for OpenAI, Gemini, and Anthropic.
   - Password-masked token input.
   - Save or Replace action.
   - Test connection action.
   - Remove token action.
   - Non-sensitive configuration status.
3. Never populate the token field from a stored credential.
4. Clear the token field after save, test, failure, provider change, and view
   teardown.
5. Show status using non-sensitive text:
   - `Not configured`
   - `Configured`
   - `Connection verified`
   - `Secure storage unavailable`
6. If a suffix such as `····a8F2` is shown immediately after saving, keep it only
   in memory for the current session. Do not persist it separately.
7. Disable Replace, Test, and Remove actions when no stored credential exists.
8. Run connection testing outside the GUI thread and return only a sanitized
   success or failure result.

Deliverable: users can manage one selected provider credential without exposing
the secret in the UI.

### Phase 4: Connection Test

1. Keep provider validation behind `test_token(provider)` so networking details
   do not enter the Settings view.
2. Retrieve the credential inside the credential service immediately before the
   validation request.
3. Use a minimal authenticated provider request that does not submit telemetry,
   prompts, or diagnostic evidence.
4. Apply a short timeout and perform the request on a worker thread.
5. Return a typed result containing only:
   - Success or failure.
   - A sanitized user-facing message.
   - A coarse failure category such as unauthorized, timeout, network, or
     provider unavailable.
6. Do not log request headers, token values, or unredacted provider responses.
7. A failed connection test must not automatically delete a stored credential.

Deliverable: users can verify authentication without running or changing a
diagnosis.

### Phase 5: Documentation and Packaging

1. Document credential precedence in `docs/configuration.md`.
2. Keep `.env` documented as a development fallback and confirm it remains in
   `.gitignore`.
3. Document macOS Keychain and Windows Credential Locker behavior in
   `docs/troubleshooting.md`.
4. Document the safe failure message for unavailable credential backends.
5. Verify the packaged application includes the required `keyring` backends.

Deliverable: development and packaged execution use the same credential rules.

## UI State Rules

| State | Save/Replace | Test | Remove | Status |
| --- | --- | --- | --- | --- |
| No stored token | Save enabled when input is non-empty | Disabled | Disabled | `Not configured` |
| Stored token | Replace enabled when input is non-empty | Enabled | Enabled | `Configured` |
| Operation running | Disabled | Disabled | Disabled | Operation-specific progress text |
| Vault unavailable | Disabled | Disabled | Disabled | `Secure storage unavailable` |
| Test succeeds | Replace available | Enabled | Enabled | `Connection verified` |
| Test fails | Replace available | Enabled | Enabled | Sanitized failure message |

## Security Requirements

- Store tokens only through the operating system credential vault.
- Never persist a plaintext or reversibly encoded fallback.
- Never display or repopulate a complete stored token.
- Never include a token in application logs, diagnostic evidence, reports,
  telemetry, cache entries, exports, or exception messages.
- Never transmit telemetry during the connection test.
- Keep the token lifetime in process memory as short as the provider call allows.
- Restore any temporarily modified environment variable after the call.
- Keep provider metadata separate from secret values.
- Do not expose credential methods through telemetry signals.

## Test Plan

### Credential Service Tests

- Save and retrieve each supported provider token using a mocked keyring backend.
- Replace an existing token.
- Delete an existing token.
- Treat a missing token as unconfigured.
- Reject an empty token.
- Map each provider to the correct keyring account and environment variable.
- Sanitize keyring backend exceptions.
- Confirm backend failure never creates a plaintext file.

### Diagnostic Integration Tests

- Prefer a stored credential over the matching `.env` variable.
- Use `.env` when no stored credential exists.
- Use local analysis when neither source exists.
- Restore the prior environment after successful and failed CrewAI calls.
- Confirm tokens never appear in evidence, logs, reports, or raised errors.
- Preserve the existing local fallback when CrewAI is unavailable.

### Settings UI Tests

- Token input uses password echo mode.
- Provider changes update configuration status without displaying a token.
- Save, replace, test, and remove actions invoke the credential service correctly.
- Token input clears after every operation path.
- Controls follow the defined UI state rules.
- Credential operations do not block the GUI thread.
- Full tokens never appear in labels, tooltips, dialogs, or widget properties.

### Connection Test Tests

- Successful authentication returns a sanitized success state.
- Unauthorized, timeout, network, and provider failures map to safe messages.
- No telemetry or evidence is included in the request.
- A failed test does not remove the credential.
- Request and response logging cannot expose the token.

### Regression Tests

- Existing GUI, diagnostics, and fallback tests continue to pass.
- `.env` development configuration remains supported.
- The local analyzer remains usable without network access or credentials.
- Packaged macOS and Windows builds can load their native credential backends.

## Acceptance Criteria

- Users can save, replace, test, and remove a supported provider token from
  Settings.
- Tokens are stored only in macOS Keychain, Windows Credential Locker, or another
  supported operating system keyring backend.
- Stored credentials take precedence over `.env` for the selected provider.
- The existing `.env` path remains available for development.
- The existing local analyzer remains the final fallback.
- No token is exposed through the GUI, logs, evidence, reports, cache, or files.
- Credential-backend and provider failures produce safe, actionable messages.
- No model-selection, prompt, telemetry, or unrelated Settings behavior changes.
