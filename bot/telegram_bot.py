from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
import asyncio

from config import TELEGRAM_TOKEN, ADMIN_TG_ID
from graph.builder import graph
from RAG.chroma_store import get_collection, query_collection
from admin.admin_agent import run_admin_agent
from langsmith import traceable

from openai import OpenAI
from langsmith import wrappers

openai_client = wrappers.wrap_openai(OpenAI())

chroma_collection = get_collection()


def get_keyboard(telegram_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("📋 Забронировать / Перенести / Отменить")],
        [KeyboardButton("❓ Задать вопрос")],
    ]
    if telegram_id == ADMIN_TG_ID:
        buttons.append([KeyboardButton("🔧 Админка")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


@traceable(name="rag_answer")
def rag_answer(question: str) -> str:
    print(">>> rag_answer вызвана, вопрос:", question)
    docs = query_collection(chroma_collection, question, n_results=3)
    context = "\n\n".join(docs)

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1000,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты помощник ресторана «У Тимура». "
                    "Отвечай только на основе информации ниже. "
                    "Если в информации есть таблицы — читай их внимательно и используй данные из них. "
                    "Если ответа нет — скажи 'Уточните по номеру телефона 22-03-05'.\n\n"
                    f"Информация:\n{context}"
                )
            },
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content


async def start(update, context):
    context.user_data["mode"] = None
    telegram_id = update.effective_user.id
    await update.message.reply_text(
        "Добро пожаловать в ресторан «У Тимура»! 🍽️\n"
        "Я помогу вам забронировать столик или ответить на вопросы.\n"
        "Выберите действие:",
        reply_markup=get_keyboard(telegram_id)
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import time
    user_text = update.message.text
    telegram_id = update.effective_user.id
    keyboard = get_keyboard(telegram_id)

    # ── сброс режима по кнопкам ──────────────────────────────
    if user_text in ["📋 Забронировать / Перенести / Отменить", "❓ Задать вопрос", "🔧 Админка"]:
        context.user_data["mode"] = None

    # ── Админка ──────────────────────────────────────────────
    if user_text == "🔧 Админка" and telegram_id == ADMIN_TG_ID:
        context.user_data["mode"] = "admin"
        context.user_data["admin_history"] = []
        await update.message.reply_text("Режим админки 🔧\nЧто сделать?", reply_markup=keyboard)
        return

    if context.user_data.get("mode") == "admin" and telegram_id == ADMIN_TG_ID:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        history = context.user_data.get("admin_history", [])
        loop = asyncio.get_running_loop()
        reply, new_history = await loop.run_in_executor(None, run_admin_agent, user_text, history)
        context.user_data["admin_history"] = new_history
        await update.message.reply_text(reply or "Готово ✅", reply_markup=keyboard)
        return

    # ── Обычные режимы ────────────────────────────────────────
    if user_text == "❓ Задать вопрос":
        context.user_data["mode"] = "rag"
        context.user_data["thread_id"] = f"{telegram_id}_{int(time.time())}"
        await update.message.reply_text("Задайте ваш вопрос о ресторане 😊", reply_markup=keyboard)
        return

    if user_text == "📋 Забронировать / Перенести / Отменить":
        context.user_data["mode"] = "booking"
        context.user_data["thread_id"] = f"{telegram_id}_{int(time.time())}"
        await update.message.reply_text(
            "Напишите что хотите сделать, например:\n«Хочу стол на завтра в 8 вечера»",
            reply_markup=keyboard
        )
        return

    if context.user_data.get("mode") == "rag":
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, rag_answer, user_text)
            await update.message.reply_text(response, reply_markup=keyboard)
        except Exception as e:
            print(">>> ОШИБКА в RAG:", e)
            await update.message.reply_text("Произошла ошибка, попробуйте ещё раз.", reply_markup=keyboard)
        return

    # ── Граф бронирования ─────────────────────────────────────
    thread_id = context.user_data.get("thread_id", str(telegram_id))
    config = {"configurable": {"thread_id": thread_id}}

    saved = graph.get_state(config)
    is_new = not saved.values

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    if is_new:
        result = graph.invoke({
            "messages": [{"role": "user", "content": user_text}],
            "raw_input": user_text,
            "intent": None,
            "booking_details": None,
            "should_continue": False,
            "cancel_flow": False,
            "available_tables": None,
            "extraction_stage": 1,
            "modify_step": None,
            "user_bookings": None,
            "selected_booking": None,
            "new_datetime": None,
            "new_guest_count": None,
            "telegram_id": telegram_id,
            "cancel_step": None,
            "cancel_booking_id": None
        }, config=config)
    else:
        result = graph.invoke({
            "messages": [{"role": "user", "content": user_text}],
            "raw_input": user_text,
            "telegram_id": telegram_id,
        }, config=config)

    if result.get("cancel_flow"):
        context.user_data["thread_id"] = f"{telegram_id}_{int(time.time())}"
        context.user_data["mode"] = None
        await update.message.reply_text(
            (result.get("response_text") or "Оформление отменено.").strip(),
            reply_markup=keyboard
        )
        return

    if result.get("should_continue") and result.get("response_text", "").startswith("Бронь перенесена"):
        context.user_data["thread_id"] = f"{telegram_id}_{int(time.time())}"
        context.user_data["mode"] = None
        await update.message.reply_text(result["response_text"], reply_markup=keyboard)
        return

    if result.get("should_continue") and result.get("response_text", "").startswith("Бронь #"):
        context.user_data["thread_id"] = f"{telegram_id}_{int(time.time())}"
        context.user_data["mode"] = None
        await update.message.reply_text(result["response_text"], reply_markup=keyboard)
        return

    if result.get("should_continue") and result.get("response_text", "").startswith("Бронь подтверждена"):
        context.user_data["thread_id"] = f"{telegram_id}_{int(time.time())}"
        context.user_data["mode"] = None
        await update.message.reply_text(result["response_text"], reply_markup=keyboard)
        return

    response = (result.get("response_text") or "").strip() or "Не понял, уточните запрос."
    await update.message.reply_text(response, reply_markup=keyboard)


def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .get_updates_connect_timeout(30)
        .get_updates_read_timeout(30)
        .get_updates_write_timeout(30)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен...")
    app.run_polling()