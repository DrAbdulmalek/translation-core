# Remote Translation Data-Flow Audit

**Scope:** static review of `src/translation_core/translator.py` on the default branch at the time of review. This document records observed code paths; it is not a runtime security test or a certification.

## Confirmed observations

| Path | Evidence in source | Data-flow consequence |
|---|---|---|
| `GoogleTranslator.translate()` | Imports `deep_translator.GoogleTranslator`, constructs a provider client, and calls `translator.translate(c)` for each text chunk. | Non-empty input is sent to Google's translation service through the third-party library. |
| `DeepLTranslator.translate()` | Calls `requests.post("https://api-free.deepl.com/v2/translate", ... data={"text": text, ...})`. | Non-empty input is sent to the DeepL API. |
| `Translator()` | Defaults to `engine="google"`. | A caller that does not explicitly select a local engine may select a remote provider by default. |
| `MultiLangTranslator()` | Defaults to `engine="google"`; its Google and DeepL branches instantiate remote-provider adapters. | The multi-language facade also defaults to a remote path. |
| `HFTranslator` | Uses `transformers.pipeline` and loads a named model lazily. | This is not the same as a guaranteed offline mode: model acquisition/cache behavior and network isolation are not controlled by this class. |

## Security gaps established by this review

1. The reviewed translation entry points do not expose a central `LOCAL_ONLY / EXPLICIT_REMOTE / REMOTE_DISABLED` policy.
2. The reviewed Google and DeepL paths do not check whether the text is patient data, personal data, or otherwise restricted before sending it.
3. There is no explicit per-call consent/authorization parameter in these methods.
4. There is no evidence in these methods that a boolean such as `deidentified` is backed by a verified de-identification process.
5. The default engine selection is remote for both `Translator` and `MultiLangTranslator`.

These are source-level findings. They do not prove that every caller sends sensitive information, nor do they establish the behavior of every downstream application.

## Required remediation design (not implemented here)

- Introduce one policy object shared by all translation facades, with explicit modes:
  - `LOCAL_ONLY`: permit only an approved local engine; reject remote providers.
  - `EXPLICIT_REMOTE`: remote use requires a separate, explicit authorization at the call boundary.
  - `REMOTE_DISABLED`: reject all remote providers unconditionally.
- Make the safe default local-only or remote-disabled; do not silently select Google or DeepL for medical workflows.
- Apply the policy before any provider client is constructed and before any text is chunked or transmitted.
- Fail closed when policy configuration is missing, malformed, or ambiguous.
- Do not treat a caller-supplied `deidentified=True` flag as proof of de-identification.
- Add synthetic-only tests with mocked provider clients proving that blocked calls make **zero** network/provider invocations.
- Test both facades (`Translator` and `MultiLangTranslator`) and direct adapter usage. Direct adapters must not bypass the policy.
- Keep model downloads separate from inference policy; an offline mode must prevent network access during model resolution as well as translation.
- Record provider, policy decision, and reason without logging source text, translated text, credentials, or patient identifiers.

## Compatibility and release gate

Changing the default engine or requiring an explicit remote authorization may affect existing consumers. Before a runtime change, inventory callers and define a migration path. Do not weaken the policy to preserve silent remote behavior in medical workflows.

## Evidence classification

- **PROVEN:** The reviewed source contains the Google and DeepL outbound call paths and the remote defaults described above.
- **PARTIALLY PROVEN:** The absence of a central policy is established within the reviewed file; other repository modules and downstream consumers were not exhaustively audited in this pass.
- **UNPROVEN:** No live network interception, offline sandbox test, or downstream application integration test was performed.
- **NOT CLAIMED:** This audit does not certify HIPAA/GDPR compliance, clinical safety, or complete de-identification.
