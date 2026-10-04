"""يضبط قواعد بيانات الاختبار **قبل** أي استيراد للوحدات ذات الأثر الجانبي.

auto_quality.py وab_testing.py ينشئان قاعدة SQLite لحظة الاستيراد
(وفاءً للنسخة الأصلية) — نوجّههما إلى مجلد مؤقت حتى لا يلوثا المستودع.
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="translation-core-tests-")
os.environ.setdefault("QUALITY_DB", os.path.join(_TMP, "quality.db"))
os.environ.setdefault("AB_DB", os.path.join(_TMP, "ab_testing.db"))
