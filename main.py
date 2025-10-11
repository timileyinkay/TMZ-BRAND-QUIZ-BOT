"""
TMZ BRAND Quiz Bot - Final Leaderboard Only
SECURE VERSION: One-time quiz participation with Admin Panel
NANOSECOND PRECISION VERSION
"""

import os
import time
import threading
import json
from collections import defaultdict, namedtuple
from dotenv import load_dotenv
import telebot
from telebot import types
from datetime import datetime
from flask import Flask

app = Flask(__name__)

load_dotenv()

# === BOT TOKEN ===
TOKEN = os.getenv("BOT_TOKEN") or "8335451882:AAGy5lwKBby2Ue7tkktNMeLKfYYNwU8YHu4"
bot = telebot.TeleBot(TOKEN)

# === CONFIGURATION ===
CONFIG = {
    "QUESTION_TIME": 15,
    "POINTS_CORRECT": 10,
    "POINTS_FIRST_CORRECT_BONUS": 5,
    "QUESTIONS_FILE": "questions.json",
    "PARTICIPANTS_FILE": "participants.json",
    "QUIZ_COMPLETION_FILE": "quiz_completed.json",
    "ADMIN_IDS": [6011041717],  # Replace with your user ID
    "QUESTION_TRANSITION_DELAY": 2,
    "AUTO_DELETE_DELAY": 100,  # 1 minutes for most messages
    "START_MESSAGE_DELAY": 60  # ⚡ CHANGED: 1 minute for start message (was 480)
}

# === MESSAGE AUTO-DELETION SYSTEM ===
def schedule_auto_delete(chat_id, message_id, delay=None):
    """Automatically delete message after given delay"""
    if delay is None:
        delay = CONFIG["AUTO_DELETE_DELAY"]
    
    def _delete_later():
        time.sleep(delay)
        try:
            bot.delete_message(chat_id, message_id)
        except Exception as e:
            # Message might already be deleted or not accessible
            pass
    
    threading.Thread(target=_delete_later, daemon=True).start()

# === DATA STRUCTURES ===
Question = namedtuple("Question", ["q", "opts", "correct_index"])

# === QUIZ COMPLETION TRACKING ===
def load_quiz_completion():
    """Load quiz completion data"""
    try:
        if not os.path.exists(CONFIG["QUIZ_COMPLETION_FILE"]):
            # Create default completion file if it doesn't exist
            default_data = {"completed_users": [], "quiz_active": True}
            with open(CONFIG["QUIZ_COMPLETION_FILE"], 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=2, ensure_ascii=False)
            return default_data
        
        with open(CONFIG["QUIZ_COMPLETION_FILE"], 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading quiz completion: {e}")
        return {"completed_users": [], "quiz_active": True}

def save_quiz_completion(data):
    """Save quiz completion data"""
    try:
        with open(CONFIG["QUIZ_COMPLETION_FILE"], 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving quiz completion: {e}")

def has_user_completed_quiz(user_id):
    """Check if user has already completed the quiz"""
    completion_data = load_quiz_completion()
    return str(user_id) in completion_data.get("completed_users", [])

def mark_user_completed(user_id):
    """Mark user as having completed the quiz"""
    completion_data = load_quiz_completion()
    user_id_str = str(user_id)
    
    if user_id_str not in completion_data.get("completed_users", []):
        completion_data.setdefault("completed_users", []).append(user_id_str)
        save_quiz_completion(completion_data)

def is_quiz_active():
    """Check if quiz is still active"""
    completion_data = load_quiz_completion()
    return completion_data.get("quiz_active", True)

def set_quiz_active(status):
    """Set quiz active status (Admin only)"""
    completion_data = load_quiz_completion()
    completion_data["quiz_active"] = status
    save_quiz_completion(completion_data)

# === SECURE QUESTION LOADING ===
def load_questions():
    """Load questions securely"""
    try:
        if not os.path.exists(CONFIG["QUESTIONS_FILE"]):
            # Create default questions file if it doesn't exist
            default_questions = {
                "questions": [],
                "question_time": CONFIG["QUESTION_TIME"]
            }
            with open(CONFIG["QUESTIONS_FILE"], 'w', encoding='utf-8') as f:
                json.dump(default_questions, f, indent=2, ensure_ascii=False)
            return []
        
        with open(CONFIG["QUESTIONS_FILE"], 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        questions = []
        for q_data in data.get("questions", []):
            questions.append(Question(
                q=q_data["question"],
                opts=q_data["options"],
                correct_index=q_data["correct_index"]
            ))
        
        if "question_time" in data:
            CONFIG["QUESTION_TIME"] = data["question_time"]
            
        return questions
    except Exception as e:
        print(f"Error loading questions: {e}")
        return []

def save_questions(questions, question_time=None):
    """Save questions to file"""
    try:
        data = {
            "questions": [
                {
                    "question": q.q,
                    "options": q.opts,
                    "correct_index": q.correct_index
                }
                for q in questions
            ]
        }
        
        if question_time:
            data["question_time"] = question_time
            CONFIG["QUESTION_TIME"] = question_time
        
        with open(CONFIG["QUESTIONS_FILE"], 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving questions: {e}")
        return False

def is_admin(user_id):
    """Check if user is admin"""
    return user_id in CONFIG["ADMIN_IDS"]

# === PARTICIPANT MANAGEMENT ===
def load_participants():
    try:
        if not os.path.exists(CONFIG["PARTICIPANTS_FILE"]):
            # Create default participants file if it doesn't exist
            with open(CONFIG["PARTICIPANTS_FILE"], 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2, ensure_ascii=False)
            return {}
        
        with open(CONFIG["PARTICIPANTS_FILE"], 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading participants: {e}")
        return {}

def save_participants(participants_data):
    try:
        with open(CONFIG["PARTICIPANTS_FILE"], 'w', encoding='utf-8') as f:
            json.dump(participants_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving participants: {e}")

def get_participant_name(user_id):
    participants = load_participants()
    return participants.get(str(user_id), {}).get("name", f"User_{user_id}")

def save_participant_info(user_id, name, chat_id=None):
    participants = load_participants()
    user_id_str = str(user_id)
    
    if user_id_str not in participants:
        participants[user_id_str] = {
            "name": name,
            "first_seen": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),  # Clean timestamp
            "chat_ids": [],
            "total_score": 0,
            "quizzes_completed": 0,
            "accuracy": 0,
            "has_completed_current_quiz": False
        }
    
    if chat_id and chat_id not in participants[user_id_str].get("chat_ids", []):
        participants[user_id_str].setdefault("chat_ids", []).append(chat_id)
    
    participants[user_id_str]["last_seen"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")  # Clean timestamp
    participants[user_id_str]["name"] = name
    save_participants(participants)

def update_participant_stats(user_id, score, correct_answers, total_questions):
    """Update participant statistics after quiz"""
    participants = load_participants()
    user_id_str = str(user_id)
    
    if user_id_str not in participants:
        return
    
    participants[user_id_str]["has_completed_current_quiz"] = True
    participants[user_id_str]["total_score"] = participants[user_id_str].get("total_score", 0) + score
    participants[user_id_str]["quizzes_completed"] = participants[user_id_str].get("quizzes_completed", 0) + 1
    
    if total_questions > 0:
        current_accuracy = participants[user_id_str].get("accuracy", 0)
        new_accuracy = (correct_answers / total_questions) * 100
        
        if participants[user_id_str]["quizzes_completed"] > 1:
            total_quizzes = participants[user_id_str]["quizzes_completed"]
            participants[user_id_str]["accuracy"] = round(((current_accuracy * (total_quizzes - 1)) + new_accuracy) / total_quizzes, 2)  # Rounded
        else:
            participants[user_id_str]["accuracy"] = round(new_accuracy, 2)  # Rounded
    
    save_participants(participants)

# === STATE MANAGEMENT ===
class ChatQuizState:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.current_q = -1
        self.is_running = False
        self.questions = []
        self.participants = defaultdict(lambda: {
            "score": 0,
            "answers": {},
            "total_time_ns": 0,  # Nanoseconds for precise ranking
            "name": "Unknown",
            "correct_answers": 0
        })
        self.first_correct_for_question = {}
        self.question_start_time_ns = None  # Nanoseconds
        self.quiz_start_time_ns = None
        self.lock = threading.Lock()
        self.answered_users_per_question = set()
        self.question_message_id = None
        self.countdown_message_id = None
        self.countdown_thread = None
        self.stop_countdown = False
        self.question_answered = False
        self.answer_lock = threading.Lock()

chat_state = {}
chat_state_lock = threading.Lock()

def get_state(chat_id):
    if chat_id not in chat_state:
        with chat_state_lock:
            if chat_id not in chat_state:  # Double check with lock
                chat_state[chat_id] = ChatQuizState(chat_id)
    return chat_state[chat_id]

def clear_state(chat_id):
    """Enhanced state clearing with proper cleanup"""
    if chat_id in chat_state:
        with chat_state_lock:
            if chat_id in chat_state:
                state = chat_state[chat_id]
                # Stop any running countdown
                if hasattr(state, 'stop_countdown'):
                    state.stop_countdown = True
                # Stop countdown thread if running
                if state.countdown_thread and state.countdown_thread.is_alive():
                    state.countdown_thread.join(timeout=1)
                del chat_state[chat_id]
                print(f"✅ Cleared state for chat {chat_id}")

def clear_all_states():
    """Clear all quiz states (Admin only)"""
    with chat_state_lock:
        chat_ids = list(chat_state.keys())
        for chat_id in chat_ids:
            state = chat_state[chat_id]
            if hasattr(state, 'stop_countdown'):
                state.stop_countdown = True
            if state.countdown_thread and state.countdown_thread.is_alive():
                state.countdown_thread.join(timeout=1)
            del chat_state[chat_id]
        print(f"✅ Cleared all {len(chat_ids)} chat states")

# === COUNTDOWN TIMER ===
def start_countdown(chat_id, duration):
    """Start a countdown timer that shows seconds remaining"""
    state = get_state(chat_id)
    state.stop_countdown = False
    
    def countdown():
        remaining = duration
        last_update_time = time.time()
        
        try:
            countdown_msg = bot.send_message(chat_id, f"⏰ Time remaining: **{remaining}s**", parse_mode='Markdown')
            state.countdown_message_id = countdown_msg.message_id
            # ⚡ CHANGED: Auto-delete countdown message AFTER the full duration
            schedule_auto_delete(chat_id, countdown_msg.message_id, duration)
        except:
            return
        
        while remaining > 0 and not state.stop_countdown:
            if state.question_answered:
                break
                
            current_time = time.time()
            if current_time - last_update_time >= 1:
                remaining -= 1
                last_update_time = current_time
                
                try:
                    if remaining > 0:
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=state.countdown_message_id,
                            text=f"⏰ Time remaining: **{remaining}s**",
                            parse_mode='Markdown'
                        )
                    else:
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=state.countdown_message_id,
                            text="⏰ **Time's up!**",
                            parse_mode='Markdown'
                        )
                except:
                    break
                
            time.sleep(0.1)
    
    state.countdown_thread = threading.Thread(target=countdown)
    state.countdown_thread.start()

def stop_countdown(chat_id):
    """Stop the countdown timer"""
    state = get_state(chat_id)
    state.stop_countdown = True
    if state.countdown_thread and state.countdown_thread.is_alive():
        state.countdown_thread.join(timeout=1)
    
    if state.countdown_message_id:
        try:
            bot.delete_message(chat_id, state.countdown_message_id)
        except:
            pass
        state.countdown_message_id = None

# === LEADERBOARD MANAGEMENT ===
class LeaderboardManager:
    def __init__(self):
        self.lock = threading.Lock()
    
    def show_final_leaderboard(self, chat_id, participants_data, questions_count):
        """Show final leaderboard after all questions are completed"""
        with self.lock:
            if not participants_data:
                msg = bot.send_message(chat_id, "🏆 <b>Final Leaderboard</b> 🏆\n\nNo participants completed the quiz.", parse_mode='HTML')
                schedule_auto_delete(chat_id, msg.message_id)
                return
            
            sorted_participants = sorted(
                [(uid, data) for uid, data in participants_data.items() if data['answers']],
                key=lambda kv: (-kv[1]['score'], kv[1]['total_time_ns'])  # Nanosecond precision for tie-breaking
            )
            
            text = "🏆 <b>QUIZ COMPLETED - FINAL LEADERBOARD</b> 🏆\n\n"
            
            for i, (uid, pdata) in enumerate(sorted_participants, start=1):
                rank_emoji = self.get_rank_emoji(i)
                accuracy = (pdata['correct_answers'] / questions_count) * 100 if questions_count > 0 else 0
                total_time_seconds = pdata['total_time_ns'] / 1_000_000_000  # Convert to seconds for display
                
                text += f"{rank_emoji} <b>{i}.</b> {pdata['name']}\n"
                text += f"   ⭐ Score: <b>{pdata['score']}</b> | 📊 Accuracy: <b>{accuracy:.1f}%</b>\n"
                text += f"   ⏱ Total Time: <b>{total_time_seconds:.2f}s</b>\n"
                text += f"   ✅ Correct: <b>{pdata['correct_answers']}/{questions_count}</b>\n\n"
            
            msg = bot.send_message(chat_id, text, parse_mode='HTML')
            schedule_auto_delete(chat_id, msg.message_id)
            return text
    
    def show_global_leaderboard(self, chat_id):
        """Show global leaderboard with all participants sorted by accuracy"""
        with self.lock:
            participants_data = load_participants()
            
            chat_participants = []
            for user_id_str, data in participants_data.items():
                if chat_id in data.get("chat_ids", []) and data.get("has_completed_current_quiz", False):
                    chat_participants.append({
                        "user_id": int(user_id_str),
                        "name": data.get("name", f"User_{user_id_str}"),
                        "total_score": data.get("total_score", 0),
                        "accuracy": data.get("accuracy", 0),
                        "quizzes_completed": data.get("quizzes_completed", 0)
                    })
            
            chat_participants.sort(key=lambda x: (-x["accuracy"], -x["total_score"]))
            
            if not chat_participants:
                msg = bot.send_message(chat_id, "🏆 <b>Global Leaderboard</b> 🏆\n\nNo participants have completed the current quiz yet!", parse_mode='HTML')
                schedule_auto_delete(chat_id, msg.message_id)
                return
            
            text = "🏆 <b>Global Leaderboard</b> 🏆\n\n"
            text += "<i>Sorted by Accuracy (Highest to Lowest)</i>\n\n"
            
            for i, participant in enumerate(chat_participants):
                rank_emoji = self.get_rank_emoji(i + 1)
                accuracy_str = f"📊 {participant['accuracy']:.1f}%"
                score_str = f"⭐ {participant['total_score']}"
                quizzes_str = f"🎯 {participant['quizzes_completed']}"
                
                text += f"{rank_emoji} <b>{i + 1}.</b> {participant['name']}\n"
                text += f"   {accuracy_str} | {score_str} | {quizzes_str} quizzes\n\n"
            
            msg = bot.send_message(chat_id, text, parse_mode='HTML')
            schedule_auto_delete(chat_id, msg.message_id)
            return text
    
    def get_rank_emoji(self, rank):
        if rank == 1: return "🥇"
        if rank == 2: return "🥈"
        if rank == 3: return "🥉"
        if rank <= 10: return "🔸"
        return "🔹"

# Initialize leaderboard manager
leaderboard_manager = LeaderboardManager()

# === KEYBOARD BUILDER ===
def make_keyboard(q_index, questions):
    keyboard = types.InlineKeyboardMarkup()
    for idx, opt in enumerate(questions[q_index].opts):
        btn = types.InlineKeyboardButton(text=f"{chr(65+idx)}. {opt}", 
                                       callback_data=f"ans|{q_index}|{idx}")
        keyboard.add(btn)
    return keyboard

# === ADMIN PANEL ===
def make_admin_keyboard():
    """Create admin panel keyboard with state management"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = [
        types.InlineKeyboardButton("📊 View Statistics", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 View Participants", callback_data="admin_participants"),
        types.InlineKeyboardButton("❓ View Questions", callback_data="admin_questions"),
        types.InlineKeyboardButton("➕ Add Question", callback_data="admin_add_question"),
        types.InlineKeyboardButton("✏️ Edit Question", callback_data="admin_edit_question"),
        types.InlineKeyboardButton("🗑️ Delete Question", callback_data="admin_delete_question"),
        types.InlineKeyboardButton("⏱️ Set Question Time", callback_data="admin_set_time"),
        types.InlineKeyboardButton("🔄 Reset Quiz", callback_data="admin_reset_quiz"),
        types.InlineKeyboardButton("🚪 Close Quiz", callback_data="admin_close_quiz"),
        types.InlineKeyboardButton("📥 Export Data", callback_data="admin_export"),
        types.InlineKeyboardButton("🔓 Reopen Quiz", callback_data="admin_reopen_quiz"),
        types.InlineKeyboardButton("🗑️ Clear State", callback_data="admin_clear_state"),
        types.InlineKeyboardButton("🔍 State Info", callback_data="admin_state_info"),
        types.InlineKeyboardButton("❌ Close Panel", callback_data="admin_close"),
        types.InlineKeyboardButton("🔄 New Round", callback_data="admin_new_round")
    ]
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.add(buttons[i], buttons[i + 1])
        else:
            keyboard.add(buttons[i])
    
    return keyboard

# Admin state management
admin_edit_state = {}
admin_state_lock = threading.Lock()

def get_admin_state(user_id):
    if user_id not in admin_edit_state:
        with admin_state_lock:
            if user_id not in admin_edit_state:
                admin_edit_state[user_id] = {"mode": None, "data": {}, "last_activity": time.time()}
    return admin_edit_state[user_id]

def clear_admin_state(user_id):
    """Enhanced admin state clearing"""
    if user_id in admin_edit_state:
        with admin_state_lock:
            if user_id in admin_edit_state:
                del admin_edit_state[user_id]
                print(f"✅ Cleared admin state for user {user_id}")

def clear_all_admin_states():
    """Clear all admin states"""
    with admin_state_lock:
        user_ids = list(admin_edit_state.keys())
        for user_id in user_ids:
            del admin_edit_state[user_id]
        print(f"✅ Cleared all {len(user_ids)} admin states")

def cleanup_old_admin_states():
    """Enhanced cleanup of old admin states"""
    current_time = time.time()
    with admin_state_lock:
        for user_id in list(admin_edit_state.keys()):
            state = admin_edit_state[user_id]
            if current_time - state.get('last_activity', 0) > 3600:  # 1 hour
                del admin_edit_state[user_id]
                print(f"🕒 Cleared expired admin state for user {user_id}")

# === COMMANDS ===
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # ⚠️ REMOVED the immediate deletion - let auto-delete handle it after 1 minute
    
    participant_name = get_participant_name(user_id)
    
    if participant_name.startswith("User_"):
        msg = bot.send_message(chat_id,
            "👋 Welcome to TMZ BRAND QUIZ BOT! 🔥\n\n"
            "Please enter your name to register:"
        )
        # Auto-delete registration prompt after 1 minute
        schedule_auto_delete(chat_id, msg.message_id, CONFIG["START_MESSAGE_DELAY"])
        bot.register_next_step_handler(msg, process_name_step, user_id, chat_id)
    else:
        welcome_msg = bot.send_message(chat_id, 
            f"🔥 Welcome back, {participant_name}! 🔥\n\n"
            "Use /start_quiz to begin the quiz.\n"
            "Use /leaderboard to view global rankings.\n"
            "Use /myinfo to see your statistics.",
            parse_mode='HTML'
        )
        # Auto-delete welcome message after 1 minute
        schedule_auto_delete(chat_id, welcome_msg.message_id, CONFIG["START_MESSAGE_DELAY"])
        global_leaderboard = leaderboard_manager.show_global_leaderboard(chat_id)

@bot.message_handler(commands=['leaderboard', 'reload', 'rankings'])
def handle_leaderboard(message):
    """Show global leaderboard"""
    # Delete the command message
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except:
        pass
    
    chat_id = message.chat.id
    global_leaderboard = leaderboard_manager.show_global_leaderboard(chat_id)

@bot.message_handler(commands=['myinfo'])
def handle_myinfo(message):
    # Delete the command message
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except:
        pass
    
    user_id = message.from_user.id
    participant_name = get_participant_name(user_id)
    
    participants = load_participants()
    user_data = participants.get(str(user_id), {})
    
    info_text = f"📊 <b>Your Information</b>\n\n"
    info_text += f"👤 Name: <b>{participant_name}</b>\n"
    info_text += f"🆔 User ID: <code>{user_id}</code>\n"
    info_text += f"⭐ Total Score: <b>{user_data.get('total_score', 0)}</b>\n"
    info_text += f"📊 Accuracy: <b>{user_data.get('accuracy', 0):.1f}%</b>\n"
    info_text += f"🎯 Quizzes Completed: <b>{user_data.get('quizzes_completed', 0)}</b>\n"
    
    quiz_status = "✅ Completed" if user_data.get('has_completed_current_quiz', False) else "❌ Not Completed"
    info_text += f"📝 Current Quiz: <b>{quiz_status}</b>\n"
    
    if "first_seen" in user_data:
        first_seen = datetime.fromisoformat(user_data["first_seen"]).strftime("%Y-%m-%d %H:%M")
        info_text += f"📅 First Seen: {first_seen}\n"
    
    msg = bot.send_message(message.chat.id, info_text, parse_mode='HTML')
    schedule_auto_delete(message.chat.id, msg.message_id)

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    # Delete the command message
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except:
        pass
    
    user_id = message.from_user.id
    if not is_admin(user_id):
        msg = bot.send_message(message.chat.id, "❌ Admin only command.")
        schedule_auto_delete(message.chat.id, msg.message_id)
        return
    
    msg = bot.send_message(
        message.chat.id,
        "🛠️ <b>Admin Panel</b>\n\n"
        "Select an option below to manage the quiz:",
        reply_markup=make_admin_keyboard(),
        parse_mode='HTML'
    )
    schedule_auto_delete(message.chat.id, msg.message_id)

@bot.message_handler(commands=['clear_state'])
def handle_clear_state(message):
    """Admin command to clear state for current chat"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        msg = bot.send_message(message.chat.id, "❌ Admin only command.")
        schedule_auto_delete(message.chat.id, msg.message_id)
        return
    
    # Delete the command message
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except:
        pass
    
    chat_id = message.chat.id
    clear_state(chat_id)
    clear_admin_state(user_id)
    
    msg = bot.send_message(message.chat.id, "✅ All states cleared for this chat and user.")
    schedule_auto_delete(message.chat.id, msg.message_id)

@bot.message_handler(commands=['state_info'])
def handle_state_info(message):
    """Admin command to check current states"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        msg = bot.send_message(message.chat.id, "❌ Admin only command.")
        schedule_auto_delete(message.chat.id, msg.message_id)
        return
    
    # Delete the command message
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except:
        pass
    
    chat_id = message.chat.id
    
    state_info = "🔍 <b>Current States</b>\n\n"
    
    # Quiz states
    state_info += f"<b>Active Quiz Chats:</b> {len(chat_state)}\n"
    for cid, state in list(chat_state.items()):
        status = "🟢 Running" if state.is_running else "🟡 Idle"
        state_info += f"  • Chat {cid}: {status} (Q{state.current_q + 1}/{len(state.questions)})\n"
    
    # Admin states
    state_info += f"\n<b>Active Admin Sessions:</b> {len(admin_edit_state)}\n"
    for uid, admin_state in list(admin_edit_state.items()):
        mode = admin_state.get('mode', 'None')
        state_info += f"  • User {uid}: {mode}\n"
    
    msg = bot.send_message(chat_id, state_info, parse_mode='HTML')
    schedule_auto_delete(message.chat.id, msg.message_id)

@bot.message_handler(commands=['reset_all_data'])
def handle_reset_all_data(message):
    """Admin command to completely reset all data for next round"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        msg = bot.send_message(message.chat.id, "❌ Admin only command.")
        schedule_auto_delete(message.chat.id, msg.message_id)
        return
    
    # Delete the command message
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except:
        pass
    
    # Reset all data
    reset_all_quiz_data()
    
    msg = bot.send_message(
        message.chat.id,
        "✅ **COMPLETE DATA RESET**\n\n"
        "All user data has been erased for the next round!\n"
        "• Quiz completion records cleared\n"
        "• All participant data reset\n"
        "• Users can start fresh",
        parse_mode='HTML'
    )
    schedule_auto_delete(message.chat.id, msg.message_id)

def reset_all_quiz_data():
    """Completely reset all quiz data for new round"""
    try:
        # 1. Reset quiz completion data
        completion_data = {
            "completed_users": [],
            "quiz_active": True
        }
        with open(CONFIG["QUIZ_COMPLETION_FILE"], 'w', encoding='utf-8') as f:
            json.dump(completion_data, f, indent=2, ensure_ascii=False)
        
        # 2. Reset participant data (keep names but reset scores and completion)
        participants = load_participants()
        for user_id, data in participants.items():
            # Keep name and basic info, reset everything else
            participants[user_id] = {
                "name": data.get("name", f"User_{user_id}"),
                "first_seen": data.get("first_seen", datetime.now().strftime("%Y-%m-%dT%H:%M:%S")),
                "chat_ids": data.get("chat_ids", []),
                "total_score": 0,
                "quizzes_completed": 0,
                "accuracy": 0,
                "has_completed_current_quiz": False,
                "last_seen": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            }
        
        with open(CONFIG["PARTICIPANTS_FILE"], 'w', encoding='utf-8') as f:
            json.dump(participants, f, indent=2, ensure_ascii=False)
        
        # 3. Clear all active states
        clear_all_states()
        clear_all_admin_states()
        
        print("✅ Complete data reset for new round")
        return True
        
    except Exception as e:
        print(f"Error resetting data: {e}")
        return False

@bot.message_handler(commands=['reopen_quiz'])
def handle_reopen_quiz(message):
    """Reopen quiz (Admin only)"""
    # Delete the command message
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except:
        pass
    
    user_id = message.from_user.id
    if not is_admin(user_id):
        msg = bot.send_message(message.chat.id, "❌ Admin only command.")
        schedule_auto_delete(message.chat.id, msg.message_id)
        return
    
    set_quiz_active(True)
    msg = bot.send_message(message.chat.id, "✅ Quiz reopened! Users can now start the quiz.")
    schedule_auto_delete(message.chat.id, msg.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_new_round")
def handle_new_round(call):
    """Handle new round confirmation"""
    user_id = call.from_user.id
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "❌ Admin only!")
        return
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✅ Yes, Start New Round", callback_data="confirm_new_round"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="admin_stats")
    )
    
    bot.edit_message_text(
        "🔄 <b>Start New Round</b>\n\n"
        "This will:\n"
        "• Reset all user scores to 0\n"
        "• Clear quiz completion records\n"
        "• Allow everyone to play again\n"
        "• Keep user names and registration\n\n"
        "Are you sure?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "confirm_new_round")
def handle_confirm_new_round(call):
    """Confirm and execute new round"""
    try:
        if reset_all_quiz_data():
            bot.edit_message_text(
                "✅ <b>New Round Started!</b>\n\n"
                "All user data has been reset.\n"
                "Everyone can now participate in the new quiz round!",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        else:
            bot.edit_message_text(
                "❌ <b>Error resetting data!</b>",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Error in new round: {e}")
        bot.answer_callback_query(call.id, "❌ Error starting new round")

# === ADMIN CALLBACK HANDLERS ===
@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("admin_"))
def handle_admin_callback(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "❌ Admin only!")
        return
    
    action = call.data
    
    if action == "admin_stats":
        show_admin_stats(call)
    elif action == "admin_participants":
        show_participants_list(call)
    elif action == "admin_questions":
        show_questions_list(call)
    elif action == "admin_add_question":
        start_add_question(call)
    elif action == "admin_edit_question":
        start_edit_question(call)
    elif action == "admin_delete_question":
        start_delete_question(call)
    elif action == "admin_set_time":
        set_question_time(call)
    elif action == "admin_reset_quiz":
        reset_quiz_confirmation(call)
    elif action == "admin_close_quiz":
        close_quiz_confirmation(call)
    elif action == "admin_reopen_quiz":
        reopen_quiz_confirmation(call)
    elif action == "admin_export":
        export_data(call)
    elif action == "admin_clear_state":
        clear_state_confirmation(call)
    elif action == "admin_state_info":
        show_state_info(call)
    elif action == "admin_close":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Admin panel closed")

def show_admin_stats(call):
    """Show comprehensive admin statistics"""
    completion_data = load_quiz_completion()
    participants = load_participants()
    questions = load_questions()
    
    completed_count = len(completion_data.get("completed_users", []))
    total_participants = len(participants)
    active_participants = len([p for p in participants.values() if p.get("has_completed_current_quiz", False)])
    
    # Calculate average accuracy
    accuracies = [p.get("accuracy", 0) for p in participants.values() if p.get("accuracy", 0) > 0]
    avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0
    
    stats_text = f"📊 <b>Admin Statistics</b>\n\n"
    stats_text += f"🔄 Quiz Active: <b>{'✅ YES' if completion_data.get('quiz_active', True) else '❌ NO'}</b>\n"
    stats_text += f"❓ Questions: <b>{len(questions)}</b>\n"
    stats_text += f"⏱ Question Time: <b>{CONFIG['QUESTION_TIME']}s</b>\n\n"
    
    stats_text += f"👥 <b>Participants:</b>\n"
    stats_text += f"   • Total Registered: <b>{total_participants}</b>\n"
    stats_text += f"   • Completed Quiz: <b>{active_participants}</b>\n"
    stats_text += f"   • Completion Rate: <b>{(active_participants/total_participants*100) if total_participants > 0 else 0:.1f}%</b>\n\n"
    
    stats_text += f"📈 <b>Performance:</b>\n"
    stats_text += f"   • Average Accuracy: <b>{avg_accuracy:.1f}%</b>\n"
    
    total_score = sum(p.get("total_score", 0) for p in participants.values())
    stats_text += f"   • Total Score: <b>{total_score}</b>\n"
    
    # State information
    stats_text += f"\n🔍 <b>System State:</b>\n"
    stats_text += f"   • Active Quiz Chats: <b>{len(chat_state)}</b>\n"
    stats_text += f"   • Active Admin Sessions: <b>{len(admin_edit_state)}</b>\n"
    
    bot.edit_message_text(
        stats_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=make_admin_keyboard(),
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

def show_participants_list(call):
    """Show list of all participants"""
    participants = load_participants()
    
    if not participants:
        bot.edit_message_text(
            "👥 <b>Participants</b>\n\nNo participants registered yet.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=make_admin_keyboard(),
            parse_mode='HTML'
        )
        return
    
    text = "👥 <b>All Participants</b>\n\n"
    
    sorted_participants = sorted(
        participants.items(),
        key=lambda x: x[1].get("total_score", 0),
        reverse=True
    )
    
    for i, (user_id, data) in enumerate(sorted_participants[:20], 1):  # Show first 20
        status = "✅" if data.get("has_completed_current_quiz", False) else "❌"
        text += f"{i}. {data.get('name', 'Unknown')} [{status}]\n"
        text += f"   Score: {data.get('total_score', 0)} | Acc: {data.get('accuracy', 0):.1f}%\n"
        text += f"   ID: {user_id}\n\n"
    
    if len(participants) > 20:
        text += f"\n... and {len(participants) - 20} more participants"
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=make_admin_keyboard(),
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

def show_questions_list(call):
    """Show list of all questions"""
    questions = load_questions()
    
    if not questions:
        bot.edit_message_text(
            "❓ <b>Questions</b>\n\nNo questions available.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=make_admin_keyboard(),
            parse_mode='HTML'
        )
        return
    
    text = f"❓ <b>All Questions ({len(questions)})</b>\n\n"
    
    for i, q in enumerate(questions, 1):
        text += f"<b>Q{i}:</b> {q.q}\n"
        text += f"<b>Options:</b>\n"
        for idx, opt in enumerate(q.opts):
            correct_indicator = " ✅" if idx == q.correct_index else ""
            text += f"  {chr(65+idx)}. {opt}{correct_indicator}\n"
        text += f"<b>Correct:</b> {chr(65+q.correct_index)}\n\n"
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=make_admin_keyboard(),
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

def start_add_question(call):
    """Start process to add a new question"""
    admin_state = get_admin_state(call.from_user.id)
    admin_state["mode"] = "add_question"
    admin_state["data"] = {"step": "question"}
    admin_state["last_activity"] = time.time()
    
    bot.edit_message_text(
        "➕ <b>Add New Question</b>\n\nPlease send the question text:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

def start_edit_question(call):
    """Start process to edit a question"""
    questions = load_questions()
    
    if not questions:
        bot.edit_message_text(
            "❌ No questions available to edit.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=make_admin_keyboard(),
            parse_mode='HTML'
        )
        return
    
    keyboard = types.InlineKeyboardMarkup()
    for i in range(len(questions)):
        keyboard.add(types.InlineKeyboardButton(
            f"Q{i+1}", 
            callback_data=f"edit_q_{i}"
        ))
    keyboard.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_questions"))
    
    bot.edit_message_text(
        "✏️ <b>Edit Question</b>\n\nSelect question to edit:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

def start_delete_question(call):
    """Start process to delete a question"""
    questions = load_questions()
    
    if not questions:
        bot.edit_message_text(
            "❌ No questions available to delete.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=make_admin_keyboard(),
            parse_mode='HTML'
        )
        return
    
    keyboard = types.InlineKeyboardMarkup()
    for i in range(len(questions)):
        keyboard.add(types.InlineKeyboardButton(
            f"Q{i+1}: {questions[i].q[:30]}...", 
            callback_data=f"delete_q_{i}"
        ))
    keyboard.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_questions"))
    
    bot.edit_message_text(
        "🗑️ <b>Delete Question</b>\n\nSelect question to delete:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

def set_question_time(call):
    """Set question time"""
    admin_state = get_admin_state(call.from_user.id)
    admin_state["mode"] = "set_time"
    admin_state["last_activity"] = time.time()
    
    bot.edit_message_text(
        f"⏱️ <b>Set Question Time</b>\n\nCurrent time: {CONFIG['QUESTION_TIME']} seconds\n\n"
        "Send new time in seconds (5-60):",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

def reset_quiz_confirmation(call):
    """Confirm quiz reset"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✅ Yes, Reset", callback_data="confirm_reset"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="admin_stats")
    )
    
    bot.edit_message_text(
        "🔄 <b>Reset Quiz</b>\n\n"
        "This will allow all users to take the quiz again.\n"
        "Are you sure you want to reset?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

def close_quiz_confirmation(call):
    """Confirm quiz closure"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✅ Yes, Close", callback_data="confirm_close"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="admin_stats")
    )
    
    bot.edit_message_text(
        "🚪 <b>Close Quiz</b>\n\n"
        "This will prevent new users from starting the quiz.\n"
        "Are you sure you want to close?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

def reopen_quiz_confirmation(call):
    """Confirm quiz reopening"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✅ Yes, Reopen", callback_data="confirm_reopen"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="admin_stats")
    )
    
    bot.edit_message_text(
        "🔓 <b>Reopen Quiz</b>\n\n"
        "This will allow new users to start the quiz.\n"
        "Are you sure you want to reopen?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

def clear_state_confirmation(call):
    """Confirm state clearing"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✅ Clear Current Chat", callback_data="confirm_clear_current"),
        types.InlineKeyboardButton("🗑️ Clear All States", callback_data="confirm_clear_all"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="admin_stats")
    )
    
    state_info = "🗑️ <b>Clear States</b>\n\n"
    state_info += f"Active Quiz Chats: <b>{len(chat_state)}</b>\n"
    state_info += f"Active Admin Sessions: <b>{len(admin_edit_state)}</b>\n\n"
    state_info += "Select what to clear:"
    
    bot.edit_message_text(
        state_info,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

def show_state_info(call):
    """Show detailed state information"""
    state_info = "🔍 <b>Detailed State Information</b>\n\n"
    
    # Quiz states
    state_info += f"<b>Active Quiz Chats ({len(chat_state)}):</b>\n"
    for cid, state in list(chat_state.items()):
        status = "🟢 Running" if state.is_running else "🟡 Idle"
        participants_count = len(state.participants)
        state_info += f"  • Chat {cid}: {status}\n"
        state_info += f"    Q{state.current_q + 1}/{len(state.questions)} | Participants: {participants_count}\n"
    
    # Admin states
    state_info += f"\n<b>Active Admin Sessions ({len(admin_edit_state)}):</b>\n"
    for uid, admin_state in list(admin_edit_state.items()):
        mode = admin_state.get('mode', 'None')
        last_active = time.time() - admin_state.get('last_activity', 0)
        state_info += f"  • User {uid}: {mode} ({last_active:.0f}s ago)\n"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="admin_state_info"))
    keyboard.add(types.InlineKeyboardButton("🗑️ Clear States", callback_data="admin_clear_state"))
    keyboard.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_stats"))
    
    bot.edit_message_text(
        state_info,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

def export_data(call):
    """Export quiz data"""
    participants = load_participants()
    questions = load_questions()
    completion_data = load_quiz_completion()
    
    export_text = f"📥 <b>Quiz Data Export</b>\n\n"
    export_text += f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    export_text += f"❓ Questions: {len(questions)}\n"
    export_text += f"👥 Participants: {len(participants)}\n"
    export_text += f"✅ Completed: {len(completion_data.get('completed_users', []))}\n\n"
    
    export_text += "<b>Top Participants:</b>\n"
    sorted_participants = sorted(
        participants.items(),
        key=lambda x: x[1].get("total_score", 0),
        reverse=True
    )[:10]
    
    for i, (user_id, data) in enumerate(sorted_participants, 1):
        export_text += f"{i}. {data.get('name', 'Unknown')} - Score: {data.get('total_score', 0)} - Acc: {data.get('accuracy', 0):.1f}%\n"
    
    bot.edit_message_text(
        export_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=make_admin_keyboard(),
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)

# === QUIZ MANAGEMENT ===
@bot.message_handler(commands=['start_quiz'])
def handle_start_quiz(message):
    # Delete the command message
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except:
        pass
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if has_user_completed_quiz(user_id):
        msg = bot.send_message(chat_id, 
            "❌ <b>Access Denied</b>\n\n"
            "You have already completed this quiz. Each participant can only attempt the quiz once.\n\n"
            "Use /leaderboard to view the current rankings.",
            parse_mode='HTML'
        )
        schedule_auto_delete(chat_id, msg.message_id)
        return
    
    if not is_quiz_active():
        msg = bot.send_message(chat_id,
            "❌ <b>Quiz Closed</b>\n\n"
            "The quiz has been closed by the administrator.\n\n"
            "Use /leaderboard to view the final results.",
            parse_mode='HTML'
        )
        schedule_auto_delete(chat_id, msg.message_id)
        return
    
    state = get_state(chat_id)

    with state.lock:
        if state.is_running:
            msg = bot.send_message(chat_id, "⚠️ A quiz is already running!")
            schedule_auto_delete(chat_id, msg.message_id)
            return
        
        questions = load_questions()
        if not questions:
            msg = bot.send_message(chat_id, "❌ No questions available. Contact admin.")
            schedule_auto_delete(chat_id, msg.message_id)
            return
        
        state.questions = questions
        state.is_running = True
        state.current_q = -1
        state.participants.clear()
        state.first_correct_for_question.clear()
        state.quiz_start_time_ns = time.time_ns()  # Nanoseconds

    start_msg = bot.send_message(chat_id, 
        f"🎯 TMZ BRAND Quiz is starting! {len(questions)} questions coming...\n"
        f"⏰ {CONFIG['QUESTION_TIME']} seconds per question\n\n"
        f"⚡ <b>Instant Mode:</b> Questions advance immediately when answered!\n"
        f"🏆 <b>Leaderboard:</b> Final results shown after all questions\n\n"
        f"⚠️ <b>Important Rules:</b>\n"
        f"• No sharing answers\n"
        f"• One attempt per question\n"
        f"• One attempt per quiz - no repeats!\n"
        f"• Fastest correct answers get bonus points!",
        parse_mode='HTML'
    )
    schedule_auto_delete(chat_id, start_msg.message_id)
    
    thread = threading.Thread(target=run_quiz, args=(chat_id, user_id))
    thread.start()

def run_quiz(chat_id, user_id):
    try:
        state = get_state(chat_id)
        questions = state.questions

        for q_idx in range(len(questions)):
            with state.lock:
                if not state.is_running:
                    break
                
                state.current_q = q_idx
                state.question_answered = False
                state.answered_users_per_question.clear()
                state.first_correct_for_question[q_idx] = None
                state.question_start_time_ns = time.time_ns()  # Nanoseconds

            # Send question
            question_text = f"❓ <b>Question {q_idx+1}/{len(questions)}</b>\n\n{questions[q_idx].q}"
            sent_msg = bot.send_message(chat_id, question_text, 
                                      reply_markup=make_keyboard(q_idx, questions),
                                      parse_mode='HTML')
            
            with state.lock:
                state.question_message_id = sent_msg.message_id

            # Start countdown
            start_countdown(chat_id, CONFIG["QUESTION_TIME"])

            # Wait for time or all answers
            question_start = time.time()
            while time.time() - question_start < CONFIG["QUESTION_TIME"]:
                with state.lock:
                    if state.question_answered:
                        break
                time.sleep(0.1)

            # Stop countdown
            stop_countdown(chat_id)

            # Delete the question message immediately
            try:
                bot.delete_message(chat_id, state.question_message_id)
            except Exception:
                pass

            # Wait before next question
            time.sleep(CONFIG["QUESTION_TRANSITION_DELAY"])

        # Quiz completed
        with state.lock:
            state.is_running = False
            
            # Update participant stats
            for uid, pdata in state.participants.items():
                if pdata['answers']:  # Only update if they answered at least one question
                    update_participant_stats(uid, pdata['score'], pdata['correct_answers'], len(questions))
                    mark_user_completed(uid)  # Mark as completed

            # Show final leaderboard
            final_leaderboard = leaderboard_manager.show_final_leaderboard(
                chat_id, state.participants, len(questions)
            )
            
    except Exception as e:
        print(f"Error in quiz: {e}")
        msg = bot.send_message(chat_id, "❌ An error occurred during the quiz. Please try again.")
        schedule_auto_delete(chat_id, msg.message_id)
    finally:
        # Always clear state whether quiz completes or errors
        clear_state(chat_id)

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("ans|"))
def handle_answer(call):
    try:
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        
        if has_user_completed_quiz(user_id):
            bot.answer_callback_query(call.id, "❌ You already completed this quiz!", show_alert=True)
            return
        
        state = get_state(chat_id)
        
        with state.answer_lock:
            if not state.is_running or state.question_answered:
                bot.answer_callback_query(call.id, "❌ Too late! Question time expired.")
                return

            # Parse callback data
            parts = call.data.split("|")
            q_idx = int(parts[1])
            ans_idx = int(parts[2])

            if q_idx != state.current_q:
                bot.answer_callback_query(call.id, "❌ Invalid question!")
                return

            if user_id in state.answered_users_per_question:
                bot.answer_callback_query(call.id, "❌ You already answered this question!")
                return

            # Record answer
            state.answered_users_per_question.add(user_id)
            participant_name = get_participant_name(user_id)
            
            if user_id not in state.participants:
                state.participants[user_id] = {
                    "score": 0,
                    "answers": {},
                    "total_time_ns": 0,
                    "name": participant_name,
                    "correct_answers": 0
                }

            # Calculate response time (nanoseconds)
            response_time_ns = time.time_ns() - state.question_start_time_ns
            state.participants[user_id]["total_time_ns"] += response_time_ns

            # Check answer
            is_correct = (ans_idx == state.questions[q_idx].correct_index)
            state.participants[user_id]["answers"][q_idx] = {
                "answer_index": ans_idx,
                "correct": is_correct,
                "time_ns": response_time_ns
            }

            points_earned = 0
            if is_correct:
                points_earned = CONFIG["POINTS_CORRECT"]
                state.participants[user_id]["correct_answers"] += 1
                
                # First correct bonus
                if state.first_correct_for_question[q_idx] is None:
                    state.first_correct_for_question[q_idx] = user_id
                    points_earned += CONFIG["POINTS_FIRST_CORRECT_BONUS"]
                    bonus_text = " + 🚀 First Correct Bonus!"
                else:
                    bonus_text = ""
                
                state.participants[user_id]["score"] += points_earned
                
                # Convert nanoseconds to seconds for display
                response_time_seconds = response_time_ns / 1_000_000_000
                
                # Send immediate feedback
                feedback = (
                    f"✅ <b>CORRECT!</b> {participant_name}\n"
                    f"🏆 Points: +{points_earned}{bonus_text}\n"
                    f"⏱ Time: {response_time_seconds:.2f}s"
                )
                
                bot.answer_callback_query(call.id, f"✅ Correct! +{points_earned} points")
                
                # Check if this should advance the question
                if len(state.answered_users_per_question) >= len(state.participants):
                    state.question_answered = True
                    stop_countdown(chat_id)
            else:
                correct_letter = chr(65 + state.questions[q_idx].correct_index)
                bot.answer_callback_query(call.id, f"❌ Wrong!")
                feedback = f"❌ <b>WRONG!</b> {participant_name}"

            # Send feedback message
            feedback_msg = bot.send_message(chat_id, feedback, parse_mode='HTML')
            schedule_auto_delete(chat_id, feedback_msg.message_id)

            # Show live points update
            leaderboard = "🏅 <b>Live Points</b>\n"
            sorted_participants = sorted(
                state.participants.items(),
                key=lambda x: -x[1]['score']
            )
            for i, (uid, pdata) in enumerate(sorted_participants, 1):
                leaderboard += f"{i}. {pdata['name']}: <b>{pdata['score']}</b> pts\n"
            leaderboard_msg = bot.send_message(chat_id, leaderboard, parse_mode='HTML')
            schedule_auto_delete(chat_id, leaderboard_msg.message_id)
            
    except Exception as e:
        print(f"Error handling answer: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ An error occurred")
        except:
            pass

# === EDIT QUESTION HANDLERS ===
@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("edit_q_"))
def handle_edit_question_select(call):
    """Handle selection of question to edit"""
    try:
        question_index = int(call.data.split("_")[2])
        questions = load_questions()
        
        if question_index >= len(questions):
            bot.answer_callback_query(call.id, "❌ Invalid question!")
            return
        
        question = questions[question_index]
        
        admin_state = get_admin_state(call.from_user.id)
        admin_state["mode"] = "edit_question"
        admin_state["data"] = {
            "step": "question",
            "question_index": question_index,
            "current_question": question.q,
            "current_options": question.opts.copy(),
            "current_correct": question.correct_index
        }
        admin_state["last_activity"] = time.time()
        
        # Show current question and options
        text = f"✏️ <b>Editing Question {question_index + 1}</b>\n\n"
        text += f"<b>Current Question:</b>\n{question.q}\n\n"
        text += f"<b>Current Options:</b>\n"
        for i, opt in enumerate(question.opts):
            correct_indicator = " ✅" if i == question.correct_index else ""
            text += f"{chr(65+i)}. {opt}{correct_indicator}\n"
        text += f"\n<b>What would you like to edit?</b>"
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("📝 Question Text", callback_data="edit_question_text"))
        keyboard.add(types.InlineKeyboardButton("🔤 Options", callback_data="edit_question_options"))
        keyboard.add(types.InlineKeyboardButton("✅ Correct Answer", callback_data="edit_question_correct"))
        keyboard.add(types.InlineKeyboardButton("💾 Save All Changes", callback_data="edit_question_save"))
        keyboard.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_edit_question"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Error in edit question select: {e}")
        bot.answer_callback_query(call.id, "❌ Error loading question")

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("edit_question_"))
def handle_edit_question_action(call):
    """Handle edit question actions"""
    try:
        action = call.data
        admin_state = get_admin_state(call.from_user.id)
        admin_state["last_activity"] = time.time()
        
        if action == "edit_question_text":
            admin_state["data"]["step"] = "edit_text"
            bot.edit_message_text(
                "📝 <b>Edit Question Text</b>\n\n"
                "Please send the new question text:",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        
        elif action == "edit_question_options":
            admin_state["data"]["step"] = "edit_options"
            admin_state["data"]["current_option_index"] = 0
            
            text = "🔤 <b>Edit Options</b>\n\n"
            text += "Please send the new text for each option one by one.\n\n"
            text += f"<b>Option A:</b> {admin_state['data']['current_options'][0]}\n"
            text += f"<b>Option B:</b> {admin_state['data']['current_options'][1]}\n"
            text += f"<b>Option C:</b> {admin_state['data']['current_options'][2]}\n"
            text += f"<b>Option D:</b> {admin_state['data']['current_options'][3]}\n\n"
            text += "Starting with <b>Option A</b>. Send the new text:"
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        
        elif action == "edit_question_correct":
            admin_state["data"]["step"] = "edit_correct"
            
            text = "✅ <b>Set Correct Answer</b>\n\n"
            text += "Select the correct option:\n\n"
            
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            for i in range(4):
                keyboard.add(types.InlineKeyboardButton(
                    f"Option {chr(65+i)}", 
                    callback_data=f"set_correct_{i}"
                ))
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        
        elif action == "edit_question_save":
            save_edited_question(call)
            return
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Error in edit question action: {e}")
        bot.answer_callback_query(call.id, "❌ Error processing request")

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("set_correct_"))
def handle_set_correct(call):
    """Set correct answer index"""
    try:
        correct_index = int(call.data.split("_")[2])
        admin_state = get_admin_state(call.from_user.id)
        admin_state["last_activity"] = time.time()
        
        admin_state["data"]["current_correct"] = correct_index
        
        # Show updated question preview
        question_index = admin_state["data"]["question_index"]
        text = f"✅ <b>Correct Answer Updated</b>\n\n"
        text += f"<b>Question {question_index + 1}:</b>\n{admin_state['data']['current_question']}\n\n"
        text += f"<b>Options:</b>\n"
        for i, opt in enumerate(admin_state["data"]["current_options"]):
            correct_indicator = " ✅" if i == correct_index else ""
            text += f"{chr(65+i)}. {opt}{correct_indicator}\n"
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("📝 Question Text", callback_data="edit_question_text"))
        keyboard.add(types.InlineKeyboardButton("🔤 Options", callback_data="edit_question_options"))
        keyboard.add(types.InlineKeyboardButton("✅ Correct Answer", callback_data="edit_question_correct"))
        keyboard.add(types.InlineKeyboardButton("💾 Save All Changes", callback_data="edit_question_save"))
        keyboard.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_edit_question"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id, "✅ Correct answer set!")
    except Exception as e:
        print(f"Error setting correct answer: {e}")
        bot.answer_callback_query(call.id, "❌ Error setting correct answer")

def save_edited_question(call):
    """Save the edited question"""
    try:
        admin_state = get_admin_state(call.from_user.id)
        question_index = admin_state["data"]["question_index"]
        
        # Load current questions
        questions = load_questions()
        
        # Update the question
        questions[question_index] = Question(
            q=admin_state["data"]["current_question"],
            opts=admin_state["data"]["current_options"],
            correct_index=admin_state["data"]["current_correct"]
        )
        
        # Save back to file
        if save_questions(questions):
            bot.edit_message_text(
                f"✅ <b>Question {question_index + 1} updated successfully!</b>",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
            clear_admin_state(call.from_user.id)
        else:
            bot.edit_message_text(
                "❌ <b>Error saving question!</b>",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Error saving edited question: {e}")
        bot.answer_callback_query(call.id, "❌ Error saving question")

# === DELETE QUESTION HANDLERS ===
@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("delete_q_"))
def handle_delete_question(call):
    """Handle deletion of a question"""
    try:
        question_index = int(call.data.split("_")[2])
        questions = load_questions()
        
        if question_index >= len(questions):
            bot.answer_callback_query(call.id, "❌ Invalid question!")
            return
        
        question = questions[question_index]
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete_{question_index}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="admin_delete_question")
        )
        
        bot.edit_message_text(
            f"🗑️ <b>Delete Question {question_index + 1}</b>\n\n"
            f"<b>Question:</b> {question.q}\n\n"
            f"Are you sure you want to delete this question?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Error in delete question: {e}")
        bot.answer_callback_query(call.id, "❌ Error loading question")

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("confirm_delete_"))
def handle_confirm_delete(call):
    """Confirm and delete the question"""
    try:
        question_index = int(call.data.split("_")[2])
        questions = load_questions()
        
        if question_index >= len(questions):
            bot.answer_callback_query(call.id, "❌ Invalid question!")
            return
        
        # Remove the question
        deleted_question = questions.pop(question_index)
        
        # Save updated questions
        if save_questions(questions):
            bot.edit_message_text(
                f"✅ <b>Question {question_index + 1} deleted successfully!</b>\n\n"
                f"Remaining questions: {len(questions)}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        else:
            bot.edit_message_text(
                "❌ <b>Error deleting question!</b>",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Error confirming delete: {e}")
        bot.answer_callback_query(call.id, "❌ Error deleting question")

# === CONFIRMATION HANDLERS ===
@bot.callback_query_handler(func=lambda call: call.data in ["confirm_reset", "confirm_close", "confirm_reopen", "confirm_clear_current", "confirm_clear_all"])
def handle_confirmation(call):
    """Handle reset and close confirmations"""
    try:
        if call.data == "confirm_reset":
            # Reset quiz completion data
            completion_data = load_quiz_completion()
            completion_data["completed_users"] = []
            completion_data["quiz_active"] = True
            save_quiz_completion(completion_data)
            
            # Reset participant completion flags
            participants = load_participants()
            for user_data in participants.values():
                user_data["has_completed_current_quiz"] = False
            save_participants(participants)
            
            bot.edit_message_text(
                "✅ <b>Quiz reset successfully!</b>\n\nAll users can now take the quiz again.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        
        elif call.data == "confirm_close":
            set_quiz_active(False)
            bot.edit_message_text(
                "✅ <b>Quiz closed successfully!</b>\n\nNew users cannot start the quiz.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        
        elif call.data == "confirm_reopen":
            set_quiz_active(True)
            bot.edit_message_text(
                "✅ <b>Quiz reopened successfully!</b>\n\nNew users can now start the quiz.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        
        elif call.data == "confirm_clear_current":
            # Clear current chat state
            clear_state(call.message.chat.id)
            clear_admin_state(call.from_user.id)
            bot.edit_message_text(
                "✅ <b>Current chat and user states cleared!</b>",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        
        elif call.data == "confirm_clear_all":
            # Clear all states
            clear_all_states()
            clear_all_admin_states()
            bot.edit_message_text(
                f"✅ <b>All states cleared!</b>\n\n"
                f"Cleared {len(chat_state)} quiz chats and {len(admin_edit_state)} admin sessions.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Error in confirmation handler: {e}")
        bot.answer_callback_query(call.id, "❌ Error processing request")

# === MESSAGE HANDLERS FOR ADMIN ===
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Handle all text messages for admin workflows"""
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        admin_state = get_admin_state(user_id)
        
        if not admin_state["mode"]:
            # Delete non-command messages that aren't part of admin workflow
            try:
                bot.delete_message(chat_id, message.message_id)
            except:
                pass
            return
        
        # Update last activity
        admin_state["last_activity"] = time.time()
        
        if admin_state["mode"] == "add_question":
            handle_add_question_flow(message, admin_state)
        
        elif admin_state["mode"] == "edit_question":
            handle_edit_question_flow(message, admin_state)
        
        elif admin_state["mode"] == "set_time":
            handle_set_time(message, admin_state)
            
    except Exception as e:
        print(f"Error handling admin message: {e}")
        msg = bot.send_message(message.chat.id, "❌ An error occurred processing your request.")
        schedule_auto_delete(message.chat.id, msg.message_id)

def handle_add_question_flow(message, admin_state):
    """Handle the add question workflow"""
    try:
        step = admin_state["data"].get("step")
        admin_state["last_activity"] = time.time()
        
        # Delete the user's input message
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        
        if step == "question":
            admin_state["data"]["question"] = message.text
            admin_state["data"]["step"] = "options"
            admin_state["data"]["options"] = []
            admin_state["data"]["current_option"] = 0
            
            msg = bot.send_message(
                message.chat.id,
                f"📝 <b>Question saved!</b>\n\nNow enter <b>Option A</b>:",
                parse_mode='HTML'
            )
            schedule_auto_delete(message.chat.id, msg.message_id)
            bot.register_next_step_handler(msg, handle_add_question_flow, admin_state)
        
        elif step == "options":
            option_text = message.text
            admin_state["data"]["options"].append(option_text)
            admin_state["data"]["current_option"] += 1
            
            if admin_state["data"]["current_option"] < 4:
                option_letter = chr(65 + admin_state["data"]["current_option"])
                msg = bot.send_message(
                    message.chat.id,
                    f"✅ Option saved! Now enter <b>Option {option_letter}</b>:",
                    parse_mode='HTML'
                )
                schedule_auto_delete(message.chat.id, msg.message_id)
                bot.register_next_step_handler(msg, handle_add_question_flow, admin_state)
            else:
                # All options collected, now ask for correct answer
                keyboard = types.InlineKeyboardMarkup(row_width=2)
                for i in range(4):
                    keyboard.add(types.InlineKeyboardButton(
                        f"Option {chr(65+i)}: {admin_state['data']['options'][i]}", 
                        callback_data=f"add_correct_{i}"
                    ))
                
                msg = bot.send_message(
                    message.chat.id,
                    "✅ All options saved! Now select the <b>correct answer</b>:",
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                schedule_auto_delete(message.chat.id, msg.message_id)
                admin_state["data"]["step"] = "correct"
    except Exception as e:
        print(f"Error in add question flow: {e}")
        msg = bot.send_message(message.chat.id, "❌ Error adding question")
        schedule_auto_delete(message.chat.id, msg.message_id)
        clear_admin_state(message.from_user.id)

def handle_edit_question_flow(message, admin_state):
    """Handle the edit question workflow"""
    try:
        step = admin_state["data"].get("step")
        admin_state["last_activity"] = time.time()
        
        # Delete the user's input message
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        
        if step == "edit_text":
            admin_state["data"]["current_question"] = message.text
            
            # Show updated preview
            question_index = admin_state["data"]["question_index"]
            text = f"✅ <b>Question Text Updated</b>\n\n"
            text += f"<b>Question {question_index + 1}:</b>\n{message.text}\n\n"
            text += f"<b>Options:</b>\n"
            for i, opt in enumerate(admin_state["data"]["current_options"]):
                correct_indicator = " ✅" if i == admin_state["data"]["current_correct"] else ""
                text += f"{chr(65+i)}. {opt}{correct_indicator}\n"
            
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("📝 Question Text", callback_data="edit_question_text"))
            keyboard.add(types.InlineKeyboardButton("🔤 Options", callback_data="edit_question_options"))
            keyboard.add(types.InlineKeyboardButton("✅ Correct Answer", callback_data="edit_question_correct"))
            keyboard.add(types.InlineKeyboardButton("💾 Save All Changes", callback_data="edit_question_save"))
            keyboard.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_edit_question"))
            
            msg = bot.send_message(
                message.chat.id,
                text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            schedule_auto_delete(message.chat.id, msg.message_id)
            clear_admin_state(message.from_user.id)
        
        elif step == "edit_options":
            option_index = admin_state["data"].get("current_option_index", 0)
            admin_state["data"]["current_options"][option_index] = message.text
            option_index += 1
            
            if option_index < 4:
                admin_state["data"]["current_option_index"] = option_index
                option_letter = chr(65 + option_index)
                
                text = f"✅ <b>Option {chr(65 + option_index - 1)} updated!</b>\n\n"
                text += f"Now send the new text for <b>Option {option_letter}</b>:"
                
                msg = bot.send_message(
                    message.chat.id,
                    text,
                    parse_mode='HTML'
                )
                schedule_auto_delete(message.chat.id, msg.message_id)
                bot.register_next_step_handler(msg, handle_edit_question_flow, admin_state)
            else:
                # All options updated
                question_index = admin_state["data"]["question_index"]
                text = f"✅ <b>All Options Updated</b>\n\n"
                text += f"<b>Question {question_index + 1}:</b>\n{admin_state['data']['current_question']}\n\n"
                text += f"<b>Options:</b>\n"
                for i, opt in enumerate(admin_state["data"]["current_options"]):
                    correct_indicator = " ✅" if i == admin_state["data"]["current_correct"] else ""
                    text += f"{chr(65+i)}. {opt}{correct_indicator}\n"
                
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("📝 Question Text", callback_data="edit_question_text"))
                keyboard.add(types.InlineKeyboardButton("🔤 Options", callback_data="edit_question_options"))
                keyboard.add(types.InlineKeyboardButton("✅ Correct Answer", callback_data="edit_question_correct"))
                keyboard.add(types.InlineKeyboardButton("💾 Save All Changes", callback_data="edit_question_save"))
                keyboard.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_edit_question"))
                
                msg = bot.send_message(
                    message.chat.id,
                    text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                schedule_auto_delete(message.chat.id, msg.message_id)
                clear_admin_state(message.from_user.id)
    except Exception as e:
        print(f"Error in edit question flow: {e}")
        msg = bot.send_message(message.chat.id, "❌ Error editing question")
        schedule_auto_delete(message.chat.id, msg.message_id)
        clear_admin_state(message.from_user.id)

def handle_set_time(message, admin_state):
    """Handle setting question time"""
    try:
        # Delete the user's input message
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        
        new_time = int(message.text)
        if 5 <= new_time <= 60:
            CONFIG["QUESTION_TIME"] = new_time
            
            # Save to questions file
            questions = load_questions()
            save_questions(questions, new_time)
            
            msg = bot.send_message(
                message.chat.id,
                f"✅ <b>Question time updated to {new_time} seconds!</b>",
                parse_mode='HTML'
            )
            schedule_auto_delete(message.chat.id, msg.message_id)
        else:
            msg = bot.send_message(
                message.chat.id,
                "❌ Please enter a number between 5 and 60 seconds."
            )
            schedule_auto_delete(message.chat.id, msg.message_id)
    except ValueError:
        msg = bot.send_message(
            message.chat.id,
            "❌ Please enter a valid number."
        )
        schedule_auto_delete(message.chat.id, msg.message_id)
    
    clear_admin_state(message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("add_correct_"))
def handle_add_correct(call):
    """Handle setting correct answer for new question"""
    try:
        correct_index = int(call.data.split("_")[2])
        admin_state = get_admin_state(call.from_user.id)
        admin_state["last_activity"] = time.time()
        
        # Create new question
        new_question = Question(
            q=admin_state["data"]["question"],
            opts=admin_state["data"]["options"],
            correct_index=correct_index
        )
        
        # Load current questions and append new one
        questions = load_questions()
        questions.append(new_question)
        
        # Save questions
        if save_questions(questions):
            bot.edit_message_text(
                f"✅ <b>New question added successfully!</b>\n\n"
                f"Total questions: {len(questions)}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        else:
            bot.edit_message_text(
                "❌ <b>Error saving question!</b>",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        
        clear_admin_state(call.from_user.id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Error adding correct answer: {e}")
        bot.answer_callback_query(call.id, "❌ Error adding question")

# === MAIN ===
if __name__ == "__main__":
    print("🤖 TMZ BRAND Quiz Bot Started!")
    print("📊 Features: One-time quiz, Admin panel, Edit questions, Leaderboard")
    print("⚡ Instant mode: Questions advance when all participants answer")
    print("🗑️ Auto-delete: All messages vanish after 30s, start message after 5min")
    print("🔧 Enhanced state management with comprehensive clearing")
    
    # Ensure data files exist
    for file in [CONFIG["QUESTIONS_FILE"], CONFIG["PARTICIPANTS_FILE"], CONFIG["QUIZ_COMPLETION_FILE"]]:
        try:
            with open(file, 'a+', encoding='utf-8') as f:
                pass
        except Exception as e:
            print(f"Error creating file {file}: {e}")
    
    # Start periodic cleanup thread
    def periodic_cleanup():
        while True:
            time.sleep(3600)  # Run every hour
            cleanup_old_admin_states()
            print("🕒 Periodic cleanup completed")
    
    cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
    cleanup_thread.start()
    
    # Start bot in a background thread
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    
    # Run small web server so Render detects an open port
    port = int(os.environ.get("PORT", 10000))
    print(f"🌍 Starting Flask web server on port {port}")
    app.run(host="0.0.0.0", port=port)