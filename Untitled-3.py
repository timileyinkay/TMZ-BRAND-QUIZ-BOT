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
            # Auto-delete countdown message
            schedule_auto_delete(chat_id, countdown_msg.message_id)
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