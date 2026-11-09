"""Synthetic tests for fail-closed outbound translation policy."""
import sys
import types

import pytest

from translation_core.policy import (
    DEFAULT_TRANSLATION_POLICY,
    RemoteTranslationBlocked,
    TranslationPolicy,
)
from translation_core.translator import (
    DeepLTranslator,
    GoogleTranslator,
    MultiLangTranslator,
    Translator,
)


def test_default_policy_is_local_only():
    assert DEFAULT_TRANSLATION_POLICY.mode == "LOCAL_ONLY"
    assert DEFAULT_TRANSLATION_POLICY.remote_authorized is False


@pytest.mark.parametrize("adapter", [GoogleTranslator, DeepLTranslator])
def test_direct_remote_adapter_blocks_before_provider_import(adapter, monkeypatch):
    called = []
    if adapter is GoogleTranslator:
        fake = types.ModuleType("deep_translator")
        class FakeGoogle:
            def __init__(self, **kwargs):
                called.append(("init", kwargs))
            def translate(self, text):
                called.append(("translate", text))
                return text
        fake.GoogleTranslator = FakeGoogle
        monkeypatch.setitem(sys.modules, "deep_translator", fake)
    else:
        fake = types.ModuleType("requests")
        def post(*args, **kwargs):
            called.append(("post", args, kwargs))
            raise AssertionError("network path must not be reached")
        fake.post = post
        monkeypatch.setitem(sys.modules, "requests", fake)

    with pytest.raises(RemoteTranslationBlocked):
        adapter().translate("synthetic patient-free text", src="en", tgt="ar")
    assert called == []


@pytest.mark.parametrize("engine", ["google", "deepl"])
def test_translator_facade_blocks_remote_by_default(engine):
    with pytest.raises(RemoteTranslationBlocked):
        Translator(engine=engine).translate("synthetic text")


@pytest.mark.parametrize("engine", ["google", "deepl"])
def test_multilang_facade_blocks_remote_by_default(engine):
    with pytest.raises(RemoteTranslationBlocked):
        MultiLangTranslator(engine=engine).translate("synthetic text")


def test_explicit_remote_policy_allows_mocked_google(monkeypatch):
    calls = []
    fake = types.ModuleType("deep_translator")
    class FakeGoogle:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))
        def translate(self, text):
            calls.append(("translate", text))
            return "synthetic output"
    fake.GoogleTranslator = FakeGoogle
    monkeypatch.setitem(sys.modules, "deep_translator", fake)

    policy = TranslationPolicy(mode="EXPLICIT_REMOTE", remote_authorized=True)
    result = GoogleTranslator(policy=policy).translate("synthetic input", "en", "ar")
    assert result.translated_text == "synthetic output"
    assert [c[0] for c in calls] == ["init", "translate"]


def test_explicit_remote_requires_affirmative_authorization():
    with pytest.raises(ValueError):
        TranslationPolicy(mode="EXPLICIT_REMOTE")
    with pytest.raises(ValueError):
        TranslationPolicy(mode="LOCAL_ONLY", remote_authorized=True)


def test_remote_disabled_cannot_be_overridden():
    policy = TranslationPolicy(mode="REMOTE_DISABLED")
    with pytest.raises(RemoteTranslationBlocked):
        GoogleTranslator(policy=policy).translate("synthetic text")
