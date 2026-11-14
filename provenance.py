#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
provenance.py — عقد «إثبات الأصل» (الفكرة 3 من خطة التطوير — فورية).
لكل جملة تُنتج: بصمة تشفيرية رياضية hash(المصدر + OCR + الترجمة + الميثاق) بحيث أي
طرف يستخدم المخرجات يستطيع التحقق لاحقاً أنها خرجت من المسار الصحيح — بلا ثقة
بمحتوى الملف وحده. مرتبط بميثاق الـ18 قاعدة (Visual Evidence Charter v18 في
ocr-core — docs/charter_v2.yaml).

الاستخدام المكتبي (3 أسطر داخل forwarder/translation-core):
    from provenance import sign_translation
    prov = sign_translation(source_text, ocr_text, translation_text, actor="forwarder")
    # prov["provenance"] يُطبع مع الإنتاج أو يُخزن بجانبه (.prov.json)

سطر الأوامر:
    python provenance.py sign --source s.txt --ocr o.txt --translation t.txt --out rec
    python provenance.py verify rec.prov.json [--source s.txt --ocr o.txt --translation t.txt]
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

PROV_SCHEMA = "prov-med-ar/1.0"
RULESET_ID = "visual-evidence-charter/v18"   # ميثاق الـ18 قاعدة — ocr-core/docs/charter_v2.yaml
TOOL_VERSION = "provenance/1.0"


def sha256(text: str) -> str:
    """بصمة مكون نصي — UTF-8 ثابتة، بلا تطبيع: ما نص المحتوى هو ما يُبصم."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(obj) -> str:
    """JSON قياسي قابل لإعادة الإنتاج عبر اللغات والمكتبات."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def make_record(source_text: str, ocr_text: str, translation_text: str,
                actor: str = "", meta: dict = None) -> dict:
    """بناء سجل إثبات كامل: بصمات المكونات + بصمة الإثبات الجامعة."""
    comp = {
        "source_sha256": sha256(source_text or ""),
        "ocr_sha256": sha256(ocr_text or ""),
        "translation_sha256": sha256(translation_text or ""),
    }
    provenance = sha256(_canonical([PROV_SCHEMA, RULESET_ID,
                                    comp["source_sha256"], comp["ocr_sha256"],
                                    comp["translation_sha256"]]))
    return {
        "schema": PROV_SCHEMA,
        "ruleset": RULESET_ID,
        "components": comp,
        "provenance": provenance,
        "actor": actor,
        "tool_version": TOOL_VERSION,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "meta": meta or {},
    }


def verify(record: dict, texts: dict = None) -> dict:
    """التحقق: (1) بصمة الإثبات تُعاد حسابياً من مكوناتها، (2) إن مُرّت النصوص
    تُبصم المكونات أيضاً — أي فشل يعني عبثاً أو إنتاجاً من خارج المسار."""
    comp = record.get("components", {})
    recomputed = sha256(_canonical([record.get("schema"), record.get("ruleset"),
                                    comp.get("source_sha256"), comp.get("ocr_sha256"),
                                    comp.get("translation_sha256")]))
    ok = recomputed == record.get("provenance")
    report = {"valid": ok, "provenance_recomputed": recomputed, "component_texts_checked": False}
    if ok and texts:
        pairs = {"source_sha256": "source_text", "ocr_sha256": "ocr_text",
                 "translation_sha256": "translation_text"}
        for key, field in pairs.items():
            if field in texts and comp.get(key):
                if sha256(texts[field] or "") != comp[key]:
                    report["valid"] = False
                    report["mismatched_component"] = key
        report["component_texts_checked"] = True
    return report


def sign_translation(source_text: str, ocr_text: str, translation_text: str,
                     actor: str = "", sidecar_path: Path = None, meta: dict = None) -> dict:
    """نقطة الربط الرسمية: سجل + كتابة ملف بجانب الناتج (اختياري)."""
    rec = make_record(source_text, ocr_text, translation_text, actor=actor, meta=meta)
    if sidecar_path is not None:
        sidecar_path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def _read_or_empty(p: str) -> str:
    return Path(p).read_text(encoding="utf-8") if p and Path(p).exists() else (p or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sign", help="بناء سجل إثبات من ثلاثة نصوص")
    s.add_argument("--source", required=True, help="مسار ملف أو النص نفسه")
    s.add_argument("--ocr", required=True)
    s.add_argument("--translation", required=True)
    s.add_argument("--actor", default="cli")
    s.add_argument("--out", default="", help="مسار حفظ السجل (اختياري)")

    v = sub.add_parser("verify", help="التحقق من سجل — وربطه بالنصوص إن مُرّت")
    v.add_argument("record", help="ملف السجل .prov.json")
    v.add_argument("--source", default="")
    v.add_argument("--ocr", default="")
    v.add_argument("--translation", default="")

    a = ap.parse_args()
    if a.cmd == "sign":
        rec = make_record(_read_or_empty(a.source), _read_or_empty(a.ocr),
                          _read_or_empty(a.translation), actor=a.actor)
        if a.out:
            Path(a.out).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"✓ السجل مكتوب: {a.out}")
        print(json.dumps(rec, ensure_ascii=False, indent=1))
        return 0
    rec = json.loads(Path(a.record).read_text(encoding="utf-8"))
    texts = {}
    if a.source:
        texts["source_text"] = _read_or_empty(a.source)
    if a.ocr:
        texts["ocr_text"] = _read_or_empty(a.ocr)
    if a.translation:
        texts["translation_text"] = _read_or_empty(a.translation)
    report = verify(rec, texts or None)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
