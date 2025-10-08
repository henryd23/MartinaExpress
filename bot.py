import os
import logging
import random
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters, PicklePersistence
from dotenv import load_dotenv


# --- CONFIGURAZIONE GLOBALE ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") # Configurazione: Carica il token dal file .env
ADMIN_USER_ID = 897104160 # ID del FrontMan per poter gestire il gioco da admin
MAX_STAGE = 4 # Massimo numero di tappe
CODE_COMPOSER = "code_composer" # Costante per identificare i dati del keypad in user_data

# Configura il logging per vedere gli output nel terminale
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)

# Variabili globali per l'applicazione e l'URL
APPLICATION = None
WEBHOOK_PATH = f"/{TOKEN}" 
BASE_URL = "https://3d1bb39e-4b2c-42cc-a24f-86eada95a4f8-00-30gb5cr2v96jh.kirk.replit.dev"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH
PORT = 8080 # Porta su cui Gunicorn/Flask ascolta


# Lista delle coppie
LISTA_COPPIE = [
    "Le OG",
    "The Sicilians",
    "Il lungo, il corto e il pacioccone",
]

# Lista codici di sblocco tappe
DISCOVERY_CODES = {
    1: "7834", # Codice per sbloccare testo Tappa 1
    2: "0396", # Codice per sbloccare testo Tappa 2
    3: "3478", # Codice per sbloccare testo Tappa 3
}

# Lista codici di sblocco tappe
ADVANCEMENT_CODES = {
    1: "2140", # Codice per sbloccare Tappa 2
    2: "1989", # Codice per sbloccare Tappa 3
    3: "1007", # Codice per sbloccare Tappa 4 (Finale)
}

# PROVE E TESTI 
# La chiave è la tappa a cui si riferisce la prova.
PROOFS_DATA = {
    1: {
        "name": "Prova 1: Sfida i tuoi sensi",
        "text": "Benvenuti alla prova della prima tappa! Recatevi dal frontman per ricevere "
        "ulteriori informazioni e scoprire in cosa consiste.",
    },
    2: {
        "name": "Prova 2: Un signore italiano",
        "text": "Siete arrivati alla Chiesa di Sant'Agostino? Bene, ora dovrete trovare una busta "
        "contenente delle lettere, dovrete comporle nel modo corretto e scoprire il codice per "
        "passare alla prossima tappa.",
    },
    3: {
        "name": "Prova 3: Quasi Amici",
        "text": "Ben fatto, siete alla terza tappa! Qui dovrete coordinarvi bene, nonostante uno dei "
        "due avrà un'evidente disabilità: fermatevi qui dove avete trovato il codice di accesso e "
        "scegliete chi dei due dovrà bendarsi usando la propria fascia e chi gli darà le indicazioni. "
        "Ci sono due stemmi di Martina Express nascosti nei paraggi: prima, quello sbendato dovrà "
        "andare in cerca di questi due stemmi mentre il bendato rimane fermo qui, senza sbirciare. "
        "Una volta trovati, tornerà dal suo amico bendato e dovrà guidarlo dando indicazioni come "
        "'Cinque passi avanti, due a destra' per fargli raggiungere gli oggetti, pur mantenendo "
        "una distanza considerevole di almeno una decina di metri.\n"
        "Lo scopo della prova è infatti che il bendato trovi gli oggetti solo tramite indicazioni "
        "precise, non facendosi guidare in modo troppo esplicito da un compagno che lo segue come "
        "un'ombra.\n"
        "La benda non potrà essere tolta finché non saranno stati trovati entrambi gli oggetti.",
    },
    4: {
        "name": "Prova 4: Il Castello di Sigismondo (Finale)",
        "text": "La prova finale! Raggiungete Castel Sismondo e trovate l'incisione con lo stemma della famiglia Malatesta. Disegnatelo su un pezzo di carta e inviate la foto al Frontman. Se il disegno è accurato, avete vinto!",
    },
}

# Struttura: {NUMERO_TAPPA: [ {NOME_INDIZIO, PERCORSI_IMMAGINI} ]}
HINTS_DATA = {
    # Tappa 1 (Da raggiungere): mostra Indizi per Tappa 1
    0: [ 
        {
            "name": "Tempio Malatestiano",
            "image1": "hints/Indizio 1/temple-run-game.jpg", 
            "image2": "hints/Indizio 1/Professor_X's_Mind_Rays.jpg", 
            "image3": "hints/Indizio 1/ano.jpg",
        },
    ],
    # Tappa 2 (Da raggiungere): mostra Indizi per Tappa 2
    1: [
        {
            "name": "Chiesa di Sant'Agostino",
            "image1": "hints/Indizio 2/federicochiesa.jpg", 
            "image2": "hints/Indizio 2/gigidag.jpg", 
        },
    ],
    # Tappa 3 (Da raggiungere): Mostra Indizi Tappa 2
    2: [
        {
            "name": "Domus del chirurgo",
            "image1": "hints/Indizio 3/Doctor-Strange.jpg", 
            "image2": "hints/Indizio 3/Dr.-House-Medical-Division.jpg", 
        },
    ],
    # Tappa 4 (Da raggiungere): Mostra Indizi Tappa 3 (Finali)
    3: [
        {
            "name": "Castel Sismondo",
            "image1": "hints/Indizio 4/logo-disney-anno-1985-blu.jpg", 
            "image2": "hints/Indizio 4/rondodasosa.jpeg", 
            "image3": "hints/Indizio 4/earthquakemove.png", 
        },
    ],
}

# Chiave per memorizzare lo stato (per la fase di inserimento codice)
# Contiene: {'action': 'DISCOVER'/'ADVANCE', 'target_stage': 1/2/3...}
WAITING_FOR_CODE = "WAITING_FOR_CODE"


# Funzione helper per accedere in modo sicuro allo stato persistente
def get_couple_stages(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Restituisce il dizionario dello stato delle coppie (COUPLE_STAGES) dal bot_data, inizializzandolo se mancante."""
    if 'COUPLE_STAGES' not in context.bot_data:
        context.bot_data['COUPLE_STAGES'] = {}
    return context.bot_data['COUPLE_STAGES']

# Funzione helper per verificare se la coppia è registrata
async def check_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Controlla se la chat è registrata e avvisa in caso negativo."""
    chat_id = update.effective_chat.id
    couple_stages = get_couple_stages(context)
    
    if chat_id not in couple_stages:
        await update.message.reply_text(
            "⚠️ Prima devi registrare la tua coppia! Usa il comando /setcoppia."
        )
        return False
    return True
 
# FUNZIONI HANDLER: Definizione delle azioni del bot
# Funzione che risponde al comando /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia un messaggio di benvenuto quando viene emesso il comando /start."""
    user_name = update.effective_user.first_name if update.effective_user else "Utente"
    await update.message.reply_text(f"Ciao {user_name}! Sono il tuo nuovo bot "
                                     "e sarò il tuo assistente nel corso di Martina Express!")

# Funzione che risponde al comando /aiuto
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia un messaggio di aiuto quando viene emesso il comando /aiuto."""
    await update.message.reply_text("Sono qui per aiutarti! Comandi disponibili:\n"
        "/setcoppia - Seleziona o resetta la coppia\n"
        "/stradeammesse - Mostra la mappa per la tua tappa attuale\n"
        "/indizio - Mostra gli indizi della prossima tappa e delle precedenti\n"
        "/tentaprova - Sblocca il testo della prova (richiede un codice)\n"
        "/superaprova - Avanza alla tappa successiva (richiede un codice)\n"
        "/scopettonero - Ricevi una penitenza (se necessario)"
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
        "Seleziona la tua coppia dall\'elenco:",
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
                  "Ora potete usare il comando /stradeammesse per vedere la mappa e "
                  "il comando /indizio per vedere gli indizi della prossima tappa e delle precedenti."
                  "Per sbloccare il testo della prova, usate /tentaprova."
        )  

# Funzione che risponde al comando /scopettonero
async def scopettonero_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia una delle penitenze quando viene emesso il comando /scopettonero."""
    penlist = {
        "1": "Romagna Mia in Napoletano",
        "2": "Romagna Mia in Barese",
        "3": "Romagna Mia in Toscano",
        "4": "Romagna Mia in Veneto"
    }
    penitenza = random.choice(list(penlist.values()))
    await update.message.reply_text("Qualcuno è stato beccato eh? Beh, ora vi tocca la penitenza: "
                                    f"dovrete imparare a memoria una strofa di {penitenza}.\n"
                                    "La sfida prevede che vi registriate, appoggiando il telefono da qualche parte, "
                                    "e mandiate il video ad Enrico che valuterà se sarà o meno sufficiente. "
                                    "In caso di esito positivo potrete proseguire, altrimenti dovrete rifarlo. "
                                    "Ma ora, ecco la strofa che dovrete imparare:\n"
    )
    if penitenza=="Romagna Mia in Napoletano":
        await update.message.reply_text("Sento 'a malincunia 'e nu passato\n"
                                        "Addò mammarella mia aggio lassato\n"
                                        "Nun te pozzo scurdà, casarella mia\n"
                                        "Int'a sta nuttata chiena 'e stelle\n"
                                        "A serenata mia 'a canto pe' te.\n"
                                        "Terra mia, Terra 'e passione\n"
                                        "Tu si' 'a stella, tu si' 'o core\n"
                                        "Quanno te penzo, vulesse turnà\n"
                                        "D'a bella mia, 'a dinto 'o casale.\n"
                                        "Napule, Napule mia,\n"
                                        "Luntano a te nun se po' sta'!\n"
        )
    elif penitenza=="Romagna Mia in Barese":
        await update.message.reply_text("Sènde 'a malencunì d'nu passàte\n"
                                        "Addò la màme mèje agg' lassàte\n"
                                        "Nun t' pozze scurdà, casarelle mèje\n"
                                        "Mbrèsce a sta nòtte chièna de stélle\n"
                                        "La serenàte mèje a cante p'a tté.\n"
                                        "Tèrre mèje, Tèrre ch'a fiurìsce\n"
                                        "Tu si' la stélle, tu si' l'amòre\n"
                                        "Quanne t' pènze, vulèsse turnà\n"
                                        "D'a zite mèje a dìnne 'u casàle.\n"
                                        "Bàre, Bàre mèje,\n"
                                        "Luntàne a tté nu s' po' stà.\n"
        )
    elif penitenza=="Romagna Mia in Toscano":
        await update.message.reply_text("Sento la malìa d'un passato andato\n"
                                        "Dóve la mì mamma l'ho lasciata\n"
                                        "Un ti potrò scordare, casetta bòna\n"
                                        "In codesta notte piena di stelle\n"
                                        "La mìa serenata la canto per te.\n"
                                        "Terra mìa, Terra ch'è in fiore\n"
                                        "Tu se' la stella, tu se' l'amore\n"
                                        "Quande ti penso, vorrei tornà\n"
                                        "Dalla mìa bella, al casalare.\n"
                                        "Terra, Terra mìa,\n"
                                        "Lontano da te 'un si può stare!\n"
    )
    elif penitenza=="Romagna Mia in Veneto":
        await update.message.reply_text("Sento la nostalìa de 'n passà\n"
                                        "Doe che la mama me go lassà\n"
                                        "No te poderò scordar, caxéta mia\n"
                                        "In sta nòte piena de stéle\n"
                                        "La serenata me la canto par ti.\n"
                                        "Tera me, Tera 'n fiore\n"
                                        "Ti te sì la stéla, ti te sì l'amore\n"
                                        "Co te pènso, vorìa tornar\n"
                                        "Dala me bèla al casolàr.\n"
                                        "Tera, Tera me,\n"
                                        "Lontan da ti no se pol star!\n"
        )

# Funzione che invia le strade ammesse
async def stradeammesse_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    image_path = "MartinaExpress - Mappa.png"

    # Invio dell'immagine
    try:
        # Apri il file in modalità binaria (richiesta da send_photo)
        with open(image_path, 'rb') as photo_file:
            await update.message.reply_photo(
                photo=photo_file,
                caption=f"🛣️ Ecco le strade ammesse durante il gioco.\n"
                "Ricordate, non tutte le tappe saranno necessariamente lungo le strade indicate, "
                "bensì potrebbero essere nei dintorni. In tal caso, potrete arrivarci soltanto "
                "tramite 'prolungamenti' delle strade già ammesse.\nBuon divertimento!"
            )
            
    except FileNotFoundError:
        await update.message.reply_text(
            f"Errore: Immagine non trovata al percorso: {image_path}. Assicurati che il file esista sul server."
        )
    except Exception as e:
        await update.message.reply_text(f"Si è verificato un errore durante l'invio della foto: {e}")

# Funzione che permette alle coppie di vedere gli indizi
async def indizio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra i pulsanti per tutti gli indizi disponibili (dalle tappe precedenti fino a quella corrente)."""
    chat_id = update.effective_chat.id
    couple_stages = get_couple_stages(context)
    
    if chat_id not in couple_stages:
        await update.message.reply_text("Prima devi registrare la tua coppia! Usa il comando /setcoppia.")
        return

    # La coppia è alla Tappa X, gli indizi disponibili sono per le tappe da 0 a X-1.
    current_stage_to_reach = couple_stages[chat_id]['tappa']
    
    # Determina l'ultima chiave di indizi disponibile (es. se tappa è 3, l'ultima chiave è 2)
    max_hint_key = current_stage_to_reach - 1 

    keyboard_buttons = []
    available_hints_found = False
    
    # Itera su tutte le tappe superate (dalla Tappa 0 fino a max_hint_key)
    # Tappe superate: 0, 1, 2, ...
    for hints_available_key in range(max_hint_key + 1):
        
        # Controlla se esistono dati per quella chiave di tappa in HINTS_DATA
        if hints_available_key in HINTS_DATA and HINTS_DATA[hints_available_key]:
            
            available_hints = HINTS_DATA[hints_available_key]
            available_hints_found = True
            
            # Se la chiave è l'ultima disponibile, significa che è l'indizio per la prossima tappa.
            is_current_target_hint = (hints_available_key == max_hint_key)

            # Itera sugli indizi all'interno di quella tappa
            for index, hint_data in enumerate(available_hints):
                # La callback data DEVE includere la chiave della tappa e l'indice dell'indizio
                callback_data = f"HINT_{hints_available_key}_{index}"
                tappa_display = hints_available_key + 1

                if is_current_target_hint:
                    # Se è l'indizio per la tappa successiva (ancora da completare)
                    button_text = f"Tappa {tappa_display}" 
                else:
                    # Se è un indizio di tappe precedenti (già completate, per rivederle)
                    button_text = f"Tappa {tappa_display}: {hint_data['name']}"
                
                # Aggiunge il pulsante alla lista
                keyboard_buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    if not available_hints_found:
        await update.message.reply_text("Non ci sono indizi disponibili in questo momento del gioco.")
        return

    # Organizza i pulsanti (è già una lista di liste grazie a come li abbiamo aggiunti sopra)
    reply_markup = InlineKeyboardMarkup(keyboard_buttons)

    await update.message.reply_text(
        "🔎 Seleziona l'indizio che vuoi visualizzare:",
        reply_markup=reply_markup
    )

async def handle_hint_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce la selezione dell'indizio e invia tutte le immagini collegate."""
    query = update.callback_query
    data = query.data
    chat_id = query.message.chat_id
    
    await query.answer()

    if data.startswith("HINT_"):
        parts = data.split('_')
        hints_available_key = int(parts[1]) # Tappa superata
        hint_index = int(parts[2])          # Indice dell'indizio
        
        try:
            hint_data = HINTS_DATA[hints_available_key][hint_index]
            hint_name = hint_data['name']
        except (KeyError, IndexError):
            await query.edit_message_text("Errore: Indizio non trovato. Contatta l'admin.")
            return

        await query.edit_message_text(f"Sto inviando gli indizi per la prossima tappa...")

        # Trova e invia tutte le immagini (image1, image2, image3, ...)
        image_count = 0
        
        # Ordiniamo le chiavi per garantire che image1 sia inviata prima di image2, ecc.
        image_keys = sorted([k for k in hint_data.keys() if k.startswith('image')])

        for key in image_keys:
            image_path = hint_data[key]
            
            try:
                with open(image_path, 'rb') as photo_file:
                     await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo_file,
                        caption=f"Indizio: Immagine {image_count + 1}"
                    )
                image_count += 1
                
            except FileNotFoundError:
                 await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Attenzione: Immagine '{image_path}' per l'indizio '{image_count + 1}' non trovata. Controlla il nome file."
                )
            except Exception as e:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"Si è verificato un errore durante l'invio della foto {image_path}: {e}"
                )

        if image_count == 0:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Nessuna immagine trovata per l'indizio: {hint_name}."
            )
        else:
            # Opzionale: Modifica l'ultimo messaggio per confermare
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Invio completato. Totale {image_count} indizi inviati."
            )


# --- GESTIONE DELLE PROVE E DEI DUE CODICI ---
# Funzione per tentare di sbloccare la prova (richiede il primo codice)
async def tentaprova_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Richiede il primo codice (DISCOVERY) per sbloccare la prova, usando il keypad."""
    if not await check_registration(update, context):
        return

    chat_id = update.effective_chat.id
    couple_stages = get_couple_stages(context)
    current_stage = couple_stages[chat_id]['tappa']
    couple_name = couple_stages[chat_id]['nome']
    
    if current_stage > MAX_STAGE:
        await update.message.reply_text("Hai già completato tutte le tappe!")
        return

    # Controlla se la prova è già stata sbloccata
    if couple_stages[chat_id].get('prova_sbloccata', False):
         await update.message.reply_text(
            f"La Prova {current_stage} è già stata sbloccata.\n"
            "Ora devi solo superarla! Quando avrai il codice finale, usa /superaprova."
        )
         return
    
    # Invia la tastiera per comporre il Codice 1
    await send_keypad(update, context, couple_stages, chat_id, 'DISCOVER_PROOF')


async def superaprova_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Richiede il secondo codice (ADVANCEMENT) per avanzare, usando il keypad."""
    if not await check_registration(update, context):
        return
        
    chat_id = update.effective_chat.id
    couple_stages = get_couple_stages(context)
    current_stage = couple_stages[chat_id]['tappa']
    
    if current_stage > MAX_STAGE:
        await update.message.reply_text("Complimenti! Hai completato tutte le tappe.")
        return
        
    # CONTROLLO RICHIESTO: Se la prova attuale NON è stata sbloccata
    if not couple_stages[chat_id].get('prova_sbloccata', False):
         await update.message.reply_text(
            f"Devi prima sbloccare e leggere il testo della Prova {current_stage} usando /tentaprova."
        )
         return

    # La tappa da superare è la tappa attuale
    await send_keypad(update, context, couple_stages, chat_id, 'ADVANCE_WITH_CODE')

def generate_keypad(current_code: str, is_final: bool) -> InlineKeyboardMarkup:
    """Genera la tastiera inline per comporre il codice a 4 cifre."""
    keyboard = []
    
    # Riga 1: 1, 2, 3
    keyboard.append([
        InlineKeyboardButton("1", callback_data=f"CODE_KEY_1"),
        InlineKeyboardButton("2", callback_data=f"CODE_KEY_2"),
        InlineKeyboardButton("3", callback_data=f"CODE_KEY_3"),
    ])
    # Riga 2: 4, 5, 6
    keyboard.append([
        InlineKeyboardButton("4", callback_data=f"CODE_KEY_4"),
        InlineKeyboardButton("5", callback_data=f"CODE_KEY_5"),
        InlineKeyboardButton("6", callback_data=f"CODE_KEY_6"),
    ])
    # Riga 3: 7, 8, 9
    keyboard.append([
        InlineKeyboardButton("7", callback_data=f"CODE_KEY_7"),
        InlineKeyboardButton("8", callback_data=f"CODE_KEY_8"),
        InlineKeyboardButton("9", callback_data=f"CODE_KEY_9"),
    ])
    
    # Riga 4: Indietro, 0, Operazione Finale
    final_row = [
        InlineKeyboardButton("↩️ Indietro", callback_data="CODE_KEY_BACK"),
        InlineKeyboardButton("0", callback_data="CODE_KEY_0"),
    ]
    
    if is_final:
        # Se siamo alla 4a cifra (indice 3), il tasto finale è CONFERMA
        final_row.append(InlineKeyboardButton("✅ CONFERMA", callback_data="CODE_KEY_CONFIRM"))
    else:
        # Altrimenti è AVANTI
        final_row.append(InlineKeyboardButton("➡️ Avanti", callback_data="CODE_KEY_FORWARD"))
        
    keyboard.append(final_row)
    
    return InlineKeyboardMarkup(keyboard)

async def send_keypad(update: Update, context: ContextTypes.DEFAULT_TYPE, couple_stages: dict, chat_id: int, action_type: str) -> None:
    """Funzione per inviare o aggiornare la tastiera del codice."""
    
    couple_name = couple_stages[chat_id]['nome']
    
    # Inizializza o recupera lo stato del compositore
    if CODE_COMPOSER not in context.user_data or context.user_data[CODE_COMPOSER].get('chat_id') != chat_id:
        context.user_data[CODE_COMPOSER] = {
            'code': "", 
            'action': action_type, 
            'target_stage': couple_stages[chat_id]['tappa'],
            'chat_id': chat_id
        }
    
    composer_state = context.user_data[CODE_COMPOSER]
    current_code = composer_state['code']
    current_stage = composer_state['target_stage']
    code_length = len(current_code)
    
    action_text = "SBLOCCARE LA PROVA (Codice 1)" if action_type == 'DISCOVER_PROOF' else "SUPERARE LA PROVA (Codice 2)"

    title = (
        f"{couple_name} - Tappa {current_stage}\n"
        f"Componi il codice a 4 cifre per {action_text}."
    )
    
    # Visualizzazione del codice composto
    code_display = "".join([f"{c}" for c in current_code]) 
    placeholders = " _ " * (4 - code_length)
    display_message = f"{title}\n\nCodice attuale: {code_display}{placeholders}"
    
    is_final = code_length == 4

    reply_markup = generate_keypad(current_code, is_final)
    
    # Se è una CallbackQuery, modifichiamo il messaggio esistente
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=display_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    # Se è un CommandHandler (prima richiesta), inviamo un nuovo messaggio
    else:
        await update.message.reply_text(
            text=display_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
async def process_code_validation(update: Update, context: ContextTypes.DEFAULT_TYPE, full_code: str, action: str, target_stage: int) -> None:
    """Esegue la validazione del codice finale dopo la pressione di CONFERMA."""
    
    chat_id = update.effective_chat.id
    couple_stages = get_couple_stages(context)
    couple_name = couple_stages[chat_id]['nome']
    
    # Rimuovi lo stato del compositore
    if CODE_COMPOSER in context.user_data:
        del context.user_data[CODE_COMPOSER]

    # --- Azione: SBLOCCO PROVA (Codice 1) ---
    if action == 'DISCOVER_PROOF':
        correct_code = DISCOVERY_CODES.get(target_stage)
        proof_data = PROOFS_DATA.get(target_stage)
        
        if full_code == correct_code and proof_data:
            couple_stages[chat_id]['prova_sbloccata'] = True
            
            await update.callback_query.edit_message_text(
                f"🎉 CODICE CORRETTO! (Codice inserito: {full_code})\n\n{proof_data['name']}\n\n{proof_data['text']}\n\n"
                "Buona fortuna! Una volta completata la prova e ricevuto il codice finale, "
                "usate il comando /superaprova per proseguire."
            )
        else:
            await update.callback_query.edit_message_text(
                f"❌ CODICE ERRATO. (Codice inserito: {full_code})\n"
                "Riprovate inserendo il codice esatto per lo sblocco.\n"
                "Usate nuovamente /tentaprova per ritentare."
            )

    # --- Azione: AVANZAMENTO TAPPA ---
    elif action == 'ADVANCE_WITH_CODE':
        correct_code = ADVANCEMENT_CODES.get(target_stage)
        
        if full_code == correct_code:
            
            new_stage = target_stage + 1
            couple_stages[chat_id]['tappa'] = new_stage
            couple_stages[chat_id]['prova_sbloccata'] = False
            
            completion_message = ""
            if new_stage <= MAX_STAGE:
                completion_message = (
                    f"🎉 CODICE CORRETTO! Complimenti {couple_name}! "
                    f"Siete stati promossi alla Tappa {new_stage}."
                    f"\n\nOra usate /indizio per scoprire la prossima tappa e "
                    f"/tentaprova per sbloccare la Prova {new_stage}."
                )
            elif new_stage == MAX_STAGE + 1:
                 completion_message = (
                    f"🎉 CODICE CORRETTO! Complimenti {couple_name}! "
                    f"Avete superato la prova {target_stage} e completato il percorso! "
                    f"Martina Express è concluso!\n"
                    f"Grazie per aver giocato! 😄"
                )
            
            await update.callback_query.edit_message_text(completion_message)

        else:
            await update.callback_query.edit_message_text(
                f"❌ CODICE ERRATO. (Codice inserito: {full_code})\n"
                "Riprovate inserendo il codice esatto per l'avanzamento.\n"
                "Usate nuovamente /superaprova per riaprire il compositore."
            )

async def handle_keypad_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce l'input da tastiera inline per la composizione del codice."""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat_id
    data = query.data
    
    # Controllo di sicurezza: lo stato del compositore deve esistere
    if CODE_COMPOSER not in context.user_data or context.user_data[CODE_COMPOSER].get('chat_id') != chat_id:
        await query.edit_message_text("Sessione scaduta o non valida. Usate /tentaprova o /superaprova per iniziare.")
        return

    composer_state = context.user_data[CODE_COMPOSER]
    current_code = composer_state['code']
    code_length = len(current_code)
    
    # --- Gestione Input ---
    
    # Tasto numerico (CODE_KEY_X)
    if data.startswith("CODE_KEY_") and data[-1].isdigit():
        if code_length < 4:
            # Aggiunge la cifra
            composer_state['code'] += data[-1]
            await send_keypad(update, context, get_couple_stages(context), chat_id, composer_state['action'])
    
    # Tasto INDIETRO (CODE_KEY_BACK)
    elif data == "CODE_KEY_BACK":
        if code_length > 0:
            # Rimuove l'ultima cifra
            composer_state['code'] = current_code[:-1]
            await send_keypad(update, context, get_couple_stages(context), chat_id, composer_state['action'])
    
    # Tasto CONFERMA (CODE_KEY_CONFIRM)
    elif data == "CODE_KEY_CONFIRM":
        if code_length == 4:
            # Codice completo, passa alla validazione
            await process_code_validation(update, context, current_code, composer_state['action'], composer_state['target_stage'])
        else:
            # Non dovrebbe accadere se la tastiera è corretta, ma per sicurezza
            await query.answer("Il codice deve essere di 4 cifre prima di confermare.", show_alert=True)
            
    # Tasto AVANTI (CODE_KEY_FORWARD)
    elif data == "CODE_KEY_FORWARD":
        # Questo tasto è attivo solo quando il codice non è completo (lunghezza < 4).
        # Agisce solo come feedback, non fa nulla se non confermare la scelta.
        pass # Non serve fare nulla qui, l'utente deve premere la cifra.


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
            f"⚠️ {target_name} non è ancora registrata (Tappa 0).\n"
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
            if new_stage<4:
                await context.bot.send_message(
                    chat_id=target_chat_id,
                    text=f"🎉 Complimenti! Avete superato la prova {new_stage-1}! Siete stati promossi alla Tappa {new_stage}."
                        f" Usate il comando /indizio per scoprire gli indizi della prossima tappa e "
                        "il comando /tentaprova per provare la sfida della tappa successiva."
                )
            elif new_stage==4:
                await context.bot.send_message(
                    chat_id=target_chat_id,
                    text=f"🎉 Complimenti! Avete superato la prova {new_stage-1} e avete completato Martina Express!"
                        f" Grazie per aver giocato, spero vi siate divertiti! 😄"
                )
        
        except Exception as e:
            # Manda un errore all'admin (nella chat admin) se la notifica fallisce
            logging.error(f"Errore nella notifica alla coppia {target_name}: {e}")

# Nuova funzione: Resetta tutti i progressi del gioco
async def resetgioco_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando ADMIN: Resetta lo stato di tutte le coppie a zero."""
    
    # Controllo di sicurezza: solo l'admin può eseguire questo comando
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("Non sei autorizzato a usare questo comando.")
        return
    
    couple_stages = get_couple_stages(context)
    
    # Conferma con un pulsante prima di resettare (molto importante!)
    keyboard = [
        [
            InlineKeyboardButton("✅ SÌ, CONFERMO IL RESET TOTALE", callback_data="CONFIRM_RESET")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "⚠️ ATTENZIONE: Sei sicuro di voler resettare il gioco?\n"
        "Questo eliminerà i progressi di tutte le coppie e le obbligherà a ri-registrarsi.",
        reply_markup=reply_markup
    )

# Nuova funzione: Gestisce la conferma del reset
async def handle_reset_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce la callback query di conferma reset."""
    query = update.callback_query
    
    # Controllo di sicurezza aggiuntivo
    if update.effective_user.id != ADMIN_USER_ID:
        await query.answer("Non sei autorizzato a eseguire questa azione.", show_alert=True)
        return
        
    await query.answer()

    if query.data == "CONFIRM_RESET":
        # IL VERO RESET: Elimina l'intera chiave 'COUPLE_STAGES' dai dati persistenti
        if 'COUPLE_STAGES' in context.bot_data:
            del context.bot_data['COUPLE_STAGES']
            
            # Notifica l'admin
            await query.edit_message_text(
                "✅ RESET COMPLETATO! Tutti i progressi delle coppie sono stati eliminati."
            )
        else:
            await query.edit_message_text("Il gioco era già in stato iniziale (nessun dato da resettare).")

# Nuova funzione: Visualizza lo stato di gioco
async def statogioco_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando ADMIN: Mostra un riepilogo dello stato di gioco attuale."""
    
    # Controllo di sicurezza: solo l'admin può eseguire questo comando
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("Non sei autorizzato a usare questo comando.")
        return
    
    couple_stages = get_couple_stages(context)
    
    if not couple_stages:
        await update.message.reply_text("Lo stato è vuoto: Nessuna coppia è attualmente registrata.")
        return

    report = "📊 **STATO DI GIOCO ATTUALE** 📊\n\n"
    
    # Ordina le coppie per numero di tappa (dalla più avanti alla più indietro)
    # Crea una lista di tuple (tappa, nome_coppia, dati)
    sorted_couples = sorted(
        [(data['tappa'], data['nome'], data) for data in couple_stages.values()],
        key=lambda item: item[0],  # Ordina per tappa (indice 0)
        reverse=True              # Dalla tappa più alta alla più bassa
    )
    
    for tappa, nome, data in sorted_couples:
        # Aggiunge un flag se la prova è stata sbloccata
        prova_sbloccata = "✅ Sbloccata" if data.get('prova_sbloccata', False) else "❌ Bloccata"
        
        report += (
            f"**{nome}**\n"
            f"  - Tappa attuale: **{tappa}**\n"
            f"  - Prova Tappa {tappa}: {prova_sbloccata}\n"
        )
        # Se vuoi vedere il Chat ID per debugging:
        # chat_id = next((k for k, v in couple_stages.items() if v['nome'] == nome), "N/A")
        # report += f"  - ID Chat: {chat_id}\n"
        report += "--------------------\n"

    await update.message.reply_text(report, parse_mode='Markdown')

# Funzione che risponde a qualsiasi altro testo
async def echo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ripete il messaggio ricevuto."""
    if update.message and update.message.text:
        await update.message.reply_text(f"Non ho capito. Usa /help per vedere i comandi disponibili.")


# --- FUNZIONE DI INIZIALIZZAZIONE DEL BOT (ORA ASINCRONA) ---
# DEVE ESSERE ASINCRONA PER POTER USARE AWAIT SU set_webhook!
async def init_bot_application() -> None: # <--- RESA ASINCRONA
    """Crea l'oggetto Application, registra gli handler e imposta il webhook su Telegram."""
    global APPLICATION
    
    # Se APPLICATION è già stato creato in questo processo (worker Gunicorn), usciamo.
    if APPLICATION is not None:
        return
        
    logging.info(f"-> Inizializzazione ASINCRONA del Telegram Application... URL: {WEBHOOK_URL}")
    
    # Configura la persistenza
    persistence = PicklePersistence(filepath='game_state.pkl')

    # Crea l'oggetto Application
    APPLICATION = Application.builder().token(TOKEN).persistence(persistence).build()
    
    # Inizializza l'Application
    APPLICATION.initialize()

    
    
    # Registrazione Webhook su Telegram
    try:
        # 1. Chiama l'API di Telegram per registrare l'URL (ORA CON AWAIT)
        await APPLICATION.bot.set_webhook(
            url=WEBHOOK_URL,
            drop_pending_updates=True
        )
        logging.info("-> Webhook registrato su Telegram con successo (set_webhook).")
    except Exception as e:
        logging.error(f"-> ERRORE nella registrazione del Webhook: {e}")



# --- FUNZIONE PRINCIPALE ---
def main():
    persistence = PicklePersistence(filepath="game_state.pkl")
    app = Application.builder().token(TOKEN).persistence(persistence).build()

    # Comandi base
    # Registra tutti gli handler
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("setcoppia", setcoppia_command))
    app.add_handler(CommandHandler("stradeammesse", stradeammesse_command))
    app.add_handler(CommandHandler("indizio", indizio_command))
    app.add_handler(CommandHandler("tentaprova", tentaprova_command))
    app.add_handler(CommandHandler("superaprova", superaprova_command))
    app.add_handler(CommandHandler("scopettonero", scopettonero_command))
    app.add_handler(CommandHandler("avanzatappa", avanzatappa_command))
    app.add_handler(CommandHandler("resetgioco", resetgioco_command))
    app.add_handler(CommandHandler("statogioco", statogioco_command))

    app.add_handler(CallbackQueryHandler(handle_couple_selection, pattern=r'^SET_'))
    app.add_handler(CallbackQueryHandler(handle_advance_selection, pattern=r'^ADVANCE'))
    app.add_handler(CallbackQueryHandler(handle_hint_selection, pattern=r'^HINT_'))
    app.add_handler(CallbackQueryHandler(handle_keypad_input, pattern=r'^CODE_KEY_'))
    app.add_handler(CallbackQueryHandler(handle_reset_confirmation, pattern=r'^CONFIRM_RESET'))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_command))

    logging.info("🤖 Bot avviato in modalità polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
