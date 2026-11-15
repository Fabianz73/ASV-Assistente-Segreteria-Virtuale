
import streamlit as st
from google import genai
from google.genai import types
import io
import re
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

st.set_page_config(
    page_title="Assistente Segreteria Scuola",
    page_icon="🏫",
    layout="wide"
)

st.markdown("""
<style>
.trappola-box {
    background-color: #ffebee;
    border-left: 6px solid #c62828;
    padding: 15px;
    border-radius: 5px;
    margin: 15px 0;
    color: #b71c1c;
    font-weight: bold;
    font-size: 1.05em;
}
.risposta-diretta {
    background-color: #e8f5e9;
    border-left: 6px solid #2e7d32;
    padding: 15px;
    border-radius: 5px;
    margin-top: 20px;
    color: #1b5e20;
    font-weight: bold;
    font-size: 1.1em;
}
</style>
""", unsafe_allow_html=True)

SYSTEM_PROMPT = """
Rispondi sempre ed esclusivamente in lingua italiana corretta, chiara e formale.

Sei un tutor e assistente amministrativo per le segreterie scolastiche italiane. Il tuo utente principale è un nuovo assunto neofita (es. Assistente Amministrativo alla prima nomina) che non conosce le procedure interne né il gergo tecnico.

REGOLE DI RICERCA:
1. Dai priorità assoluta alle norme, decreti legge, circolari e note più recenti (anno 2026 e precedenti in vigore) verificando che non siano abrogate.
2. Usa esclusivamente fonti ufficiali e autorevoli italiane: mim.gov.it, gazzettaufficiale.it, normattiva.it, aranagenzia.it e orizzontescuola.it per gli approfondimenti operativi.

STRUTTURA OBBLIGATORIA DELLA RISPOSTA (Rispetta rigorosamente questo ordine dall'alto verso il basso):

1. **RIFERIMENTI NORMATIVI (Compressi):**
   * **[Nome/Numero Atto + Data]**: riassunto in 1 sola riga semplice di cosa stabilisce. (Inserisci il link ufficiale se disponibile).

2. **GUIDA PRATICA PER NEOFITI (Passo-passo):**
   * Spiega in massimo 3-4 punti brevi cosa fare concretamente in ufficio.
   * Traduci sempre eventuali sigle o piattaforme (es. spiega brevemente cos'è SIDI, Argo/Axios, NoiPA, Protocollo o Fascicolo Personale se vanno usati).
   * Chiudi questa sezione andando a capo e scrivendo ESATTAMENTE questo marcatore su una riga da sola:
     [TRAPPOLE] Testo della trappola principale o cosa non fare mai [/TRAPPOLE]

3. **AZIONI / DOCUMENTI (Solo se richiesti):**
   * Se l'utente chiede una mail: scrivila pronta da copiare, formale ma chiara e sintetica.
   * Se l'utente chiede un modulo, una dichiarazione o un documento da compilare: racchiudi la struttura del modulo tra questi marcatori esatti e usa le parentesi quadre per i campi compilabili (es. [NOME_COGNOME], [DATA_NASCITA], [CODICE_FISCALE], [CLASSE_CONCORSO]):
     [MODULO_PDF]
     TITOLO DEL MODULO
     Testo del modulo con i campi [CAMPO_COMPILABILE]
     [/MODULO_PDF]

4. **RISPOSTA DIRETTA (SEMPRE IN FONDO):**
   Chiudi obbligatoriamente il messaggio con questo marcatore esatto su una riga da sola, contenente massimo 2-3 righe in linguaggio semplice e operativo:
   [DIRETTA] Risposta immediata e azione concreta da fare subito [/DIRETTA]

DIVIETI:
- Non usare linguaggio burocratico difficile quando spieghi i passaggi al neofita.
- Non scrivere introduzioni ("Certamente, ecco...") né saluti finali fuori dai marcatori.
- Non fare riassunti lunghi dei decreti.
"""

def crea_pdf_editabile(testo_modulo):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    larghezza, altezza = A4
    form = c.acroForm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, altezza - 45, "ISTITUTO SCOLASTICO STATALE - SEGRETERIA AMMINISTRATIVA")
    c.setStrokeColor(colors.grey)
    c.line(50, altezza - 52, larghezza - 50, altezza - 52)

    y = altezza - 85
    righe = testo_modulo.strip().split("\n")

    for i, riga in enumerate(righe):
        riga = riga.strip()
        if not riga:
            y -= 14
            continue

        if y < 80:
            c.showPage()
            form = c.acroForm
            y = altezza - 60

        if i == 0:
            c.setFont("Helvetica-Bold", 13)
            c.drawString(50, y, riga[:80])
            y -= 28
            continue

        campi = re.findall(r'\[([^\]]+)\]', riga)
        if campi:
            parti = re.split(r'(\[[^\]]+\])', riga)
            x = 50
            c.setFont("Helvetica", 10)
            for idx, parte in enumerate(parti):
                if parte.startswith("[") and parte.endswith("]"):
                    nome_campo = f"campo_{i}_{idx}_{parte[1:-1][:15]}"
                    larghezza_campo = 160
                    if x + larghezza_campo > larghezza - 50:
                        y -= 24
                        x = 50
                    form.textfield(
                        name=nome_campo,
                        tooltip=parte[1:-1],
                        x=x,
                        y=y - 4,
                        width=larghezza_campo,
                        height=18,
                        borderStyle='underlined',
                        borderColor=colors.darkblue,
                        fillColor=colors.Color(0.95, 0.97, 1.0),
                        textColor=colors.black,
                        fontSize=10
                    )
                    x += larghezza_campo + 8
                elif parte:
                    c.drawString(x, y, parte)
                    x += c.stringWidth(parte, "Helvetica", 10) + 4
            y -= 24
        else:
            c.setFont("Helvetica", 10)
            parole = riga.split(" ")
            linea_corrente = ""
            for parola in parole:
                if c.stringWidth(linea_corrente + " " + parola, "Helvetica", 10) < (larghezza - 100):
                    linea_corrente += (" " if linea_corrente else "") + parola
                else:
                    c.drawString(50, y, linea_corrente)
                    y -= 16
                    linea_corrente = parola
            if linea_corrente:
                c.drawString(50, y, linea_corrente)
                y -= 18

    c.save()
    buffer.seek(0)
    return buffer

def formatta_e_mostra(testo, indice_msg):
    testo_pulito = testo

    match_trappola = re.search(r'\[TRAPPOLE\](.*?)\[/TRAPPOLE\]', testo_pulito, re.DOTALL)
    trappola_html = ""
    if match_trappola:
        contenuto_trappola = match_trappola.group(1).strip()
        trappola_html = f'<div class="trappola-box">🚨 ERRORE DA EVITARE: {contenuto_trappola}</div>'
        testo_pulito = testo_pulito.replace(match_trappola.group(0), "")

    match_modulo = re.search(r'\[MODULO_PDF\](.*?)\[/MODULO_PDF\]', testo_pulito, re.DOTALL)
    testo_modulo = None
    if match_modulo:
        testo_modulo = match_modulo.group(1).strip()
        testo_pulito = testo_pulito.replace(match_modulo.group(0), "\n*(📄 Modulo generato e pronto per il download qui sotto)*\n")

    match_diretta = re.search(r'\[DIRETTA\](.*?)\[/DIRETTA\]', testo_pulito, re.DOTALL)
    diretta_html = ""
    if match_diretta:
        contenuto_diretta = match_diretta.group(1).strip()
        diretta_html = f'<div class="risposta-diretta">✅ RISPOSTA DIRETTA: {contenuto_diretta}</div>'
        testo_pulito = testo_pulito.replace(match_diretta.group(0), "")

    st.markdown(testo_pulito.strip())

    if trappola_html:
        st.markdown(trappola_html, unsafe_allow_html=True)

    if testo_modulo:
        with st.expander("Anteprima testo del modulo", expanded=False):
            st.text(testo_modulo)
        pdf_bytes = crea_pdf_editabile(testo_modulo)
        st.download_button(
            label="📥 Scarica PDF Editabile",
            data=pdf_bytes,
            file_name=f"Modulo_Segreteria_{indice_msg}.pdf",
            mime="application/pdf",
            key=f"btn_pdf_{indice_msg}"
        )

    if diretta_html:
        st.markdown(diretta_html, unsafe_allow_html=True)

st.title("🏫 Assistente Virtuale Segreteria Scolastica")
st.caption("Guida operativa per neofiti e personale amministrativo | Fonti ufficiali MIM, Normattiva, ARAN e Orizzonte Scuola")

with st.sidebar:
    st.header("⚡ Azioni Rapide")
    st.markdown("Clicca su una procedura frequente per avviarla subito:")
    if st.button("📋 Presa di servizio supplente"):
        st.session_state["prompt_rapido"] = "Qual è la procedura esatta e quali documenti servono per la presa di servizio di un docente supplente?"
    if st.button("🤒 Assenza per malattia"):
        st.session_state["prompt_rapido"] = "Come si gestisce l'assenza per malattia di un docente o ATA e quando parte la visita fiscale?"
    if st.button("📄 Genera Modulo Presa Servizio"):
        st.session_state["prompt_rapido"] = "Prepara il modulo compilabile di assunzione in servizio per un docente supplente con tutti i campi anagrafici e di nomina."
    st.divider()
    if st.button("🗑️ Nuova conversazione"):
        st.session_state["messaggi"] = []
        st.rerun()

if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ Chiave API mancante! Inserisci GEMINI_API_KEY nelle impostazioni Secrets di Streamlit.")
    st.stop()

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

if "messaggi" not in st.session_state:
    st.session_state["messaggi"] = []

for idx, msg in enumerate(st.session_state["messaggi"]):
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            formatta_e_mostra(msg["content"], idx)
        else:
            st.markdown(msg["content"])

domanda = st.chat_input("Scrivi qui il tuo quesito amministrativo o chiedi un modulo...")

if "prompt_rapido" in st.session_state and st.session_state["prompt_rapido"]:
    domanda = st.session_state["prompt_rapido"]
    del st.session_state["prompt_rapido"]

if domanda:
    st.session_state["messaggi"].append({"role": "user", "content": domanda})
    with st.chat_message("user"):
        st.markdown(domanda)

    with st.chat_message("assistant"):
        with st.spinner("Consulto le normative ufficiali 2026 e Orizzonte Scuola..."):
     
