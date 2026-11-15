import streamlit as st
from google import genai
from google.genai import types
import io
import re
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# Configurazione della pagina
st.set_page_config(
    page_title="Assistente Segreteria Scuola",
    page_icon="🏫",
    layout="wide"
)

# Stile CSS per evidenziare in VERO ROSSO l'errore da evitare
st.markdown("""
<style>
.trappola-box {
    background-color: #ffebee;
    border-left: 6px solid #d32f2f;
    padding: 15px;
    border-radius: 5px;
    margin: 15px 0;
    color: #b71c1c;
    font-weight: bold;
    font-size: 16px;
}
.risposta-diretta {
    background-color: #e8f5e9;
    border-left: 6px solid #2e7d32;
    padding: 15px;
    border-radius: 5px;
    margin-top: 20px;
    color: #1b5e20;
    font-weight: bold;
    font-size: 16px;
}
</style>
""", unsafe_allow_html=True)

# Funzione per generare un vero PDF editabile con caselle compilabili
def crea_pdf_editabile(testo_modulo, titolo="Modulo_Segreteria"):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    larghezza, altezza = A4
    form = c.acroForm

    # Intestazione documento
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, altezza - 50, "ISTITUTO SCOLASTICO STATALE - SEGRETERIA AMMINISTRATIVA")
    c.line(50, altezza - 60, larghezza - 50, altezza - 60)

    y = altezza - 95
    c.setFont("Helvetica", 11)
    campo_id = 1

    righe = testo_modulo.split('\n')
    for riga in righe:
        if y < 70:
            c.showPage()
            c.setFont("Helvetica", 11)
            y = altezza - 50

        riga_pulita = riga.strip()
        if not riga_pulita:
            y -= 12
            continue

        # Se la riga contiene [CAMPO COMPILABILE] o simili tra parentesi quadre
        if "[" in riga_pulita and "]" in riga_pulita:
            parti = re.split(r'(\[.*?\])', riga_pulita)
            x = 50
            for parte in parti:
                if parte.startswith("[") and parte.endswith("]"):
                    nome_campo = parte[1:-1]
                    larghezza_campo = max(140, len(nome_campo) * 7)
                    if x + larghezza_campo > larghezza - 50:
                        y -= 28
                        x = 50
                    form.textfield(
                        name=f"campo_{campo_id}",
                        tooltip=nome_campo,
                        x=x,
                        y=y - 4,
                        borderStyle='underlined',
                        borderColor=colors.darkblue,
                        fillColor=colors.HexColor("#f0f4f8"),
                        width=larghezza_campo,
                        height=18,
                        fontSize=10
                    )
                    campo_id += 1
                    x += larghezza_campo + 8
                else:
                    c.drawString(x, y, parte)
                    x += c.stringWidth(parte, "Helvetica", 11)
            y -= 28
        else:
            # Testo normale
            c.drawString(50, y, riga_pulita[:95])
            y -= 18

    c.save()
    buffer.seek(0)
    return buffer

# Istruzioni di sistema per l'IA
SYSTEM_INSTRUCTIONS = """
Rispondi sempre ed esclusivamente in lingua italiana corretta, chiara e formale.

Sei un tutor e assistente amministrativo per le segreterie scolastiche italiane. Il tuo utente principale è un nuovo assunto neofita (es. Assistente Amministrativo alla prima nomina) che non conosce le procedure interne né il gergo tecnico.

REGOLE DI RICERCA:
1. Dai priorità assoluta alle norme, decreti legge, circolari e note più recenti (anno 2026 e precedenti in vigore) verificando che non siano abrogate.
2. Usa fonti ufficiali italiane e guide operative scolastiche autorevoli: mim.gov.it, gazzettaufficiale.it, normattiva.it, aranagenzia.it e orizzontescuola.it.

STRUTTURA OBBLIGATORIA DELLA RISPOSTA (Rispetta rigorosamente questo ordine dall'alto verso il basso):

1. **RIFERIMENTI NORMATIVI (Compressi):**
   * **[Nome/Numero Atto + Data]**: riassunto in 1 sola riga semplice di cosa stabilisce. (Inserisci il link ufficiale o di Orizzonte Scuola se disponibile).

2. **GUIDA PRATICA PER NEOFITI (Passo-passo):**
   * Spiega in massimo 3-4 punti brevi cosa fare concretamente in ufficio.
   * Traduci sempre eventuali sigle o piattaforme (es. spiega brevemente cos'è SIDI, Argo/Axios, NoiPA, Protocollo o Fascicolo Personale se vanno usati).
   * Chiudi questa sezione andando a capo e inserendo l'avviso esatto racchiuso tra i tag [TRAPPOLA] e [/TRAPPOLA] così:
     [TRAPPOLA]🚨 ERRORE DA EVITARE: scrivi qui la trappola principale o cosa non fare mai[/TRAPPOLA]

3. **AZIONI / DOCUMENTI (Solo se richiesti):**
   * Se l'utente chiede una mail: scrivila pronta da copiare, formale ma chiara e sintetica.
   * Se l'utente chiede un modulo o un PDF editabile: prepara la struttura essenziale usando i campi tra parentesi quadre (es. [Nome e Cognome], [Data di nascita], [Classe di concorso]) e racchiudi l'intero testo del modulo tra i tag [MODULO_PDF] e [/MODULO_PDF]. Non inserire dati personali reali per rispetto della privacy.

4. **RISPOSTA DIRETTA (SEMPRE IN FONDO):**
   Chiudi obbligatoriamente il messaggio racchiudendo la conclusione operativa tra i tag [DIRETTA] e [/DIRETTA] (massimo 2-3 righe in linguaggio semplice e operativo, es. [DIRETTA]✅ Sì, devi accettare la domanda. Ecco l'azione immediata da fare: ...[/DIRETTA]). Deve essere l'ultima cosa visibile in fondo allo schermo.

DIVIETI:
- Non usare linguaggio burocratico difficile quando spieghi i passaggi al neofita.
- Non scrivere introduzioni ("Certamente, ecco...") né saluti finali dopo la Risposta Diretta.
- Non fare riassunti lunghi dei decreti.
"""

# Intestazione App
st.title("🏫 Assistente Virtuale Segreteria Scolastica")
st.caption("Normative aggiornate (MIM, Normattiva, ARAN, Orizzonte Scuola) • Guida Neofiti • Moduli PDF Editabili")

# Barra laterale con comandi rapidi
with st.sidebar:
    st.header("⚡ Comandi Rapidi")
    st.info("Clicca su un pulsante per avviare subito la procedura guidata:")
    if st.button("📋 Presa di servizio supplente"):
        st.session_state.prompt_rapido = "È arrivato un docente supplente per la prima presa di servizio. Quali documenti servono, cosa devo controllare e preparami il modulo di presa di servizio in PDF editabile."
    if st.button("🤒 Malattia e Visita Fiscale"):
        st.session_state.prompt_rapido = "Un docente ha comunicato stamattina di essere in malattia. Qual è la procedura esatta, le fasce orarie attuali e gli errori da evitare?"
    if st.button("🏖️ Permessi e Ferie Supplenti"):
        st.session_state.prompt_rapido = "Un supplente al 30 giugno chiede permessi retribuiti o ferie durante le lezioni. Cosa spetta secondo l'ultimo CCNL e quali sono le trappole?"
    if st.button("📄 Nulla Osta Alunno"):
        st.session_state.prompt_rapido = "Un genitore chiede il nulla osta per trasferire il figlio in un'altra scuola. Quali controlli devo fare e scrivimi la mail formale di invio."
    st.divider()
    if st.button("🗑️ Nuova Conversazione"):
        st.session_state.messages = []
        st.rerun()

# Controllo chiave API nei Secrets di Streamlit
if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ Chiave API mancante! Inserisci GEMINI_API_KEY nelle impostazioni 'Secrets' di Streamlit Cloud.")
    st.stop()

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# Inizializza cronologia chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# Funzione per formattare il testo con il VERO ROSSO e il pulsante PDF
def mostra_risposta_formattata(testo, indice_msg):
    # Estrai eventuale modulo PDF
    modulo_pdf = None
    match_pdf = re.search(r'\[MODULO_PDF\](.*?)\[/MODULO_PDF\]', testo, re.DOTALL)
    if match_pdf:
        modulo_pdf = match_pdf.group(1).strip()
        testo = re.sub(r'\[MODULO_PDF\].*?\[/MODULO_PDF\]', '\n*(📄 Modulo pronto per il download qui sotto)*\n', testo, flags=re.DOTALL)

    # Sostituisci i tag [TRAPPOLA] con il riquadro ROSSO
    testo = re.sub(
        r'\[TRAPPOLA\](.*?)\[/TRAPPOLA\]',
        r'<div class="trappola-box">\1</div>',
        testo,
        flags=re.DOTALL
    )

    # Sostituisci i tag [DIRETTA] con il riquadro VERDE in fondo
    testo = re.sub(
        r'\[DIRETTA\](.*?)\[/DIRETTA\]',
        r'<div class="risposta-diretta">\1</div>',
        testo,
        flags=re.DOTALL
    )

    st.markdown(testo, unsafe_allow_html=True)

    # Se c'è un modulo, mostra il pulsante di download del PDF editabile
    if modulo_pdf:
        pdf_file = crea_pdf_editabile(modulo_pdf)
        st.download_button(
            label="📥 Scarica Modulo PDF Editabile",
            data=pdf_file,
            file_name=f"Modulo_Segreteria_{indice_msg}.pdf",
            mime="application/pdf",
            key=f"btn_pdf_{indice_msg}"
        )

# Mostra i messaggi precedenti
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            mostra_risposta_formattata(message["content"], i)
        else:
            st.markdown(message["content"])

# Input utente (da barra chat o da pulsante rapido)
prompt = st.chat_input("Scrivi qui il tuo dubbio o chiedi un modulo/mail (es. 'Prepara modulo presa di servizio')...")
if "prompt_rapido" in st.session_state:
    prompt = st.session_state.prompt_rapido
    del st.session_state.prompt_rapido

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consulto MIM, Normattiva, ARAN e Orizzonte Scuola..."):
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
