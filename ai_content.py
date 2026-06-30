"""
ai_content.py — Истифодаи Groq API барои сохтани мундариҷаи дарсҳо ва тестҳо

Барои ҳар дарс, мо аз AI хоҳиш мекунем, ки мундариҷаро ҳар бор ба тарзи
гуногун (диалог, луғат, мисолҳо, эмоҷӣ ҳамчун "акс") пешниҳод кунад, то
дарс хӣ ҷонкунанда набошад.
"""

import json
import re
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL, LESSONS_PER_MODULE

client = Groq(api_key=GROQ_API_KEY)

# Услубҳои гуногуни пешниҳоди дарс — ҳар дафъа якеро интихоб мекунем
LESSON_STYLES = [
    "бо диалоги хурди ҳаётӣ дар байни ду нафар",
    "бо рӯйхати луғати нав ва эмоҷӣ ба ҳар калима (ба ҳайси расм)",
    "бо як ҳикояи кӯтоҳи шавқовар ва саволи дарк",
    "бо ҷадвали муқоисавӣ (масалан феъл дар замонҳои гуногун)",
    "бо бозии хурди 'ҳолатро тарҷума кун'",
    "бо мисолҳои ҷумлаҳои рӯзмарра ва шарҳи грамматика ба забони оддӣ",
]


def generate_lesson(language: str, module_number: int, lesson_in_module: int) -> str:
    """Як дарси нав месозад (матн, барои фиристодан ба Telegram)."""
    overall_lesson_num = (module_number - 1) * LESSONS_PER_MODULE + lesson_in_module
    style = LESSON_STYLES[overall_lesson_num % len(LESSON_STYLES)]

    prompt = f"""Ту як устоди хуш ва шавқовари забони {language} ҳастӣ.
Барои донишҷӯи тоҷикзабон дарси №{overall_lesson_num} (модули {module_number},
дарси {lesson_in_module} аз {LESSONS_PER_MODULE}) бисоз.

Дарс {style} бошад.

Қоидаҳо:
- Ҳамаи шарҳҳо ба забони тоҷикӣ, вале калима/ҷумлаҳои забони {language}-ро бо
  тарҷумаи тоҷикӣ дар қавс биёр.
- Истифода кун аз эмоҷӣ ба ҷои расм, то дарс зинда бошад.
- Дар охир, як вазифаи хонагии хурд (1-2 ҷумла барои тарҷума ё такрор) гузор.
- Дарозии дарс: миёна, на хеле дароз (тахм. 150-250 калима).
- Сатри аввал бояд унвони дарс бо эмоҷӣ бошад, масалан: "📘 Дарси {overall_lesson_num}: ..."
"""

    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=900,
    )
    return resp.choices[0].message.content.strip()


def generate_quiz(language: str, module_number: int) -> list:
    """
    Тест барои модул месозад.
    Бармегардонад: рӯйхати лугатҳо [{question, options: [...], correct_index}]
    """
    prompt = f"""Барои донишҷӯе ки забони {language}-ро (модули {module_number}, яъне
7 дарси охир) омӯхтааст, 5 саволи тести интихобӣ (4 вариант ҳар яке) бисоз.
Саволҳо бояд донишҳои ҳамин модулро санҷанд.

ФАҚАТ дар формати JSON ҷавоб деҳ, бе ҳеҷ матни иловагӣ, бе markdown, чунин:
[
  {{"question": "матни савол (бо тоҷикӣ, бо мисоли забони {language})",
    "options": ["вариант1", "вариант2", "вариант3", "вариант4"],
    "correct_index": 0}},
  ...
]
"""

    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1200,
    )
    raw = resp.choices[0].message.content.strip()
    # Тоза кардани backticks агар AI бо хато ```json гузорад
    raw = re.sub(r"^```json|```$", "", raw, flags=re.MULTILINE).strip()

    try:
        questions = json.loads(raw)
        return questions
    except json.JSONDecodeError:
        # Ҳолати эҳтиётӣ — агар AI формати дурустро надод
        return [{
            "question": f"({language}) Ин модулро такрор кардан лозим аст (хатои AI).",
            "options": ["Бале", "Не", "—", "—"],
            "correct_index": 0,
        }]