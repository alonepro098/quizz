import os
import PyPDF2
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")  # Render me env variable set karna

# ===== GLOBAL STORAGE =====
user_state = {}        # chat_id -> state
pdf_text_store = {}   # chat_id -> pdf text
mcq_store = {}        # chat_id -> list of mcqs
quiz_index = {}       # chat_id -> current question index
scores = {}           # user_name -> score
current_answer = {}   # chat_id -> correct answer


# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi!\n\n"
        "📘 Quiz banane ke liye /upload_pdf use karo"
    )


# ===== UPLOAD PDF COMMAND =====
async def upload_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_state[chat_id] = "WAITING_PDF"

    await update.message.reply_text(
        "📄 PDF upload karo\n"
        "⚠️ Sirf wahi questions aayenge jo PDF me honge"
    )


# ===== HANDLE PDF =====
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if user_state.get(chat_id) != "WAITING_PDF":
        return

    file = await update.message.document.get_file()
    await file.download_to_drive("input.pdf")

    reader = PyPDF2.PdfReader("input.pdf")
    text = ""

    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text() + "\n"

    pdf_text_store[chat_id] = text
    mcq_store[chat_id] = generate_mcqs_from_pdf(text)
    quiz_index[chat_id] = 0

    user_state[chat_id] = "QUIZ_READY"

    await update.message.reply_text(
        "✅ QUIZ IS READY\n"
        "▶️ PLEASE TAP /start_quiz"
    )


# ===== MCQ GENERATOR (NO FALTU) =====
def generate_mcqs_from_pdf(text):
    """
    Simple rule-based MCQ generator
    Sirf PDF ke text se
    No repeat
    """

    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 40]
    used = set()
    mcqs = []

    for line in lines[:10]:  # 10 questions
        if line in used:
            continue

        used.add(line)

        mcqs.append({
            "question": f"Is sentence ka sahi statement kaunsa hai?",
            "options": [
                line,
                "Ye PDF me nahi likha",
                "Ye galat statement hai",
                "Koi sambandh nahi"
            ],
            "answer": line
        })

    return mcqs


# ===== START QUIZ =====
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if user_state.get(chat_id) != "QUIZ_READY":
        await update.message.reply_text("❌ Pehle /upload_pdf karo")
        return

    await ask_next_question(update, context)


# ===== ASK QUESTION =====
async def ask_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    index = quiz_index.get(chat_id, 0)
    mcqs = mcq_store.get(chat_id, [])

    if index >= len(mcqs):
        await show_result(update, context)
        return

    q = mcqs[index]
    current_answer[chat_id] = q["answer"]

    options_text = ""
    for opt in q["options"]:
        options_text += f"• {opt}\n"

    await update.message.reply_text(
        f"❓ Question {index + 1}\n\n"
        f"{q['question']}\n\n"
        f"{options_text}"
    )


# ===== ANSWER HANDLER =====
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.message.from_user.first_name
    text = update.message.text

    if chat_id not in current_answer:
        return

    if text == current_answer[chat_id]:
        scores[user] = scores.get(user, 0) + 1

    quiz_index[chat_id] += 1
    await ask_next_question(update, context)


# ===== RESULT =====
async def show_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await update.message.reply_text("❌ Koi answer nahi diya")
        return

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    msg = "🏆 TOP 3 WINNERS 🏆\n\n"
    for i, (name, score) in enumerate(sorted_scores[:3], 1):
        msg += f"{i}. {name} — {score} marks\n"

    await update.message.reply_text(msg)


# ===== MAIN =====
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("upload_pdf", upload_pdf))
    app.add_handler(CommandHandler("start_quiz", start_quiz))

    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))

    app.run_polling()


if __name__ == "__main__":
    main()
