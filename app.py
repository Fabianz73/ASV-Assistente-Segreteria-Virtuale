import io
import re
import textwrap
import unicodedata

import streamlit as st
from google import genai
from google.genai import types
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


# -------------------- CONFIGURAZIONE --------------------
st.set_page_config(
    page_title="Assistente Segreteria Scuola",
    page_icon="🏫",
    layout="wide",
)

MODEL_NAME = "gemini-3.8-flash"

st.markdown(
    """
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
        font-size: 1.05em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

SYSTEM_PROMPT = """
Rispondi sempre in lingua italiana corretta, chiara e formale.

Sei un tutor e assistente amministrativo per le segreterie scolastiche italiane.
L'utente può essere un nuovo assunto che non conosce le procedure interne né il gergo tecnico.

REGOLE DI ACCURATEZZA:
- Non inventare norme, numeri di circolari, date, link o procedure.
- Distingui le informazioni verificate dalle indicazioni generali.
- Quando non puoi verificare la vigenza di una norma o non hai accesso alla ricerca web,
  dichiaralo esplicitamente e invita a controllare la fonte ufficiale.
- Dai priorità alle fonti ufficiali italiane: mim.gov.it, gazzettaufficiale.it,
  normattiva.it e aranagenzia.it. Orizzonte Scuola può essere usato solo come
  approfondimento operativo, non come sostituto della fonte normativa.
- Non dichiarare di aver consultato siti web se non è stata effettuata una ricerca.

STRUTTURA DELLA RISPOSTA:
1. RIFERIMENTI NORMATIVI (se pertinenti):
   - Nome/numero dell'atto e data, seguito da una breve spiegazione e dal link ufficiale
     solo se noto e attendibile.
   - Se non puoi identificare con sicurezza una norma pertinente, dillo senza inventarla.

2. GUIDA PRATICA PER NEOFITI:
   - Massimo 3-4 passaggi concreti e brevi.
   - Spiega le sigle e le piattaforme quando servono (SIDI, Argo/Axios, NoiPA,
     protocollo informatico, fascicolo personale).
   - Concludi questa sezione con una riga nel formato:
     [TRAPPOLE] Indica l'errore principale da evitare. [/TRAPPOLE]

3. AZIONI / DOCUMENTI (solo se richiesti):
   - Se viene richiesta una mail, prepara una bozza pronta da copiare.
   - Se viene richiesto un modulo, una dichiarazione o un documento, racchiudi il testo
     del modulo tra:
     [MODULO_PDF]
     TITOLO DEL MODULO
     Testo con campi compilabili nel formato [NOME_COGNOME]
     [/MODULO_PDF]
   - Inserisci solo campi sensati per il documento richiesto.

4. RISPOSTA DIRETTA:
   - Termina sempre con una riga nel formato:
     [DIRETTA] Indica la risposta immediata e l'azione concreta da fare. [/DIRETTA]
   - Mantieni la risposta diretta semplice e operativa, in massimo 2-3 righe.

DIVIETI:
- Evita un linguaggio burocratico difficile quando spieghi i passaggi.
- Non iniziare con formule come "Certamente, ecco".
- Non aggiungere saluti finali.
- Non fare riassunti lunghi dei decreti.
"""


# -------------------- PDF COMPILABILE --------------------
def nome_campo_sicuro(testo, indice):
    """Crea un nome PDF semplice e univoco."""
    testo_ascii = (
        unicodedata.normalize("NFKD", testo)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    testo_ascii = re.sub(r"[^A-Za-z0-9_]+", "_", testo_ascii).strip("_")
    return f"campo_{indice}_{testo_ascii[:24] or 'testo'}"


def crea_pdf_editabile(testo_modulo):
    """Genera un PDF A4 con campi interattivi per i segnaposto [CAMPO]."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    larghezza, altezza = A4
    margine_sinistro = 50
    margine_destro = 50
    larghezza_testo = larghezza - margine_sinistro - margine_destro
    y_iniziale = altezza - 82
    y = y_iniziale
    numero_campo = 0

    def intestazione():
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(
            margine_sinistro,
            altezza - 40,
            "ISTITUTO SCOLASTICO STATALE - SEGRETERIA AMMINISTRATIVA",
        )
        pdf.setStrokeColor(colors.grey)
        pdf.line(
            margine_sinistro,
            altezza - 50,
            larghezza - margine_destro,
            altezza - 50,
        )

    def nuova_pagina():
        nonlocal y
        pdf.showPage()
        intestazione()
        y = altezza - 72

    intestazione()
    righe = testo_modulo.strip().splitlines()

    for indice_riga, riga_originale in enumerate(righe):
        riga = riga_originale.strip()

        if not riga:
            y -= 12
            if y < 65:
                nuova_pagina()
            continue

        if y < 70:
            nuova_pagina()

        if indice_riga == 0:
            pdf.setFont("Helvetica-Bold", 13)
            parole = riga.split()
            linea = ""
            for parola in parole:
                candidata = f"{linea} {parola}".strip()
                if pdf.stringWidth(candidata, "Helvetica-Bold", 13) <= larghezza_testo:
                    linea = candidata
                else:
                    pdf.drawString(margine_sinistro, y, linea)
                    y -= 18
                    linea = parola
            if linea:
                pdf.drawString(margine_sinistro, y, linea)
                y -= 26
            continue

        # Per rendere il modulo leggibile, ogni segnaposto ha una riga dedicata.
        parti = re.split(r"(\[[^\]]+\])", riga)
        pdf.setFont("Helvetica", 10)
        testo_corrente = ""

        def disegna_testo_wrappato(testo, font="Helvetica", dimensione=10):
            nonlocal y
            parole = testo.split()
            linea_local = ""
            for parola in parole:
                candidata = f"{linea_local} {parola}".strip()
                if pdf.stringWidth(candidata, font, dimensione) <= larghezza_testo:
                    linea_local = candidata
                else:
                    if linea_local:
                        pdf.setFont(font, dimensione)
                        pdf.drawString(margine_sinistro, y, linea_local)
                        y -= 15
                        if y < 65:
                            nuova_pagina()
                    linea_local = parola
            if linea_local:
                pdf.setFont(font, dimensione)
                pdf.drawString(margine_sinistro, y, linea_local)
                y -= 17
                if y < 65:
                    nuova_pagina()

        for parte in parti:
            if parte.startswith("[") and parte.endswith("]"):
                if testo_corrente.strip():
                    disegna_testo_wrappato(testo_corrente.strip())
                    testo_corrente = ""

                etichetta = parte[1:-1].strip() or "Campo"
                # Etichetta e campo sono separati: evita di oltrepassare i margini.
                pdf.setFont("Helvetica", 9)
                etichetta_visuale = f"{etichetta}:"
                pdf.drawString(margine_sinistro, y, etichetta_visuale)
                y -= 19
                if y < 75:
                    nuova_pagina()

                numero_campo += 1
                larghezza_campo = larghezza_testo
                altezza_campo = 20
                pdf.acroForm.textfield(
                    name=nome_campo_sicuro(etichetta, numero_campo),
                    tooltip=etichetta,
                    x=margine_sinistro,
                    y=y - 3,
                    width=larghezza_campo,
                    height=altezza_campo,
                    borderStyle="underlined",
                    borderWidth=1,
                    borderColor=colors.darkblue,
                    fillColor=colors.Color(0.97, 0.98, 1.0),
                    textColor=colors.black,
                    forceBorder=True,
                    fontName="Helvetica",
                    fontSize=10,
                )
                y -= 29
                if y < 65:
                    nuova_pagina()
            else:
                testo_corrente += parte

        if testo_corrente.strip():
            disegna_testo_wrappato(testo_corrente.strip())

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


# -------------------- RENDER DELLA RISPOSTA --------------------
def formatta_e_mostra(testo, indice_msg):
    testo_pulito = testo or ""

    match_trappola = re.search(
        r"\[TRAPPOLE\](.*?)\[/TRAPPOLE\]", testo_pulito, re.DOTALL | re.IGNORECASE
    )
    trappola_html = ""
    if match_trappola:
        contenuto = match_trappola.group(1).strip()
        trappola_html = (
            '<div class="trappola-box">🚨 ERRORE DA EVITARE: '
            + contenuto
            + "</div>"
        )
        testo_pulito = testo_pulito.replace(match_trappola.group(0), "")

    match_modulo = re.search(
        r"\[MODULO_PDF\](.*?)\[/MODULO_PDF\]",
        testo_pulito,
        re.DOTALL | re.IGNORECASE,
    )
    testo_modulo = None
    if match_modulo:
        testo_modulo = match_modulo.group(1).strip()
        testo_pulito = testo_pulito.replace(
            match_modulo.group(0),
            "\n\n**📄 Modulo generato e pronto per il download qui sotto.**\n\n",
        )

    match_diretta = re.search(
        r"\[DIRETTA\](.*?)\[/DIRETTA\]",
        testo_pulito,
        re.DOTALL | re.IGNORECASE,
    )
    diretta_html = ""
    if match_diretta:
        contenuto = match_diretta.group(1).strip()
        diretta_html = (
            '<div class="risposta-diretta">✅ RISPOSTA DIRETTA: '
            + contenuto
            + "</div>"
        )
        testo_pulito = testo_pulito.replace(match_diretta.group(0), "")

    if testo_pulito.strip():
        st.markdown(testo_pulito.strip())

    if trappola_html:
        st.markdown(trappola_html, unsafe_allow_html=True)

    if testo_modulo:
        with st.expander("Anteprima del testo del modulo", expanded=False):
            st.text(testo_modulo)

        try:
            pdf_bytes = crea_pdf_editabile(testo_modulo)
            st.download_button(
                label="📥 Scarica PDF compilabile",
                data=pdf_bytes,
                file_name=f"Modulo_Segreteria_{indice_msg}.pdf",
                mime="application/pdf",
                key=f"btn_pdf_{indice_msg}",
            )
        except Exception as exc:
            st.error(f"Non è stato possibile generare il PDF: {exc}")

    if diretta_html:
        st.markdown(diretta_html, unsafe_allow_html=True)


# -------------------- INTERFACCIA STREAMLIT --------------------
st.title("🏫 Assistente Virtuale Segreteria Scolastica")
st.caption(
    "Guida operativa per il personale amministrativo | "
    "Fonti di riferimento: MIM, Normattiva, Gazzetta Ufficiale e ARAN"
)

with st.sidebar:
    st.header("⚡ Azioni rapide")
    st.markdown("Seleziona una procedura frequente per avviare la richiesta.")

    if st.button("📋 Presa di servizio supplente", use_container_width=True):
        st.session_state["prompt_rapido"] = (
            "Un docente supplente deve prendere servizio oggi ma ha la febbre "
            "e non può venire fisicamente a firmare. Come devo procedere? "
            "Prepara anche una bozza di modulo editabile per la presa di servizio."
        )

    if st.button("🏥 Assenza per malattia ATA/docente", use_container_width=True):
        st.session_state["prompt_rapido"] = (
            "Un docente mi ha comunicato stamattina di essere in malattia. "
            "Spiega i passaggi amministrativi da verificare su SIDI, Argo e NoiPA, "
            "distinguendo gli obblighi certi dalle procedure che dipendono dalla scuola."
        )

    if st.button("✉️ Bozza convocazione interpello", use_container_width=True):
        st.session_state["prompt_rapido"] = (
            "Devo inviare una convocazione urgente per supplenza breve tramite "
            "interpello. Prepara una mail formale e una bozza di modulo di accettazione "
            "editabile. Indica quali dati devo verificare prima dell'invio."
        )

    st.divider()

    if st.button("🗑️ Nuova conversazione", use_container_width=True):
        st.session_state["messaggi"] = []
        st.rerun()

if "messaggi" not in st.session_state:
    st.session_state["messaggi"] = []

# Mostra la cronologia della sessione.
for idx, messaggio in enumerate(st.session_state["messaggi"]):
    with st.chat_message(messaggio["role"]):
        if messaggio["role"] == "assistant":
            formatta_e_mostra(messaggio["content"], idx)
        else:
            st.markdown(messaggio["content"])

domanda = st.chat_input("Scrivi il tuo dubbio amministrativo o chiedi un modulo...")

if "prompt_rapido" in st.session_state:
    domanda = st.session_state.pop("prompt_rapido")

if domanda:
    st.session_state["messaggi"].append({"role": "user", "content": domanda})

    with st.chat_message("user"):
        st.markdown(domanda)

    with st.chat_message("assistant"):
        with st.spinner("Sto preparando la risposta..."):
            try:
                api_key = st.secrets.get("GEMINI_API_KEY")
                if not api_key:
                    raise ValueError(
                        "Chiave API mancante. Configura GEMINI_API_KEY nel file "
                        ".streamlit/secrets.toml."
                    )

                client = genai.Client(api_key=api_key)

                # Gemini usa "user" e "model" come ruoli nella cronologia.
                contenuti = []
                for messaggio in st.session_state["messaggi"][-20:]:
                    ruolo = "model" if messaggio["role"] == "assistant" else "user"
                    contenuti.append(
                        {
                            "role": ruolo,
                            "parts": [{"text": messaggio["content"]}],
                        }
                    )

                risposta = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=contenuti,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.2,
                    ),
                )

                testo_risposta = (risposta.text or "").strip()
                if not testo_risposta:
                    testo_risposta = (
                        "Non è arrivato testo nella risposta del modello. "
                        "Riprova con una domanda più specifica."
                    )

                formatta_e_mostra(testo_risposta, len(st.session_state["messaggi"]))
                st.session_state["messaggi"].append(
                    {"role": "assistant", "content": testo_risposta}
                )

            except Exception as exc:
                st.error(
                    "Si è verificato un problema durante la richiesta a Gemini. "
                    "Controlla la chiave API, la connessione e il nome del modello."
                )
                st.code(str(exc))
