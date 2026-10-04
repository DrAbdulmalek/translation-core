# tests/test_lang_support.py
"""منقول من marathon tests/test_lang_support.py — الجزء الخاص بالنواة.

[PORT] اختبارات سجل اللغات وعقد المحركات فقط (7 من 14). البقية
(7 اختبارات: config.yaml، ted_fetcher، ci.yml، api.py، dashboard.py)
خاصة بتطبيق marathon وتبقى فيه — إدراجها هنا سيرفع اعتماديات لا
تنتمي للنواة.

[PORT] المسارات: `ROOT / "config/languages.yaml"` → مسار بيانات
الحزمة (`translation_core/config/languages.yaml`) عبر وحدة
`translation_core.languages` نفسها.
"""
import inspect

import pytest

import translation_core.languages as lang_mod
from translation_core.languages import LanguageRegistry, get_registry
from translation_core.translator import (
    FinetunedTranslator,
    HFTranslator,
    TranslationResult,
)

PKG_YAML = lang_mod._DEFAULT_CONFIG_PATH


# ---------- الإصلاح 1: en في languages.yaml ----------
def test_registry_defines_en():
    reg = LanguageRegistry(path=PKG_YAML)
    assert reg.get("en") is not None
    assert "en" in reg.list_all()
    assert reg.list_all() == sorted(
        reg.list_all(), key=lambda c: (c != "en", c)
    ) or len(reg.list_all()) >= 11


def test_en_models_mapping():
    reg = LanguageRegistry(path=PKG_YAML)
    en = reg.get("en")
    assert en["rtl"] is False
    assert en["models"]["google"] == "en"
    assert en["models"]["deepl"] == "EN"
    assert en["models"]["nllb"] == "eng_Latn"
    # بلا نموذج marian — get_model_id يعيد None بوضوح (فشل صادق لا خاطس)
    assert reg.get_model_id("en", "marian") is None


def test_rtl_flags():
    reg = LanguageRegistry(path=PKG_YAML)
    assert reg.is_rtl("ar") is True
    assert reg.is_rtl("en") is False
    assert reg.is_rtl("fa") is True


# ---------- الإصلاح 2: عقد FinetunedTranslator ----------
def test_finetuned_signature_and_contract():
    sig = inspect.signature(FinetunedTranslator.__init__)
    # الدمج مع نسخة Qwen: init صار (model_dir=None) مع حل مسار CWD-مستقل،
    # والاتجاه انقل إلى translate(src,tgt) — لا باراميترات src/tgt في init.
    assert "model_dir" in sig.parameters
    tr_sig = inspect.signature(FinetunedTranslator.translate)
    assert tr_sig.return_annotation is TranslationResult


# ---------- الإصلاح 3: اختيار نموذج HF حسب الاتجاه ----------
def test_hf_model_selection_by_direction():
    # الدمج: الجدول صار HFTranslator.PAIR_MODELS والاختيار عبر select_model
    assert HFTranslator.PAIR_MODELS[("en", "ar")] == "Helsinki-NLP/opus-mt-en-ar"
    assert HFTranslator.PAIR_MODELS[("ar", "en")] == "Helsinki-NLP/opus-mt-ar-en"
    t = HFTranslator()  # بلا تحميل — init كسول
    assert t.select_model("en", "ar") == "Helsinki-NLP/opus-mt-en-ar"
    assert t.select_model("ar", "en") == "Helsinki-NLP/opus-mt-ar-en"
    # زوج غير موجود في PAIR_MODELS لكنه في سجل اللغات (es لديها marian)
    # → select_model يرجع نموذج السجل ويحذّر على عدم تطابق المصدر — سلوك أغنى
    # من الافتراضي الأعمى، وهو العقد المصمم لنسخة Qwen.
    assert t.select_model("fr", "es") == "Helsinki-NLP/opus-mt-en-es"
    # زوج مجهول كليًا (لا جدول لا سجل) → الافتراضي الآمن en→ar
    assert t.select_model("zz", "qq") == "Helsinki-NLP/opus-mt-en-ar"
    # نموذج صريح يتجاوز كل شيء
    t2 = HFTranslator(model_name="custom/model")
    assert t2.select_model("ar", "en") == "custom/model"


# ---------- الإصلاح 6: المسار الافتراضي مستقل عن CWD ----------
def test_default_registry_cwd_independent(tmp_path, monkeypatch):
    """LanguageRegistry() بالمسار الافتراضي يجب أن تعمل من أي دليل عمل.

    قبل الإصلاح كان CONFIG_PATH نسبيًا (config/languages.yaml) →
    FileNotFoundError فور الخروج من جذر المستودع. هذا الاختبار كان سيفشل
    قبل الإصلاح وهو قفله الانحداري.
    """
    monkeypatch.chdir(tmp_path)  # دليل بلا config/languages.yaml
    reg = LanguageRegistry()  # بلا مسار صريح — المسار الافتراضي بالضبط
    assert reg.get("en") is not None
    assert reg.is_rtl("ar") is True
    assert len(reg.list_all()) >= 11


def test_get_registry_singleton_from_foreign_cwd(tmp_path, monkeypatch):
    """get_registry() (المفرد) يعمل من CWD غريب ويعيد نفس المثيل."""
    monkeypatch.chdir(tmp_path)
    r1 = get_registry()
    r2 = get_registry()
    assert r1 is r2
    assert r1.get("ar") is not None
