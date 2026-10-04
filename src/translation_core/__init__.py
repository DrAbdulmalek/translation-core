"""translation_core — المحرك المركزي للترجمة (single source of truth).

المكونات:
- languages:  سجل اللغات (10 لغات RTL/LTR) — مصدر حقيقة واحد
- translator: محركات الترجمة الموحدة (google/deepl/hf/finetuned + MultiLang)
- quality:    مقاييس جودة الترجمة (BLEU/chrF/METEOR/COMET/BERTScore) + تقييم تلقائي
- ab_testing: تجارب A/B بين المحركات مع دلالة إحصائية
- tm:         ذاكرة الترجمة (Translation Memory) + TMX 1.4b import/export
- glossary:   المسرد — فرض المصطلحات الموحدة

السياسة: الثقة لا تُختلق — كل محرك يعيد TranslationResult؛ ما لا يُعرف
يُحذَّر منه صراحةً ولا يُمرَّر بصمت.
"""
from .languages import LanguageRegistry, get_registry
from .translator import (
    BaseTranslator,
    DeepLTranslator,
    FinetunedTranslator,
    GoogleTranslator,
    HFTranslator,
    MultiLangTranslator,
    TranslationResult,
    Translator,
)
from .quality import QualityEvaluator, QualityScore
from .tm import TranslationMemory, TranslationUnit
from .glossary import Glossary, GlossaryViolation

__version__ = "0.1.0"

__all__ = [
    "LanguageRegistry", "get_registry",
    "BaseTranslator", "GoogleTranslator", "DeepLTranslator", "HFTranslator",
    "FinetunedTranslator", "Translator", "MultiLangTranslator",
    "TranslationResult",
    "QualityEvaluator", "QualityScore",
    "TranslationMemory", "TranslationUnit",
    "Glossary", "GlossaryViolation",
    "__version__",
]
