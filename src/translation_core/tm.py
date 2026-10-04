"""ذاكرة الترجمة (Translation Memory) — نمط OmegaT/Trados.

الميزات:
- تخزين وحدات الترجمة (Translation Units) في JSONL — سطر لكل وحدة:
  قابل للمراجعة بـ git diff، بلا اعتماديات، وبلا خادم.
- بحث مطابق تام (exact) بعد تطبيع NFC/مسافات، ومطابقة ضبابية (fuzzy)
  بحد أدنى قابل للضبط.
- التطبيع: unicodedata NFC + طي مسافات — يمتص انزياحات الأشكال العربية
  من مصادر مختلفة (يدوي/آلي) بلا تخمين.
- TMX 1.4b import/export (xml.etree.ElementTree) للتوافق مع OmegaT /
  Trados / memoQ.
- تسريع اختياري عبر rapidfuzz عند توفره؛ الاحتياط difflib (دقيق
  وحتمي، أبطأ فقط). النتيجة لا تعتمد على تخمين: كل مباراة تحمل
  kind ∈ {exact, fuzzy} وscore ∈ [0, 1] محسوبًا فعليًا.

ثقة حقيقية لا مختلقة: المباراة إما مطابقة تامة (1.0) أو نسبة تشابه
محسوبة من النصوص نفسها — صفر نقاط تُختلق.
"""
from __future__ import annotations

import difflib
import json
import logging
import re
import unicodedata
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:  # تسريع اختياري — الاحتياط حتمي
    from rapidfuzz import fuzz as _rfuzz
except ImportError:  # pragma: no cover - مسار الاختبار الصريح موجود
    _rfuzz = None


_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """تطبيع محفوظ للمقارنة: NFC + طي المسافات + تقليم.

    [تصميم] عمدًا لا يخفض الأحرف: في العربية الأحرف لا حالة لها، وفي
    الإنجليزية حالة الحرف قد تحمل دلالة (أسماء علم). المطابقة التامة
    هنا "تطابق بعد تنظيف" — وأي تساهل إضافي يُقاس في المباراة الضبابية.
    """
    return _WS_RE.sub(" ", unicodedata.normalize("NFC", text or "")).strip()


@dataclass
class TranslationUnit:
    """وحدة ترجمة واحدة: زوج (مصدر، هدف) + تتبع استخدام."""

    source: str
    target: str
    src_lang: str = "en"
    tgt_lang: str = "ar"
    meta: Dict = field(default_factory=dict)
    usage_count: int = 0
    last_used: Optional[str] = None
    created_at: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class Match:
    """نتيجة بحث في الذاكرة."""

    unit: TranslationUnit
    score: float          # 0..1 — محسوب فعليًا لا مُختلقًا
    kind: str             # "exact" | "fuzzy"


class TranslationMemory:
    """ذاكرة ترجمة ملفية (JSONL) مع بحث تام/ضبابي وTMX."""

    def __init__(self,
                 path: Optional[str] = None,
                 src_lang: str = "en",
                 tgt_lang: str = "ar",
                 fuzzy_threshold: float = 0.75,
                 use_rapidfuzz: bool = True):
        self.path = Path(path) if path else None
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        if not 0 < fuzzy_threshold <= 1:
            raise ValueError("fuzzy_threshold يجب أن يكون في (0, 1]")
        self.fuzzy_threshold = fuzzy_threshold
        self.use_rapidfuzz = bool(use_rapidfuzz and _rfuzz)
        self._units: List[TranslationUnit] = []
        self._index: Dict[str, TranslationUnit] = {}
        if self.path and self.path.exists():
            self._load()

    # ------------------------------------------------------------------
    # التخزين
    # ------------------------------------------------------------------
    def _load(self):
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                tu = TranslationUnit(**d)
                self._units.append(tu)
                self._index[self._key(tu.source)] = tu

    def save(self) -> Optional[Path]:
        """يكتب كل الوحدات إلى الملف (JSONL). يعيد المسار إن وُجد."""
        if not self.path:
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            for tu in self._units:
                f.write(json.dumps(asdict(tu), ensure_ascii=False) + "\n")
        return self.path

    # ------------------------------------------------------------------
    # الإضافة والبحث
    # ------------------------------------------------------------------
    @staticmethod
    def _key(source: str) -> str:
        return normalize(source)

    def __len__(self) -> int:
        return len(self._units)

    def add(self, source: str, target: str,
            meta: Optional[Dict] = None) -> TranslationUnit:
        """يضيف وحدة (أو يحدّث القائمة إن كان المصدر موجودًا).

        [عقد] نفس المصدر مع هدف مختلف = **تحديث** للهدف (آخر ترجمة
        معتمدة تربح) مع زيادة عدّاد الاستخدام — لا تكرار صامت.
        """
        if not normalize(source) or not normalize(target):
            raise ValueError("لا يمكن إضافة وحدة بنص فارغ")
        key = self._key(source)
        existing = self._index.get(key)
        if existing is not None:
            existing.target = target
            existing.usage_count += 1
            existing.last_used = datetime.now(timezone.utc).isoformat()
            if meta:
                existing.meta.update(meta)
            return existing
        tu = TranslationUnit(
            source=source, target=target,
            src_lang=self.src_lang, tgt_lang=self.tgt_lang,
            meta=dict(meta or {}),
        )
        self._units.append(tu)
        self._index[key] = tu
        return tu

    def _similarity(self, a: str, b: str) -> float:
        """نسبة تشابه حقيقية في [0, 1] — محسوبة لا معلَنة."""
        if self.use_rapidfuzz and _rfuzz is not None:
            return _rfuzz.ratio(a, b) / 100.0
        return difflib.SequenceMatcher(None, a, b).ratio()

    def lookup(self, source: str, fuzzy: bool = True,
               limit: int = 5) -> List[Match]:
        """يبحث عن أفضل المباريات للمصدر المطلوب.

        التامة أولًا (score=1.0)؛ وإلا ضبابية ≥ العتبة، مرتبة تنازليًا.
        لا تعيد أبدًا نتيجة بلا دليل (score محسوب من النصوص).
        """
        q = self._key(source)
        if not q:
            return []
        exact = self._index.get(q)
        if exact is not None:
            exact.usage_count += 1
            exact.last_used = datetime.now(timezone.utc).isoformat()
            return [Match(unit=exact, score=1.0, kind="exact")]
        if not fuzzy:
            return []
        matches: List[Match] = []
        for tu in self._units:
            score = self._similarity(q, self._key(tu.source))
            if score >= self.fuzzy_threshold:
                matches.append(Match(unit=tu, score=round(score, 4),
                                     kind="fuzzy"))
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:max(1, limit)]

    def stats(self) -> Dict:
        """إحصاءة سريعة: عدد الوحدات، أزواج اللغات، متوسط الاستخدام."""
        pairs = {}
        total_usage = 0
        for tu in self._units:
            pair = f"{tu.src_lang}->{tu.tgt_lang}"
            pairs[pair] = pairs.get(pair, 0) + 1
            total_usage += tu.usage_count
        return {
            "units": len(self._units),
            "pairs": pairs,
            "avg_usage": round(total_usage / len(self._units), 3)
                         if self._units else 0.0,
        }

    # ------------------------------------------------------------------
    # TMX 1.4b — توافق معيار الصناعة
    # ------------------------------------------------------------------
    def export_tmx(self, path: str) -> Path:
        """يصدّر الذاكرة إلى TMX 1.4b (ElementTree — بلا اعتماديات)."""
        tmx = ET.Element("tmx", version="1.4")
        ET.SubElement(tmx, "header", {
            "creationtool": "translation-core",
            "creationtoolversion": "0.1.0",
            "segtype": "sentence",
            "o-tmf": "translation-core",
            "adminlang": "en",
            "srclang": self.src_lang,
            "datatype": "plaintext",
        })
        body = ET.SubElement(tmx, "body")
        for tu in self._units:
            el = ET.SubElement(body, "tu")
            if tu.usage_count:
                ET.SubElement(el, "prop",
                              {"type": "x-usage-count"}
                              ).text = str(tu.usage_count)
            if tu.meta:
                ET.SubElement(el, "prop", {"type": "x-meta"}
                              ).text = json.dumps(tu.meta, ensure_ascii=False)
            for lang, text in ((tu.src_lang, tu.source),
                               (tu.tgt_lang, tu.target)):
                tuv = ET.SubElement(el, "tuv", {"xml:lang": lang})
                seg = ET.SubElement(tuv, "seg")
                seg.text = text
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(tmx).write(out, encoding="utf-8",
                                  xml_declaration=True)
        return out

    def import_tmx(self, path: str) -> int:
        """يستورد TMX 1.4b ويعيد عدد الوحدات المستوردة فعلًا.

        يتجاهل وحدات tuc (وحدات بلا هدف) ويزيد usage_count من prop.
        [أمان] ElementTree لا ينفّذ كيانات خارجية — الملفات الضارة
        بشبكات خارجية تُرفض من التقرير القياسي (ولا نستورد إلا ملفات
        يملكها المشروع).
        """
        tree = ET.parse(path)
        root = tree.getroot()
        if not root.tag.endswith("tmx"):
            raise ValueError(f"ليس ملف TMX: الجذر {root.tag}")
        body = root.find("body")
        if body is None:
            return 0
        count = 0
        for tu_el in body.findall("tu"):
            segs: Dict[str, str] = {}
            usage = 0
            meta_extra: Dict = {}
            for prop in tu_el.findall("prop"):
                if prop.get("type") == "x-usage-count":
                    try:
                        usage = int((prop.text or "0").strip())
                    except ValueError:
                        usage = 0
                elif prop.get("type") == "x-meta":
                    try:
                        meta_extra = json.loads(prop.text or "{}")
                    except ValueError:
                        meta_extra = {}
            for tuv in tu_el.findall("tuv"):
                lang = tuv.get("xml:lang") or tuv.get("{http://www.w3.org/XML/1998/namespace}lang")
                seg = tuv.find("seg")
                if lang and seg is not None and seg.text:
                    segs[lang] = seg.text
            src = segs.get(self.src_lang)
            tgt = segs.get(self.tgt_lang)
            if not src or not tgt:
                continue  # وحدة ناقصة — تُتجاهل لا تُختلَق
            tu = self.add(src, tgt, meta=meta_extra or None)
            tu.usage_count += usage
            count += 1
        logger.info("استُوردت %d وحدة من %s", count, path)
        return count


def new_id() -> str:
    """معرّف فريد لوحدات تحتاج تتبعًا خارجيًا (اختياري)."""
    return uuid.uuid4().hex
