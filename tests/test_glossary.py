# tests/test_glossary.py
"""اختبارات المسرد: التحميل (YAML/JSON/مطّح)، الكشف، الفرض، الأشكال الممنوعة."""
import pytest

from translation_core.glossary import Glossary, GlossaryViolation


FLAT = {"dataset": "مجموعة البيانات", "pipeline": "خط المعالجة"}

NESTED = {
    "terms": {
        "dataset": {
            "target": "مجموعة البيانات",
            "alt": ["داتاسِت", "قاعدة البيانات"],
            "notes": "ممنوع داتاسِت",
        },
        "pipeline": {"target": "خط المعالجة"},
    }
}


# ---------- التحميل ----------
def test_flat_entries():
    g = Glossary(entries=FLAT)
    assert len(g) == 2
    assert g.get("dataset").target == "مجموعة البيانات"


def test_nested_entries_with_alt():
    g = Glossary(entries=NESTED)
    e = g.get("dataset")
    assert e.target == "مجموعة البيانات"
    assert "داتاسِت" in e.alt
    assert e.notes


def test_load_yaml_file(tmp_path):
    p = tmp_path / "g.yaml"
    p.write_text(
        "terms:\n  pipeline:\n    target: خط المعالجة\n", encoding="utf-8")
    g = Glossary(path=str(p))
    assert len(g) == 1


def test_load_json_file(tmp_path):
    import json
    p = tmp_path / "g.json"
    p.write_text(json.dumps(NESTED, ensure_ascii=False), encoding="utf-8")
    g = Glossary(path=str(p))
    assert g.get("pipeline").target == "خط المعالجة"


def test_rejects_missing_target():
    with pytest.raises(ValueError):
        Glossary(entries={"terms": {"bad": {"alt": ["x"]}}})


def test_rejects_unknown_extension(tmp_path):
    p = tmp_path / "g.txt"
    p.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        Glossary(path=str(p))


# ---------- الكشف في المصدر ----------
def test_detect_word_boundaries():
    g = Glossary(entries=FLAT)
    found = g.detect("The dataset and the pipeline are ready.")
    assert sorted(found) == ["dataset", "pipeline"]


def test_detect_avoids_substring_matches():
    """[عقد] مطابقة كلمة لا سلسلة فرعية: "datasets" ليست "dataset"."""
    g = Glossary(entries=FLAT)
    assert g.detect("Many datasets exist.") == []


def test_detect_arabic_case_insensitive():
    g = Glossary(entries={"Model": "النموذج"})
    assert g.detect("The MODEL is fast.") == ["Model"]


# ---------- الاقتراح ----------
def test_suggest_returns_pairs():
    g = Glossary(entries=FLAT)
    s = g.suggest("A dataset flows through a pipeline.")
    assert {"term": "dataset", "target": "مجموعة البيانات"} in s
    assert {"term": "pipeline", "target": "خط المعالجة"} in s


# ---------- الفرض ----------
def test_validate_passes_when_canonical_used():
    g = Glossary(entries=NESTED)
    assert g.validate(
        "The dataset is ready.",
        "مجموعة البيانات جاهزة.",
    ) == []


def test_validate_flags_banned_alt():
    g = Glossary(entries=NESTED)
    # الشكل الممنوع مستقل (بين مسافتين) — حدود الكلمات تعمل على العربية
    v = g.validate("The dataset is ready.", "هذه داتاسِت جاهزة.")
    assert len(v) == 1
    assert isinstance(v[0], GlossaryViolation)
    assert v[0].term == "dataset"
    assert v[0].found_alt == "داتاسِت"


def test_validate_flags_missing_canonical():
    g = Glossary(entries={"terms": {"pipeline": {"target": "خط المعالجة"}}})
    v = g.validate("The pipeline works.", "الأنبوب يعمل.")
    assert len(v) == 1
    assert v[0].found_alt is None
    assert "غائبة" in v[0].reason


def test_validate_ignores_absent_terms():
    """مصطلح غير موجود في المصدر لا يُحاسَب في الهدف."""
    g = Glossary(entries=NESTED)
    assert g.validate("Nothing relevant here.", "لا علاقة له.") == []


def test_validate_asdict_shape():
    g = Glossary(entries=NESTED)
    v = g.validate("The dataset is ready.", "قاعدة البيانات جاهزة.")
    d = v[0].asdict()
    assert set(d.keys()) == {"term", "expected", "found_alt", "reason"}
