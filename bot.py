"""
bot.py — Боти асосии омӯзиши забон

Сценарий:
1. Корбар /start мезанад -> дархост ба админ фиристода мешавад
2. Админ "Қабул" / "Рад" мезанад
3. Агар қабул -> корбар забонро интихоб мекунад
4. Бот 7 дарси аввалро (бо AI сохта) яке аз сонгӣ мефиристад
5. Пас аз 7 дарс -> тест (5 савол)
6. Натиҷаи тест ба админ фиристода мешавад -> админ "Идома" / "Такрор"
7. Агар "Идома" -> 7 дарси навбатӣ оғоз мешавад, ва ҳамин тавр то 6 моҳ
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
)

import database as db
import ai_content
from config import BOT_TOKEN, ADMIN_ID, LANGUAGES, LESSONS_PER_MODULE

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Сессияҳои тести фаъол дар хотира: {user_id: {questions, current, score, module}}
quiz_sessions = {}


# ---------- 1. /start ва дархости тасдиқ ----------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username or "", user.full_name)
    row = db.get_user(user.id)

    if row["status"] == "approved":
        await send_main_menu(update.effective_chat.id, context, user.id)
        return

    if row["status"] == "pending":
        await update.message.reply_text(
            "✅ Дархости шумо ба админ фиристода шуд.\nЛутфан интизор шавед..."
        )

    # ба админ хабар фиристодан (фақат боре, вале барои соддагӣ ҳар /start мефиристем)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Қабул", callback_data=f"approve_{user.id}"),
        InlineKeyboardButton("❌ Рад", callback_data=f"reject_{user.id}"),
    ]])
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(f"🔔 Корбари нав:\n"
              f"Ном: {user.full_name}\n"
              f"Username: @{user.username}\n"
              f"ID: {user.id}\n\n"
              f"Иҳозат диҳед, ки забон омӯзад?"),
        reply_markup=keyboard,
    )


# ---------- 2. Қарори админ: Қабул / Рад ----------

async def admin_decision_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, user_id = query.data.split("_")
    user_id = int(user_id)

    if action == "approve":
        db.set_status(user_id, "approved")
        await query.edit_message_text(f"✅ Корбар {user_id} қабул шуд.")
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(lang, callback_data=f"lang_{lang}")] for lang in LANGUAGES]
        )
        await context.bot.send_message(
            chat_id=user_id,
            text="🎉 Дархости шумо қабул шуд!\n\nКадом забонро омӯхтан мехоҳед?",
            reply_markup=keyboard,
        )
    else:
        db.set_status(user_id, "rejected")
        await query.edit_message_text(f"❌ Корбар {user_id} рад шуд.")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Мутаасифона, дархости шумо рад карда шуд.",
        )


# ---------- 3. Интихоби забон ----------

async def language_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    language = query.data.replace("lang_", "")
    user_id = query.from_user.id

    db.set_language(user_id, language)
    await query.edit_message_text(f"📚 Забони интихобшуда: {language}\n\nДарси якум омода мешавад...")

    await send_next_lesson(user_id, context)


# ---------- 4. Фиристодани дарс ----------

async def send_next_lesson(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    row = db.get_user(user_id)

    if row["waiting_admin_review"]:
        await context.bot.send_message(
            user_id, "⏳ Натиҷаи тести шумо назди админ аст. Интизор шавед..."
        )
        return

    if row["lessons_done_in_module"] >= LESSONS_PER_MODULE:
        await start_quiz(user_id, context)
        return

    lesson_text = ai_content.generate_lesson(
        language=row["language"],
        module_number=row["current_module"],
        lesson_in_module=row["lessons_done_in_module"] + 1,
    )
    db.increment_lesson(user_id)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("➡️ Давоми дарси навбатӣ", callback_data="next_lesson")
    ]])
    await context.bot.send_message(user_id, lesson_text, reply_markup=keyboard)


async def next_lesson_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await send_next_lesson(query.from_user.id, context)


# ---------- 5. Тест пас аз 7 дарс ----------

async def start_quiz(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    row = db.get_user(user_id)
    questions = ai_content.generate_quiz(row["language"], row["current_module"])
    quiz_sessions[user_id] = {"questions": questions, "current": 0, "score": 0,
                               "module": row["current_module"]}
    await context.bot.send_message(
        user_id, f"📝 Вакти тест расид! ({len(questions)} савол)\nМуваффақ бошед!"
    )
    await send_quiz_question(user_id, context)


async def send_quiz_question(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    session = quiz_sessions[user_id]
    idx = session["current"]
    q = session["questions"][idx]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(opt, callback_data=f"quiz_{i}")]
        for i, opt in enumerate(q["options"])
    ])
    await context.bot.send_message(
        user_id, f"❓ Савол {idx + 1}/{len(session['questions'])}:\n{q['question']}",
        reply_markup=keyboard,
    )


async def quiz_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chosen = int(query.data.replace("quiz_", ""))

    session = quiz_sessions.get(user_id)
    if not session:
        return

    idx = session["current"]
    q = session["questions"][idx]
    correct = (chosen == q["correct_index"])
    if correct:
        session["score"] += 1
        await query.edit_message_text(f"✅ Дуруст!\n{q['question']}")
    else:
        correct_text = q["options"][q["correct_index"]]
        await query.edit_message_text(
            f"❌ Нодуруст.\n{q['question']}\nҶавоби дуруст: {correct_text}"
        )

    session["current"] += 1
    if session["current"] < len(session["questions"]):
        await send_quiz_question(user_id, context)
    else:
        await finish_quiz(user_id, context)


async def finish_quiz(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    session = quiz_sessions.pop(user_id)
    score, total, module = session["score"], len(session["questions"]), session["module"]
    db.save_test_result(user_id, score, total)
    row = db.get_user(user_id)

    await context.bot.send_message(
        user_id, f"🏁 Тест анҷом ёфт! Натиҷа: {score}/{total}\n"
                 f"Натиҷаи шумо ба админ фиристода шуд. Интизор шавед..."
    )

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("➡️ Идома (7 дарси нав)", callback_data=f"admincont_{user_id}_yes"),
        InlineKeyboardButton("🔁 Такрори модул", callback_data=f"admincont_{user_id}_no"),
    ]])
    await context.bot.send_message(
        ADMIN_ID,
        text=(f"📊 Натиҷаи тест:\n"
              f"Корбар: {row['full_name']} (@{row['username']}) ID:{user_id}\n"
              f"Забон: {row['language']}\n"
              f"Модул: {module}\n"
              f"Натиҷа: {score}/{total}\n\n"
              f"Идома диҳем ё модулро такрор кунем?"),
        reply_markup=keyboard,
    )


# ---------- 6. Қарори админ пас аз тест ----------

async def admin_continue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, user_id, decision = query.data.split("_")
    user_id = int(user_id)

    if decision == "yes":
        db.advance_to_next_module(user_id)
        await query.edit_message_text("✅ Тасдиқ шуд — модули нав оғоз мешавад.")
        await context.bot.send_message(user_id, "🎉 Аъло! Ба модули навбатӣ мегузарем.")
    else:
        db.repeat_current_module(user_id)
        await query.edit_message_text("🔁 Модул такрор карда мешавад.")
        await context.bot.send_message(
            user_id, "📌 Лозим аст ин модулро боз як бор такрор кунем."
        )

    await send_next_lesson(user_id, context)


# ---------- 7. Менюи асосӣ барои корбарони аллакай қабулшуда ----------

async def send_main_menu(chat_id, context, user_id):
    row = db.get_user(user_id)
    if not row["language"]:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(lang, callback_data=f"lang_{lang}")] for lang in LANGUAGES]
        )
        await context.bot.send_message(chat_id, "Забонеро интихоб кунед:", reply_markup=keyboard)
    else:
        await send_next_lesson(user_id, context)


# ---------- Роҳандозӣ ----------

def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(admin_decision_callback, pattern=r"^(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(language_choice_callback, pattern=r"^lang_"))
    app.add_handler(CallbackQueryHandler(next_lesson_callback, pattern=r"^next_lesson$"))
    app.add_handler(CallbackQueryHandler(quiz_answer_callback, pattern=r"^quiz_"))
    app.add_handler(CallbackQueryHandler(admin_continue_callback, pattern=r"^admincont_"))

    log.info("Бот оғоз шуд...")
    app.run_polling()


if __name__ == "__main__":
    main()