"""المسرد (Glossary) — فرض المصطلحات الموحدة على الترجمات.

الفكرة: الترجمة الحرة بلا مصطلح موحد تفتت هوية المشروع لغويًا
("مفتاح/زر"؟ "ذاكرة/مِيمُوري"؟). المسرد يربط كل مصطلح مصدر بترجمته
المعتمدة وبأشكال بديلة **ممنوعة** (alt) تُكتشف في الترجمة وتُبلَّغ
كخرق — لا يُصلَّح تلقائيًا (القرار للمراجع البشري، وفاءً لسياسة
"لا تختلق ترجمة بصمت").

صيغة الملف (YAML أو JSON):
    terms:
      "dataset":
        target: "مجموعة البيانات"
        alt: ["داتاسِت", "قاعدة البيانات"]
        notes: "ممنوع داتاسِت"
      "pipeline":
        target: "خط المعالجة"

أو مسطّح (اختصار):
    "dataset": "مجموعة البيانات"

ثم:
    g = Glossary(path="glossary.yaml")
    g.detect("The dataset pipeline is fast.")   # -> مصطلحات موجودة في المصدر
    g.validate(src, translation)                # -> خرائق مصطلحات
"""
from __future__ import annotations

import json
import logging
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GlossaryViolation:
    """خرق مسرد واحد: مصطلح معتمد لم يُحترم في الترجمة."""

    term: str               # المصطلح المصدر
    expected: str           # الترجمة المعتمدة
    found_alt: Optional[str]  # الشكل البديل الممنوع الذي ظهر (إن وُجد)
    reason: str             # شرح بشري

    def asdict(self) -> Dict:
        return {
            "term": self.term, "expected": self.expected,
            "found_alt": self.found_alt, "reason": self.reason,
        }


@dataclass
class GlossaryEntry:
    target: str
    alt: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    case_sensitive: bool = False


def _norm(text: str) -> str:
    """NFC + طي مسافات — نفس تطبيع tm.py (اتساق الحزمة)."""
    import re
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text or "")).strip()


class Glossary:
    """مسرد مصطلحات ثنائي الاتجاه: كشف في المصدر، فرض في الهدف."""

    def __init__(self, path: Optional[str] = None,
                 entries: Optional[Dict] = None):
        self._terms: Dict[str, GlossaryEntry] = {}
        if entries:
            self._load_entries(entries)
        if path:
            self.load(path)

    # ------------------------------------------------------------------
    # التحميل
    # ------------------------------------------------------------------
    def _load_entries(self, raw: Dict):
        terms = raw.get("terms", raw) if isinstance(raw, dict) else None
        if not isinstance(terms, dict):
            raise ValueError("صيغة المسرد: {terms: {...}} أو {مصطلح: ترجمة}")
        for src, spec in terms.items():
            if isinstance(spec, str):
                self._terms[str(src)] = GlossaryEntry(target=spec)
            elif isinstance(spec, dict):
                if "target" not in spec:
                    raise ValueError(f"مصطلح بلا ترجمة معتمدة: {src}")
                alt = spec.get("alt") or []
                if isinstance(alt, str):
                    alt = [alt]
                self._terms[str(src)] = GlossaryEntry(
                    target=str(spec["target"]),
                    alt=[str(a) for a in alt],
                    notes=spec.get("notes"),
                    case_sensitive=bool(spec.get("case_sensitive", False)),
                )
            else:
                raise ValueError(f"قيمة مصطلح غير مفهومة لـ {src}")

    def load(self, path: str):
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        if p.suffix.lower() in (".yaml", ".yml"):
            import yaml
            raw = yaml.safe_load(text) or {}
        elif p.suffix.lower() == ".json":
            raw = json.loads(text)
        else:
            raise ValueError(f"امتداد غير مدعوم للمسرد: {p.suffix}")
        self._load_entries(raw)
        return self

    # ------------------------------------------------------------------
    # العمليات
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._terms)

    def get(self, term: str) -> Optional[GlossaryEntry]:
        return self._terms.get(term)

    def terms(self) -> List[str]:
        return list(self._terms.keys())

    def detect(self, source_text: str) -> List[str]:
        """المصطلحات الموجودة في النص المصدر (مطابقة كلمة واعية بالحدود)."""
        import re
        text = _norm(source_text)
        found = []
        for term in self._terms:
            flags = 0 if self._terms[term].case_sensitive else re.IGNORECASE
            if re.search(rf"\b{re.escape(_norm(term))}\b", text, flags):
                found.append(term)
        return found

    def suggest(self, source_text: str) -> List[Dict]:
        """اقتراح ترجمات المصطلحات المكتشفة — للمترجم البشري أو البرمجي."""
        return [
            {"term": t, "target": self._terms[t].target}
            for t in self.detect(source_text)
        ]

    def validate(self, source_text: str, translation: str
                 ) -> List[GlossaryViolation]:
        """يكتشف خرائق المسرد في ترجمة معينة.

        خرق يُعلَن فقط عند:
        1. المصطلح موجود في المصدر، **و**
        2. الترجمة المعتمدة غائبة عن الهدف، **و**
        3. (أ) ظهر شكل بديل ممنوع — خرق صريح، أو
           (ب) لا بديل ظهر لكن المعتمد غائب — تنبيه "غير مطبَّق".

        [سياسة] لا استبدال تلقائي: المراجع البشري يقرر — قد يكون
        الغياب مقصودًا (جملة اسمية، اقتباس...). الهدف رفع الوعي لا
        التحرير الصامت.
        """
        violations: List[GlossaryViolation] = []
        tgt = _norm(translation)
        for term in self.detect(source_text):
            entry = self._terms[term]
            expected_present = self._contains(tgt, entry.target,
                                              entry.case_sensitive)
            if expected_present:
                continue
            alt_found = None
            for a in entry.alt:
                if self._contains(tgt, _norm(a), entry.case_sensitive):
                    alt_found = a
                    break
            if alt_found is not None:
                violations.append(GlossaryViolation(
                    term=term, expected=entry.target, found_alt=alt_found,
                    reason=f"شكل ممنوع «{alt_found}» بدل المعتمد «{entry.target}»",
                ))
            else:
                violations.append(GlossaryViolation(
                    term=term, expected=entry.target, found_alt=None,
                    reason=f"الترجمة المعتمدة «{entry.target}» غائبة عن الهدف",
                ))
        return violations

    @staticmethod
    def _contains(haystack: str, needle: str, case_sensitive: bool) -> bool:
        import re
        if not needle:
            return False
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.search(rf"\b{re.escape(needle)}\b", haystack, flags) is not None

    def asdict(self) -> Dict:
        return {
            term: {
                "target": e.target,
                "alt": list(e.alt),
                "notes": e.notes,
            } for term, e in self._terms.items()
        }
