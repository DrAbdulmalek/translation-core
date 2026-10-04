"""حزمة جودة الترجمة — نقلت من marathon src/quality.

[PORT DEVIATION — documented] marathon كانت تستخدم namespace package
(بلا __init__.py). هنا __init__.py صريح يصدّر الواجهة العامة، وهو
الممارسة القياسية لحزمة قابلة للتثبيت عبر pip.
"""
from .metrics import QualityEvaluator, QualityScore

__all__ = ["QualityEvaluator", "QualityScore"]
