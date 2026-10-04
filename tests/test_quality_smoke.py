# tests/test_quality_smoke.py
"""اختبارات دخان لحزمة الجودة وab_testing — بلا اعتماديات ثقيلة.

ما لا يُختبر هنا عمدًا: استدعاء `evaluate` الحقيقي (يتطلب HF evaluate +
نماذج) — تُختبر العقود والبيانات الخلفية (SQLite) والمنطق النقي.
"""
import pytest

from translation_core.quality import QualityEvaluator, QualityScore
from translation_core.quality import auto_quality as aq
from translation_core.quality import sampler
from translation_core import ab_testing as ab


# ---------- QualityScore: العقد الافتراضي ----------
def test_quality_score_defaults_are_all_none():
    s = QualityScore()
    assert s.bleu is None and s.chrf is None and s.meteor is None
    assert s.comet is None and s.bertscore is None
    assert s.overall is None and s.level == "unknown"


def test_evaluator_init_lazy_no_side_effects():
    """init لا يحمل شيئًا — الاعتماديات الثقيلة كسولة وقت evaluate."""
    e = QualityEvaluator(use_comet=True, use_bertscore=True)
    assert e._bleu is None and e._comet is None and e._bertscore is None


def test_evaluator_to_dict_roundtrip():
    e = QualityEvaluator()
    s = QualityScore(bleu=42.0, chrf=50.0, overall=46.0, level="fair")
    d = e.to_dict(s)
    assert d["bleu"] == 42.0 and d["level"] == "fair"


# ---------- auto_quality: دفة SQLite الكاملة ----------
def test_auto_quality_record_and_read(tmp_path, monkeypatch):
    db = tmp_path / "q.db"
    monkeypatch.setattr(aq, "DB_PATH", db)
    aq.init_db()
    s = QualityScore(bleu=30, chrf=40, meteor=35, overall=35.0, level="fair")
    aq.record_run("hf", "m1", samples=10, score=s)
    aq.record_run("google", None, samples=10, score=s)
    runs = aq.get_recent_runs(limit=5)
    assert len(runs) == 2
    assert runs[0]["engine"] in ("hf", "google")
    assert runs[0]["overall"] == 35.0


def test_auto_quality_degradation_detected(tmp_path, monkeypatch):
    db = tmp_path / "deg.db"
    monkeypatch.setattr(aq, "DB_PATH", db)
    aq.init_db()
    good = QualityScore(overall=80.0, level="excellent")
    bad = QualityScore(overall=50.0, level="fair")
    for _ in range(5):
        aq.record_run("hf", "m", 5, good)
    for _ in range(5):
        aq.record_run("hf", "m", 5, bad)
    msg = aq.detect_degradation(window=5, threshold=10.0)
    assert msg is not None and "تدهور" in msg


def test_auto_quality_no_degradation_under_threshold(tmp_path, monkeypatch):
    db = tmp_path / "nodeg.db"
    monkeypatch.setattr(aq, "DB_PATH", db)
    aq.init_db()
    for _ in range(5):
        aq.record_run("hf", "m", 5, QualityScore(overall=80.0))
    for _ in range(5):
        aq.record_run("hf", "m", 5, QualityScore(overall=75.0))
    assert aq.detect_degradation(window=5, threshold=10.0) is None


# ---------- sampler: عينات من ملفات JSON ----------
def test_sampler_returns_pairs(tmp_path, monkeypatch):
    ddir = tmp_path / "downloads"
    ddir.mkdir()
    (ddir / "a.json").write_text(
        '{"source_text": "hello", "target_text": "مرحبا"}', encoding="utf-8")
    (ddir / "b.json").write_text(
        '{"source_text": "world", "target_text": "عالم"}', encoding="utf-8")
    monkeypatch.setattr(sampler, "DATA_DIR", ddir)
    pairs = sampler.sample_pairs(n=10, seed=1)
    assert len(pairs) == 2
    assert {"source", "target", "file"} <= set(pairs[0].keys())


# ---------- ab_testing: دورة حياة تجربة كاملة ----------
@pytest.fixture()
def ab_db(tmp_path, monkeypatch):
    db = tmp_path / "ab.db"
    monkeypatch.setattr(ab, "DB_PATH", db)
    ab.init_db()
    return db


def test_ab_create_and_get(ab_db):
    exp_id = ab.create_experiment(
        "exp1", "وصف",
        variants=[{"name": "a", "weight": 50}, {"name": "b", "weight": 50}],
        metric="bleu",
    )
    assert isinstance(exp_id, int)
    got = ab.get_experiment("exp1")
    assert got is not None and got["status"] == "active"
    assert got["metric"] == "bleu"


def test_ab_assign_variant_deterministic(ab_db):
    ab.create_experiment(
        "det", "",
        variants=[{"name": "ctrl"}, {"name": "treat"}], metric="bleu")
    v1 = ab.assign_variant("det", "user-42")
    v2 = ab.assign_variant("det", "user-42")
    assert v1 == v2  # نفس الوحدة → نفس المتغير دائمًا (هاش حتمي)
    assert v1 in ("ctrl", "treat")


def test_ab_unknown_experiment_returns_none(ab_db):
    """عقد صادق: تجربة غير موجودة/غير نشطة → None لا استثناء."""
    assert ab.assign_variant("no-such-exp", "u1") is None


def test_ab_analyze_picks_better_variant(ab_db):
    ab.create_experiment(
        "win", "",
        variants=[{"name": "weak"}, {"name": "strong"}], metric="bleu")
    for i in range(60):
        u = f"u{i}"
        ab.assign_variant("win", u)  # يُسجَّل التخصيص أولًا (عقد record_result)
    # بعد التخصيص: نسجّل قيمة لكل وحدة — القراءة من جدول assignments
    import sqlite3
    conn = sqlite3.connect(ab_db)
    rows = conn.execute(
        "SELECT unit_id, variant FROM assignments WHERE experiment_id = "
        "(SELECT id FROM experiments WHERE name = 'win')").fetchall()
    conn.close()
    for unit_id, variant in rows:
        val = 40.0 if variant == "weak" else 90.0
        assert ab.record_result("win", unit_id, val) is True
    res = ab.analyze_experiment("win")
    assert "error" not in res
    assert res["variants"]["strong"]["mean"] > res["variants"]["weak"]["mean"]
    assert res["winner"] == "strong"


def test_ab_auto_select_winner(ab_db):
    ab.create_experiment(
        "auto", "",
        variants=[{"name": "w1"}, {"name": "w2"}], metric="bleu")
    import sqlite3
    for i in range(300):
        ab.assign_variant("auto", f"x{i}")
    conn = sqlite3.connect(ab_db)
    rows = conn.execute(
        "SELECT unit_id, variant FROM assignments WHERE experiment_id = "
        "(SELECT id FROM experiments WHERE name = 'auto')").fetchall()
    conn.close()
    for unit_id, variant in rows:
        base = 30.0 if variant == "w1" else 95.0
        # اهتزاز حتمي حتى لا تكون std=0 (وهي تُبطل t-test بالتعريف: se=0)
        jitter = (int(unit_id[1:]) % 10) * 0.1
        ab.record_result("auto", unit_id, base + jitter)
    out = ab.auto_select_winner("auto", min_samples=100)
    assert out == "w2"
