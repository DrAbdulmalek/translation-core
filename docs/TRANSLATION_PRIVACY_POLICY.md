# Translation privacy policy

## Default-deny behavior

The Google and DeepL adapters now require an explicit policy permitting remote
processing. The default is `LOCAL_ONLY`; therefore direct adapter use and both
facades (`Translator` and `MultiLangTranslator`) reject Google/DeepL calls
before importing or invoking their provider clients.

```python
from translation_core import Translator, RemoteTranslationBlocked

# Safe default: remote provider call is rejected.
translator = Translator(engine="google")
try:
    translator.translate("synthetic text", src="en", tgt="ar")
except RemoteTranslationBlocked:
    pass
```

## Explicit remote authorization

Remote processing must be deliberately authorized by the application boundary:

```python
from translation_core import TranslationPolicy, Translator

policy = TranslationPolicy(
    mode="EXPLICIT_REMOTE",
    remote_authorized=True,
)
translator = Translator(engine="deepl", policy=policy)
```

This authorization is a caller decision, not proof of consent, de-identification,
legal basis, or clinical suitability. Applications must obtain and record any
required authorization before constructing or using this policy. Never pass
patient data merely because this flag is set.

## Modes

| Mode | Google / DeepL |
|---|---|
| `LOCAL_ONLY` (default) | Blocked |
| `EXPLICIT_REMOTE` with `remote_authorized=True` | Permitted |
| `REMOTE_DISABLED` | Always blocked |

Invalid or ambiguous policy configuration raises an exception.

## Important scope limitation: Hugging Face

This change gates outbound calls through Google and DeepL. It does **not** yet
guarantee offline model resolution for `HFTranslator` or
`FinetunedTranslator`. Hugging Face/Transformers may attempt to resolve or
download model files unless the deployment separately pins local model paths,
uses an offline cache, and enforces network isolation (for example,
`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and an OS/container network
policy). Environment flags alone are not a security boundary.

Do not describe the entire package as offline-safe until model loading and all
other network-capable dependencies have been audited and tested in an isolated
environment.

## Logging and data handling

The policy exception contains the provider and policy mode, not source text.
Callers should avoid logging source text, translated text, credentials, patient
identifiers, or provider request payloads. This module does not perform PHI
detection or de-identification.

## Verification status

Synthetic tests mock provider modules and assert that blocked calls do not
reach provider constructors or request functions. These tests do not replace
network-denied integration tests, dependency auditing, downstream consumer
review, or clinical validation.
