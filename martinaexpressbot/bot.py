import os
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters, PicklePersistence
from dotenv import load_dotenv

# Configurazione: Carica il token dal file .env
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ID del FrontMan per poter gestire il gioco da admin
ADMIN_USER_ID = 897104160

# Lista delle coppie
LISTA_COPPIE = [
    "Le OG",
    "I depressi",
    "Le queen",
    "Gli innamorati",
]

# Mappa per i percorsi delle immagini.
STAGE_IMAGES = {
    1: "/home/enrico/Desktop/MartinaExpress/MartinaExpress - Mappa 1.png", # Mappa iniziale
    2: "/home/enrico/Desktop/MartinaExpress/MartinaExpress - Mappa 2.png", # Mappa per la seconda tappa
    3: "/home/enrico/Desktop/MartinaExpress/MartinaExpress - Mappa 3.png", # Mappa per la quarta e ultima tappa
}
MAX_STAGE = 4

# Configura il logging per vedere gli output nel terminale
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Funzione helper per accedere in modo sicuro allo stato persistente
def get_couple_stages(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Restituisce il dizionario dello stato delle coppie (COUPLE_STAGES) dal bot_data, inizializzandolo se mancante."""
    if 'COUPLE_STAGES' not in context.bot_data:
        context.bot_data['COUPLE_STAGES'] = {}
    return context.bot_data['COUPLE_STAGES']

# Funzioni Handler: Definizione delle azioni del bot

# Funzione che risponde al comando /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia un messaggio di benvenuto quando viene emesso il comando /start."""
    user_name = update.effective_user.first_name if update.effective_user else "Utente"
    await update.message.reply_text(f'Ciao {user_name}! Sono il tuo nuovo bot.')

# Funzione che risponde al comando /aiuto
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia un messaggio di aiuto quando viene emesso il comando /aiuto."""
    await update.message.reply_text('Sono qui per aiutarti! Comandi disponibili:\n'
        '/setcoppia - Seleziona o resetta la coppia\n'
        '/stradeammesse - Mostra la mappa per la tua tappa attuale\n'
        '/scopettonero - Ricevi una penitenza (se necessario)'
    )

# Funzione che permette di selezionare la coppia
async def setcoppia_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia il menu con i pulsanti per selezionare la coppia."""
    
    keyboard_buttons = []
    
    for nome_coppia in LISTA_COPPIE:
        callback_data = f"SET_{nome_coppia}"
        
        # Aggiungi il pulsante alla lista
        keyboard_buttons.append(
            InlineKeyboardButton(nome_coppia, callback_data=callback_data)
        )
    
    # Organizza i pulsanti in 2 colonne (più compatto)
    rows = [keyboard_buttons[i:i + 2] for i in range(0, len(keyboard_buttons), 2)]
    
    reply_markup = InlineKeyboardMarkup(rows)

    await update.message.reply_text(
        'Seleziona la tua coppia dall\'elenco:',
        reply_markup=reply_markup
    )

# Funzione che gestisce la selezione della coppia
async def handle_couple_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce la selezione della coppia tramite pulsante inline."""
    
    query = update.callback_query
    chat_id = update.effective_chat.id
    data = query.data
    
    # Rispondi subito alla query per eliminare l'icona di caricamento
    await query.answer()

    # Controlla il prefisso 'SET_'
    if data.startswith("SET_"):
        
        # Estrai il nome della coppia
        selected_couple_name = data.replace("SET_", "")
        
        # OTTIENI LO STATO PERSISTENTE
        couple_stages = get_couple_stages(context)
        
        # Registra lo stato nel bot_data persistente
        couple_stages[chat_id] = {'nome': selected_couple_name, 'tappa': 1}
        
        # Modifica il messaggio originale per confermare
        await query.edit_message_text(
            text=f"✅ Coppia {selected_couple_name} registrata con successo! Dovete raggiungere la Tappa 1.\n"
                 f"Ora potete usare il comando /stradeammesse per vedere la mappa."
        )  

# Funzione che risponde al comando /scopettonero
async def scopettonero_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia una delle penitenze quando viene emesso il comando /scopettonero."""
    penlist = {
        "1": "Fai 10 flessioni.",
        "2": "Canta una canzone a caso.",
        "3": "Racconta una barzelletta.",
        "4": "Fai una danza strana."
    }
    penitenza = random.choice(list(penlist.values()))
    await update.message.reply_text(f'Qualcuno è stato beccato eh? Beh, ora tocca la penitenza: {penitenza}')

# Funzione che invia le strade ammesse
async def stradeammesse_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    
    # Ottieni lo stato persistente
    couple_stages = get_couple_stages(context)

    # Controllo preliminare: la coppia è registrata?
    if chat_id not in couple_stages:
        await update.message.reply_text(
            "Prima devi registrare la tua coppia! Per farlo, usa il comando /setcoppia [NomeCoppia]."
        )
        return

    # Recupero dello stato della coppia
    current_stage = couple_stages[chat_id]['tappa']
    couple_name = couple_stages[chat_id]['nome']
    
    # Determinazione del percorso dell'immagine
    if current_stage not in STAGE_IMAGES:
        await update.message.reply_text(
            f"Errore: Tappa {current_stage} non mappata. Contatta l'admin."
        )
        return
    
    image_path = STAGE_IMAGES[current_stage]
    
    # Invio dell'immagine
    try:
        # Apri il file in modalità binaria (richiesta da send_photo)
        with open(image_path, 'rb') as photo_file:
            await update.message.reply_photo(
                photo=photo_file,
                caption=f"🛣️ Strade ammesse per raggiungere la Tappa {current_stage}."
            )
            
    except FileNotFoundError:
        await update.message.reply_text(
            f"Errore: Immagine non trovata al percorso: {image_path}. Assicurati che il file esista sul server."
        )
    except Exception as e:
        await update.message.reply_text(f"Si è verificato un errore durante l'invio della foto: {e}")

# Funzione che permette all'admin di impostare alcuni parametri manualmente
async def avanzatappa_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando ADMIN: Avanza la tappa di una coppia specifica."""
    
    # Controllo di sicurezza: solo l'admin può eseguire questo comando
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("Non sei autorizzato a usare questo comando.")
        return
    
    # Ottieni lo stato persistente
    couple_stages = get_couple_stages(context)

    # Mappatura inversa per trovare velocemente l'ID chat di una coppia registrata
    registered_names_to_id = {data['nome']: chat_id for chat_id, data in couple_stages.items()}

    keyboard_buttons = []
    
    # Prepara i pulsanti solo per le coppie registrate
    for nome_coppia in LISTA_COPPIE:
        
        # Cerca l'ID della chat (se esiste) usando il nome come chiave
        chat_id = registered_names_to_id.get(nome_coppia)
        
        if chat_id:
            # Coppia registrata: usa l'ID chat per l'avanzamento
            tappa_attuale = couple_stages[chat_id]['tappa']
            callback_data = f"ADVANCE_{chat_id}"
        else:
            # Coppia NON registrata: usa il nome e mostra Tappa 0
            tappa_attuale = 0
            # Usiamo un prefisso speciale per le coppie non registrate
            callback_data = f"ADVANCE_UNREG_{nome_coppia}"
        
        # Aggiungi il pulsante mostrando la tappa attuale
        button_text = f"{nome_coppia} (Tappa {tappa_attuale})"
        keyboard_buttons.append(
            InlineKeyboardButton(button_text, callback_data=callback_data)
        )
    
    # Organizza i pulsanti in 1 colonna (più leggibile per l'admin)
    rows = [[btn] for btn in keyboard_buttons]
    reply_markup = InlineKeyboardMarkup(rows)

    await update.message.reply_text(
        'Clicca sulla coppia che deve avanzare di +1 tappa:',
        reply_markup=reply_markup
    )

async def handle_advance_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce la callback query dall'admin per avanzare la tappa di una coppia."""
    query = update.callback_query
    data = query.data
    
    # Controllo di sicurezza aggiuntivo per le callback
    if update.effective_user.id != ADMIN_USER_ID:
        await query.answer("Non sei autorizzato a eseguire questo comando.", show_alert=True)
        return
    
    await query.answer()

    # Ottieni lo stato persistente
    couple_stages = get_couple_stages(context)    

    if data.startswith("ADVANCE_UNREG"):
        target_name = data.replace("ADVANCE_UNREG_", "")

        await query.edit_message_text(
            f"⚠️ **{target_name}** non è ancora registrata (Tappa 0).\n"
            f"Non posso avanzarla perché non so a quale chat inviare la notifica di Tappa 1. \n"
            f"Chiedi alla coppia di registrarsi (/setcoppia), poi riprova."
        )
        return

    if data.startswith("ADVANCE_"):

        # Estrai l'ID della chat della coppia (il target)
        try:
            target_chat_id = int(data.replace("ADVANCE_", ""))
        except ValueError:
            await query.edit_message_text("Errore nell'identificazione della coppia.")
            return

        if target_chat_id not in couple_stages:
            await query.edit_message_text("Coppia non trovata nello stato globale.")
            return

        # Logica di avanzamento
        target_name = couple_stages[target_chat_id]['nome']
        current_stage = couple_stages[target_chat_id]['tappa']
        
        new_stage = current_stage + 1
        
        if new_stage > MAX_STAGE:
             await query.edit_message_text(f"La coppia '{target_name}' ha già raggiunto la tappa finale ({MAX_STAGE}). Impossibile avanzare.")
             return

        # Aggiorna lo stato
        couple_stages[target_chat_id]['tappa'] = new_stage
                
        # Notifica l'admin modificando il menu originale
        await query.edit_message_text(
            f"✅ Coppia '{target_name}' avanzata alla Tappa {new_stage}."
            f"\n(Utilizza nuovamente il comando /avanzatappa per il menu aggiornato.)"
        )
        
        # Manda un messaggio alla coppia (notifica)
        try:
            await context.bot.send_message(
                chat_id=target_chat_id,
                text=f"🎉 Complimenti! Avete superato la prova {new_stage-1}! Siete stati promossi alla Tappa {new_stage}."
                     f" Usate il comando /stradeammesse per vedere la nuova mappa di strade disponibili."
            )
        except Exception as e:
            # Manda un errore all'admin (nella chat admin) se la notifica fallisce
            logging.error(f"Errore nella notifica alla coppia {target_name}: {e}")

# Funzione che risponde a qualsiasi altro testo
async def echo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ripete il messaggio ricevuto."""
    if update.message and update.message.text:
        await update.message.reply_text(f"Non ho capito. Usa /help per vedere i comandi disponibili.")

# Funzione Principale: Avvio del Bot
def main() -> None:
    """Avvia il bot."""

    # Configura la persistenza: i dati saranno salvati in game_state.pkl
    persistence = PicklePersistence(filepath='game_state.pkl')

    # Crea l'oggetto Application e passagli il token
    application = Application.builder().token(TOKEN).build()

    # Registra gli handler: associa i comandi alle funzioni
    # HANDLER PUBBLICI
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("setcoppia", setcoppia_command))
    application.add_handler(CommandHandler("stradeammesse", stradeammesse_command))  
    application.add_handler(CommandHandler("scopettonero", scopettonero_command))

    # HANDLER AMMINISTRATIVI (Comando che genera il menu)
    application.add_handler(CommandHandler("avanzatappa", avanzatappa_command))

    # HANDLER INLINE E MESSAGGI
    application.add_handler(CallbackQueryHandler(handle_couple_selection, pattern=r'^SET_'))
    # NUOVO HANDLER PER L'AVANZAMENTO ADMIN
    application.add_handler(CallbackQueryHandler(handle_advance_selection, pattern=r'^ADVANCE'))
   
    # FALLBACK/ECHO
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_command))
    application.run_polling(poll_interval=3)
    
    # Avvia il polling (il bot controlla Telegram per nuovi messaggi)
    application.run_polling(poll_interval=3)

if __name__ == "__main__":
    main()