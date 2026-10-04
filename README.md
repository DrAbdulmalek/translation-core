# translation-core

المحرك المركزي للترجمة — **single source of truth** لكل ما يتعلق بالترجمة في منظومة الماراثون.

> الشعار المعماري: نواة مركزية + مستهلكون رفيعون (نمط `ocr-core` نفسه).
> أي تعديل على سجل اللغات أو المحركات أو المقاييس يحدث **هنا**، ثم يُرفع
> الإصدار، والمستهلكون (marathon، مكونات مستقبلية) تثبّت إصدارًا محددًا.

## المكونات

| الوحدة | الدور |
|---|---|
| `translation_core.languages` | سجل اللغات (10 لغات RTL/LTR) — `config/languages.yaml` بيانات حزمة، مستقل عن CWD، تجاوز عبر `LANGUAGES_FILE` |
| `translation_core.translator` | محركات موحدة: google / deepl / hf (اختيار نموذج حسب الزوج) / finetuned + `MultiLangTranslator` |
| `translation_core.quality` | BLEU / chrF / METEOR / (COMET / BERTScore اختياريًا) + تقييم تلقائي SQLite + كشف تدهور |
| `translation_core.ab_testing` | تجارب A/B بين المحركات: توزيع حتمي بالهاش، Welch t-test، فائز تلقائي |
| `translation_core.tm` | ذاكرة ترجمة JSONL: مطابقة تامة/ضبابية + **TMX 1.4b** import/export |
| `translation_core.glossary` | مسرد مصطلحات: كشف في المصدر، فرض المعتمد، كشف الأشكال الممنوعة — بلا تحرير صامت |

## التثبيت

```bash
pip install git+https://github.com/DrAbdulmalek/translation-core.git@v0.1.0
# extras:
#   google | deepl | hf | quality | tm | ab | all | dev
```

الاعتماديات الثقيلة (transformers/torch/evaluate/scipy) **كسولة واختيارية** —
الحزمة الأساسية تحتاج `pyyaml` فقط، وكل محرك/مقياس يعلن حاجته وقت الاستدعاء.

## سياسة الثقة

- كل محرك يعيد `TranslationResult` — والعقد مفحوص اختباريًا لكل محرك.
- ما لا يُعرف يُحذَّر منه صراحةً ولا يُمرَّر بصمت (فشل مرئي > هراء صامت).
- المباريات في الذاكرة تحمل `score` محسوبًا فعليًا؛ لا نقاط تُختلَق.

## الترخيص

MIT — انظر [LICENSE](LICENSE).
