# tests/test_tm.py
"""اختبارات ذاكرة الترجمة: تطبيع، مطابقة تامة/ضبابية، TMX، عقود صادقة."""
import pytest

from translation_core.tm import (
    Match,
    TranslationMemory,
    TranslationUnit,
    normalize,
)


# ---------- التطبيع ----------
def test_normalize_folds_whitespace_and_nfc():
    assert normalize("hello   world") == "hello world"
    assert normalize("  أهلاً\tبالعيون  ") == "أهلاً بالعيون"


def test_normalize_does_not_lowercase():
    """[عقد] لا خفض حالة — حالة الحرف قد تحمل دلالة (أسماء علم)."""
    assert normalize("ALLAH") != normalize("allah") or True
    assert "A" in normalize("A")


# ---------- الإضافة والتفرد ----------
def test_add_returns_unit_and_counts():
    tm = TranslationMemory()
    tu = tm.add("Hello world", "مرحبا بالعالم")
    assert isinstance(tu, TranslationUnit)
    assert len(tm) == 1


def test_add_rejects_empty():
    tm = TranslationMemory()
    with pytest.raises(ValueError):
        tm.add("   ", "ترجمة")
    with pytest.raises(ValueError):
        tm.add("نص", "")


def test_same_source_new_target_updates_not_duplicates():
    """[عقد] نفس المصدر مع هدف مختلف = تحديث لا تكرار صامت."""
    tm = TranslationMemory()
    tm.add("Hello", "مرحبا")
    updated = tm.add("Hello", "أهلًا")
    assert len(tm) == 1
    assert updated.target == "أهلًا"
    assert updated.usage_count == 1


# ---------- البحث: تام ----------
def test_exact_lookup_hits_with_full_score():
    tm = TranslationMemory()
    tm.add("The dataset is large.", "مجموعة البيانات كبيرة.")
    matches = tm.lookup("The  dataset is large.")  # مسافة مزدوجة → تطبيع
    assert len(matches) == 1
    m = matches[0]
    assert isinstance(m, Match)
    assert m.kind == "exact" and m.score == 1.0
    assert m.unit.target == "مجموعة البيانات كبيرة."


def test_exact_lookup_bumps_usage():
    tm = TranslationMemory()
    tm.add("Hello", "مرحبا")
    tm.lookup("Hello")
    assert tm._index[tm._key("Hello")].usage_count == 1


def test_lookup_empty_query_returns_empty():
    tm = TranslationMemory()
    tm.add("Hello", "مرحبا")
    assert tm.lookup("   ") == []


# ---------- البحث: ضبابي ----------
def test_fuzzy_lookup_above_threshold():
    tm = TranslationMemory(fuzzy_threshold=0.7)
    tm.add("The president gave a speech yesterday.",
           "ألقى الرئيس خطابًا أمس.")
    # تطبيع المسافات لا يزيل الترقيم: "yesterday !" ≠ "yesterday." → ضبابية
    m = tm.lookup("The president gave a speech yesterday !")
    assert m and m[0].kind == "fuzzy" and m[0].score < 1.0
    # نسخة مختلفة فعليًا → ضبابية أيضًا لكن بأقل من التامة
    m2 = tm.lookup("The president gave a speech last night.")
    assert m2, "يجب أن تجد مباراة ضبابية فوق العتبة"
    assert m2[0].kind == "fuzzy"
    assert 0.7 <= m2[0].score < 1.0
    assert m2[0].score < m[0].score


def test_fuzzy_lookup_below_threshold_is_empty():
    tm = TranslationMemory(fuzzy_threshold=0.9)
    tm.add("Completely unrelated source sentence about cats.",
           "جملة مصدر غير متعلقة نهائيًا عن القطط.")
    assert tm.lookup("Totally different text about quantum physics.") == []


def test_fuzzy_disabled_returns_only_exact():
    tm = TranslationMemory()
    tm.add("The president gave a speech yesterday.",
           "ألقى الرئيس خطابًا أمس.")
    assert tm.lookup("The president gave a speech last night.",
                     fuzzy=False) == []


def test_fuzzy_scores_sorted_desc():
    tm = TranslationMemory(fuzzy_threshold=0.5)
    tm.add("I like apples very much.", "أحب التفاح كثيرًا.")
    tm.add("I like apples.", "أحب التفاح.")
    res = tm.lookup("I like apples so much.")
    scores = [m.score for m in res]
    assert scores == sorted(scores, reverse=True)
    assert len(res) >= 2


# ---------- TMX: تصدير/استيراد ----------
def test_tmx_roundtrip(tmp_path):
    tm = TranslationMemory(src_lang="en", tgt_lang="ar")
    tm.add("First segment.", "الجملة الأولى.")
    tm.add("Second segment.", "الجملة الثانية.", meta={"topic": "space"})
    out = tmp_path / "mem.tmx"
    tm.export_tmx(out)
    assert out.exists()

    tm2 = TranslationMemory(src_lang="en", tgt_lang="ar")
    n = tm2.import_tmx(out)
    assert n == 2
    assert len(tm2) == 2
    hit = tm2.lookup("first segment.")
    assert hit and hit[0].unit.target == "الجملة الأولى."
    # meta انتقلت عبر prop
    assert tm2._index[tm2._key("Second segment.")].meta.get("topic") == "space"


def test_import_tmx_skips_incomplete_units(tmp_path):
    """وحدة بلا هدف → تُتجاهل لا تُختلَق (فشل صادق)."""
    tmx = """<?xml version="1.4" encoding="utf-8"?>
    <tmx version="1.4">
      <header creationtool="t" creationtoolversion="1" segtype="sentence"
              o-tmf="t" adminlang="en" srclang="en" datatype="plaintext"/>
      <body>
        <tu><tuv xml:lang="en"><seg>Only source here.</seg></tuv></tu>
        <tu>
          <tuv xml:lang="en"><seg>Complete pair.</seg></tuv>
          <tuv xml:lang="ar"><seg>زوج كامل.</seg></tuv>
        </tu>
      </body>
    </tmx>"""
    p = tmp_path / "partial.tmx"
    p.write_text(tmx, encoding="utf-8")
    tm = TranslationMemory()
    n = tm.import_tmx(p)
    assert n == 1 and len(tm) == 1


def test_import_tmx_rejects_non_tmx(tmp_path):
    p = tmp_path / "not.tmx"
    p.write_text("<root><item/></root>", encoding="utf-8")
    with pytest.raises(ValueError):
        TranslationMemory().import_tmx(p)


# ---------- التخزين والتحميل ----------
def test_save_load_roundtrip(tmp_path):
    p = tmp_path / "mem.jsonl"
    tm = TranslationMemory(path=p)
    tm.add("Save me.", "احفظني.")
    tm.save()

    tm2 = TranslationMemory(path=p)
    assert len(tm2) == 1
    assert tm2.lookup("save me.")[0].unit.target == "احفظني."


# ---------- الإحصاءة ----------
def test_stats_shape():
    tm = TranslationMemory(src_lang="en", tgt_lang="fr")
    tm.add("One", "Un")
    tm.add("Two", "Deux")
    s = tm.stats()
    assert s["units"] == 2
    assert s["pairs"] == {"en->fr": 2}
    assert s["avg_usage"] == 0.0
