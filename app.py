import io
import re
import textwrap
import unicodedata
from urllib.parse import quote_plus

import streamlit as st
from google import genai
from google.genai import types
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


# -------------------- CONFIGURAZIONE --------------------
st.set_page_config(
    page_title="AVS - Assistente Virtuale Scolastico",
    page_icon="🏫",
    layout="wide",
)

MODEL_NAME = "gemini-3.5-flash-lite"


@st.cache_resource
def get_gemini_client(api_key):
    """Riutilizza il client Gemini invece di ricrearlo a ogni richiesta."""
    return genai.Client(api_key=api_key)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@400;500;600;700;800;900&display=swap');

    :root {
        --avs-lavender: #8172B8;
        --avs-lavender-dark: #62548F;
        --avs-lavender-pale: #F1EDFA;
        --avs-sage: #6F9D8C;
        --avs-sage-pale: #EAF4EF;
        --avs-cream: #FBF9F6;
        --avs-ink: #302D38;
        --avs-muted: #77727F;
        --avs-border: #E6E0EA;
    }

    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
        font-family: 'Nunito Sans', sans-serif;
        color: var(--avs-ink);
    }

    [data-testid="stAppViewContainer"] {
        background: var(--avs-cream);
    }

    [data-testid="stHeader"] {
        background: rgba(251, 249, 246, 0.92);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #F3EFFA 0%, #F8F6F3 58%, #EEF5F0 100%);
        border-right: 1px solid var(--avs-border);
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: var(--avs-ink);
        font-weight: 800;
        letter-spacing: -0.025em;
    }

    h1, h2, h3 {
        font-family: 'Nunito Sans', sans-serif !important;
        color: var(--avs-ink);
        font-weight: 800 !important;
        letter-spacing: -0.035em;
    }

    h1 { line-height: 1.18; }
    p, label, li, .stMarkdown, .stCaption {
        font-family: 'Nunito Sans', sans-serif;
    }

    [data-testid="stCaptionContainer"] p {
        color: var(--avs-muted);
        font-size: 0.94rem;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        line-height: 1.6;
    }

    /* Pulsanti: morbidi, ma con contrasto sufficiente */
    .stButton > button, .stDownloadButton > button, .stLinkButton > a,
    [data-testid="stFormSubmitButton"] button {
        border-radius: 13px;
        border: 1px solid #DED6E8;
        background: #FFFFFF;
        color: var(--avs-lavender-dark);
        font-family: 'Nunito Sans', sans-serif;
        font-weight: 700;
        transition: all 0.18s ease;
        box-shadow: 0 2px 7px rgba(65, 48, 87, 0.04);
    }

    .stButton > button:hover, .stDownloadButton > button:hover,
    .stLinkButton > a:hover, [data-testid="stFormSubmitButton"] button:hover {
        border-color: var(--avs-lavender);
        background: var(--avs-lavender-pale);
        color: #493B75;
        transform: translateY(-1px);
    }

    [data-testid="stFormSubmitButton"] button,
    .stDownloadButton > button {
        background: var(--avs-lavender);
        border-color: var(--avs-lavender);
        color: #FFFFFF;
    }

    [data-testid="stFormSubmitButton"] button:hover,
    .stDownloadButton > button:hover {
        background: var(--avs-lavender-dark);
        color: #FFFFFF;
    }

    /* Campi di testo chiari e arrotondati */
    .stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"],
    .stMultiSelect [data-baseweb="select"] {
        border-radius: 12px;
        border-color: #DCD5E4;
        background: #FFFFFF;
    }

    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--avs-lavender);
        box-shadow: 0 0 0 2px rgba(129, 114, 184, 0.14);
    }

    [data-testid="stChatMessage"] {
        border: 1px solid var(--avs-border);
        border-radius: 18px;
        padding: 1rem 1.15rem;
        background: #FFFFFF;
        box-shadow: 0 3px 12px rgba(55, 45, 68, 0.035);
    }

    [data-testid="stChatInput"] {
        border-radius: 16px;
        border-color: #DCD5E4;
        background: #FFFFFF;
        box-shadow: 0 4px 18px rgba(55, 45, 68, 0.06);
    }

    [data-testid="stExpander"] {
        border: 1px solid var(--avs-border);
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.78);
    }

    [data-testid="stAlert"] {
        border-radius: 14px;
    }

    .trappola-box {
        background-color: #FFF0ED;
        border-left: 5px solid #C96D61;
        padding: 15px 17px;
        border-radius: 12px;
        margin: 15px 0;
        color: #843E37;
        font-weight: 700;
        font-size: 1.02em;
    }

    .risposta-diretta {
        background-color: var(--avs-sage-pale);
        border-left: 5px solid var(--avs-sage);
        padding: 15px 17px;
        border-radius: 12px;
        margin-top: 20px;
        color: #285B49;
        font-weight: 700;
        font-size: 1.02em;
    }

    /* Piccoli dettagli decorativi, discreti e non invasivi */
    .avs-hero {
        position: relative;
        overflow: hidden;
        isolation: isolate;
    }

    .avs-hero::after {
        content: "✦   ·   ♡";
        position: absolute;
        right: 18px;
        top: 12px;
        color: rgba(98, 84, 143, 0.20);
        font-size: 1.05rem;
        letter-spacing: 7px;
        pointer-events: none;
        z-index: -1;
    }

    .avs-cat-chase {
        position: absolute;
        right: 13px;
        bottom: 9px;
        width: 145px;
        height: 32px;
        pointer-events: none;
        user-select: none;
        opacity: 0.88;
    }

    .avs-cat-chase .avs-mouse,
    .avs-cat-chase .avs-cat {
        position: absolute;
        bottom: 0;
        display: inline-block;
        line-height: 1;
        filter: saturate(0.78);
        will-change: transform, opacity;
    }

    .avs-cat-chase .avs-mouse {
        right: 7px;
        font-size: 17px;
        animation: avs-mouse-run 2.7s ease-in-out 0.15s 1 both;
    }

    .avs-cat-chase .avs-cat {
        right: 24px;
        font-size: 23px;
        animation: avs-cat-run 2.7s ease-in-out 1 both;
    }

    @keyframes avs-mouse-run {
        0%   { transform: translateX(0); opacity: 0; }
        8%   { opacity: 0.82; }
        55%  { transform: translateX(-100px) translateY(-2px); opacity: 0.82; }
        76%  { transform: translateX(-118px) translateY(0); opacity: 0.7; }
        100% { transform: translateX(-145px); opacity: 0; }
    }

    @keyframes avs-cat-run {
        0%   { transform: translateX(0); opacity: 0; }
        10%  { opacity: 0.9; }
        54%  { transform: translateX(-90px) translateY(-3px); opacity: 0.9; }
        76%  { transform: translateX(-111px) translateY(0); opacity: 0.78; }
        100% { transform: translateX(-142px); opacity: 0; }
    }

    /* Rispetta chi preferisce ridurre le animazioni nel proprio dispositivo */
    @media (prefers-reduced-motion: reduce) {
        .avs-cat-chase { display: none !important; }
        *, *::before, *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            scroll-behavior: auto !important;
        }
    }

    /* Selezione radio in tonalità lavanda */
    [data-testid="stRadio"] label {
        border-radius: 10px;
    }

    hr {
        border-color: var(--avs-border);
    }

    @media (max-width: 768px) {
        .avs-cat-chase { right: 8px; bottom: 5px; transform: scale(0.82); transform-origin: bottom right; }
        h1 { font-size: 1.8rem !important; }
        [data-testid="stChatMessage"] { padding: 0.8rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

SYSTEM_PROMPT = """
Sei AVS, Assistente Virtuale Scolastico per le segreterie scolastiche italiane.
Rispondi in italiano, in modo pratico, chiaro e conciso.

ACCURATEZZA:
- Non inventare leggi, circolari, date, link o procedure.
- Non dire di aver consultato siti se non hai davvero effettuato una ricerca.
- Se non puoi verificare l'attualità di una norma, dichiaralo e indica di controllare
  le fonti ufficiali: MIM (mim.gov.it), Normattiva (normattiva.it), Gazzetta Ufficiale
  (gazzettaufficiale.it) e ARAN (aranagenzia.it).
- Distingui gli obblighi normativi dalle prassi che possono variare da scuola a scuola.

FORMATO:
- Parti dalla risposta concreta, senza introduzioni o saluti.
- Per le procedure, usa al massimo 3-4 passaggi brevi e spiega le sigle necessarie.
- Quando utile, indica i riferimenti normativi solo se li conosci con sufficiente sicurezza.
- Termina con: [TRAPPOLE] l'errore principale da evitare [/TRAPPOLE]
- Termina inoltre con: [DIRETTA] l'azione concreta da fare, in 1-2 righe [/DIRETTA]
- Se l'utente chiede una mail, fornisci una bozza pronta da copiare.
- Se chiede un modulo/documento da creare in PDF, racchiudilo tra [MODULO_PDF] e
  [/MODULO_PDF] e usa segnaposto come [NOME_COGNOME] per i campi compilabili.
- Non creare un modulo PDF se non è richiesto.
- Evita ripetizioni, spiegazioni lunghe e linguaggio burocratico superfluo.
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
st.title("🏫 AVS Office")
st.caption(
    "Assistente Virtuale Scolastico · Un supporto pratico, chiaro e gentile per la segreteria"
)
# Mostra la piccola animazione una sola volta per sessione, così non distrae
# quando l'utente preme pulsanti o interagisce con la chat.
mostra_animazione_avs = not st.session_state.get("avs_animazione_mostrata", False)
st.session_state["avs_animazione_mostrata"] = True

hero_html = """
    <div class="avs-hero" style="
        background: linear-gradient(115deg, #F0EBFA 0%, #F8F5FB 54%, #EAF4EF 100%);
        border: 1px solid #E6E0EA;
        border-radius: 18px;
        padding: 17px 22px 24px 22px;
        margin: 8px 0 22px 0;
    ">
      <div style="font-size: 1.08rem; font-weight: 800; color: #40384F;">
        La tua segreteria, un po’ più semplice ✨
      </div>
      <div style="font-size: 0.92rem; color: #716B79; margin-top: 4px; padding-right: 95px;">
        Procedure, risposte operative e moduli compilabili in un unico spazio.
      </div>
      __AVS_CAT_ANIMATION__
    </div>
    """

animazione_gatto_html = """
      <div class="avs-cat-chase" aria-hidden="true" title="Una piccola pausa felina">
        <span class="avs-mouse">🐭</span>
        <span class="avs-cat">🐈</span>
      </div>
    """ if mostra_animazione_avs else ""

st.markdown(
    hero_html.replace("__AVS_CAT_ANIMATION__", animazione_gatto_html),
    unsafe_allow_html=True,
)

if "messaggi" not in st.session_state:
    st.session_state["messaggi"] = []
if "modulo_testo_editabile" not in st.session_state:
    st.session_state["modulo_testo_editabile"] = ""
if "modulo_guidato_pronto" not in st.session_state:
    st.session_state["modulo_guidato_pronto"] = False

with st.sidebar:
    st.header("🧰 Strumenti AVS")
    strumento = st.radio(
        "Che cosa vuoi fare?",
        ["Assistente segreteria", "Crea modulo PDF compilabile"],
        key="strumento_avs",
    )

    st.divider()

    if strumento == "Assistente segreteria":
        st.header("⚡ Azioni rapide")
        st.markdown("Seleziona una procedura frequente per avviare la richiesta.")

        nome_scuola = st.text_input(
            "Nome dell'istituto *",
            key="nome_scuola_avs",
            placeholder="Es. I.C. Alessandro Manzoni",
            help="Scrivi il nome della scuola. AVS userà queste informazioni per cercare riferimenti pubblici, privilegiando il sito ufficiale dell'istituto.",
        ).strip()
        localita_scuola = st.text_input(
            "Comune / provincia (facoltativo)",
            key="localita_scuola_avs",
            placeholder="Es. Roma (RM)",
            help="Aggiungi la località se esistono scuole con nomi simili.",
        ).strip()
        sito_scuola = st.text_input(
            "Sito web della scuola (facoltativo)",
            key="sito_scuola_avs",
            placeholder="Es. www.istituto.edu.it",
            help="Se conosci il sito ufficiale, inseriscilo per rendere la ricerca più precisa.",
        ).strip()
        codice_meccanografico = st.text_input(
            "Codice meccanografico (facoltativo)",
            key="codice_meccanografico_avs",
            placeholder="Es. RMIC000000",
            help="Puoi inserirlo per controllare che i risultati riguardino proprio la scuola corretta; non è obbligatorio.",
        ).strip()
        tipologia_scuola = st.selectbox(
            "Tipologia di scuola (facoltativa)",
            ["Non so / cerca tutte le tipologie", "Scuola statale", "Scuola paritaria", "Altra scuola non statale"],
            key="tipologia_scuola_avs",
        )
        st.caption(
            "La ricerca è pensata per scuole di tutta Italia, comprese le scuole paritarie. "
            "Il codice meccanografico è facoltativo e serve solo come elemento di riscontro. "
            "Verifica sempre le informazioni prima di usarle nei documenti."
        )

        contesto_scuola = f"Nome istituto indicato dall'utente: {nome_scuola}."
        if localita_scuola:
            contesto_scuola += f" Località: {localita_scuola}."
        if sito_scuola:
            contesto_scuola += f" Sito web indicato dall'utente: {sito_scuola}."
        if codice_meccanografico:
            contesto_scuola += f" Codice meccanografico fornito come dato facoltativo di riscontro: {codice_meccanografico}. Usalo solo per verificare la corrispondenza, non come unico criterio di ricerca."
        if tipologia_scuola != "Non so / cerca tutte le tipologie":
            contesto_scuola += f" Tipologia indicata dall'utente: {tipologia_scuola}."
        istruzioni_ricerca = (
            "Cerca sul web l'istituto in qualsiasi regione d'Italia, includendo scuole statali, scuole paritarie "
            "e altre scuole non statali. Usa soprattutto denominazione e località; se fornito, usa il codice "
            "meccanografico soltanto come controllo incrociato. Privilegia il sito ufficiale dell'istituto e fonti "
            "istituzionali attendibili, ad esempio Scuola in Chiaro/MIM e pagine ufficiali della scuola. "
            "Restituisci una scheda anagrafica con: denominazione completa, tipologia (statale/paritaria/altro), "
            "codice meccanografico della sede e, se reperibili, dei plessi, indirizzo completo della sede (via/piazza, "
            "numero civico, CAP, comune e provincia), telefono, email ordinaria, PEC, sito web e nominativo del dirigente "
            "solo se pubblicato da fonte attendibile. Per ogni dato indica la fonte e il link, distinguendo dati confermati, "
            "dati non trovati e dati discordanti. Non inventare né completare per supposizione email, telefoni, indirizzi o codici. "
            "Se trovi più istituti omonimi, chiedi di specificare la località invece di scegliere arbitrariamente. "
        )

        if st.button("🔎 Cerca dati della scuola", use_container_width=True):
            if not nome_scuola.strip():
                st.warning("Inserisci almeno il nome della scuola per avviare la ricerca.")
            else:
                st.session_state["prompt_rapido"] = (
                    f"{contesto_scuola} {istruzioni_ricerca} "
                    "Per prima cosa mostra una scheda chiara intitolata 'DATI IDENTIFICATIVI DELLA SCUOLA', "
                    "con i campi richiesti e i link alle fonti consultate. Poi aggiungi una breve nota su quali dati "
                    "sono confermati e quali devono essere verificati dalla segreteria. Non creare documenti in questa richiesta."
                )
                st.session_state["ricerca_web_azione_rapida"] = True

        if st.button("📋 Presa di servizio supplente", use_container_width=True):
            if not nome_scuola:
                st.warning("Inserisci prima il nome dell'istituto.")
            else:
                st.session_state["prompt_rapido"] = (
                    f"{contesto_scuola} {istruzioni_ricerca} "
                    "Un docente supplente deve prendere servizio oggi ma ha la febbre "
                    "e non può venire fisicamente a firmare. Come devo procedere? "
                    "Prepara anche una bozza di modulo editabile per la presa di servizio. "
                    "Inserisci nella bozza solo i dati della scuola che hai potuto verificare; "
                    "per quelli non verificati usa segnaposto tra parentesi quadre."
                )
                st.session_state["ricerca_web_azione_rapida"] = True

        if st.button("🏥 Assenza per malattia ATA/docente", use_container_width=True):
            if not nome_scuola:
                st.warning("Inserisci prima il nome dell'istituto.")
            else:
                st.session_state["prompt_rapido"] = (
                    f"{contesto_scuola} {istruzioni_ricerca} "
                    "Un docente mi ha comunicato stamattina di essere in malattia. "
                    "Spiega i passaggi amministrativi da verificare su SIDI, Argo e NoiPA, "
                    "distinguendo gli obblighi certi dalle procedure che dipendono dalla scuola. "
                    "Non inventare dati specifici dell'istituto e cita le fonti web consultate."
                )
                st.session_state["ricerca_web_azione_rapida"] = True

        if st.button("✉️ Bozza convocazione interpello", use_container_width=True):
            if not nome_scuola:
                st.warning("Inserisci prima il nome dell'istituto.")
            else:
                st.session_state["prompt_rapido"] = (
                    f"{contesto_scuola} {istruzioni_ricerca} "
                    "Devo inviare una convocazione urgente per supplenza breve tramite "
                    "interpello. Prepara una mail formale e una bozza di modulo di accettazione "
                    "editabile. Indica quali dati devo verificare prima dell'invio. "
                    "Inserisci nella bozza solo dati della scuola confermati da fonti affidabili; "
                    "usa segnaposto tra parentesi quadre per le informazioni mancanti e cita le fonti consultate."
                )
                st.session_state["ricerca_web_azione_rapida"] = True

        st.divider()
        if st.button("🗑️ Nuova conversazione", use_container_width=True):
            st.session_state["messaggi"] = []
            st.rerun()
    else:
        st.markdown(
            "Descrivi il modulo che ti serve, controlla la bozza e scarica "
            "un PDF con campi compilabili."
        )
        if st.button("🗑️ Svuota bozza modulo", use_container_width=True):
            st.session_state["modulo_testo_editabile"] = ""
            st.session_state["modulo_guidato_pronto"] = False
            st.rerun()


if strumento == "Crea modulo PDF compilabile":
    st.subheader("📄 Crea un modulo PDF compilabile")
    st.write(
        "Descrivi il documento che ti serve. AVS preparerà una bozza da controllare; "
        "potrai correggerla prima di scaricare il PDF."
    )

    categorie_modulo = [
        "Richiesta o istanza alla scuola",
        "Autorizzazione o consenso",
        "Delega",
        "Autodichiarazione",
        "Presa di servizio o documentazione del personale",
        "Verbale o scheda di rilevazione",
        "Altro modulo",
    ]

    with st.form("form_modulo_guidato"):
        categoria = st.selectbox("Tipo di modulo", categorie_modulo)
        destinatario = st.text_input(
            "A chi è destinato?",
            placeholder="Es. famiglie, docenti, personale ATA, dirigente scolastico",
        )
        scopo = st.text_area(
            "Che cosa deve permettere di fare il modulo?",
            placeholder="Descrivi la richiesta o la procedura. Non inserire dati personali reali.",
            height=100,
        )
        campi_richiesti = st.text_area(
            "Quali campi vuoi inserire? (facoltativo)",
            placeholder="Es. nome e cognome, classe, data, motivazione, firma",
            height=80,
        )
        riferimenti = st.text_area(
            "Indicazioni o testo da rispettare (facoltativo)",
            placeholder="Incolla eventuali istruzioni della scuola o riferimenti già verificati.",
            height=80,
        )
        genera_bozza = st.form_submit_button(
            "✨ Prepara la bozza con AVS", use_container_width=True
        )

    query_ricerca = "modulo scolastico " + categoria
    if destinatario.strip():
        query_ricerca += " " + destinatario.strip()
    if scopo.strip():
        query_ricerca += " " + scopo.strip()
    url_ricerca = "https://www.google.com/search?q=" + quote_plus(
        query_ricerca + " sito scuola istituto MIM"
    )
    st.link_button(
        "🔎 Cerca modelli pubblicati online",
        url_ricerca,
        help="Apre una ricerca web in una nuova scheda. AVS non scarica né verifica automaticamente i risultati.",
        use_container_width=True,
    )
    st.caption(
        "I risultati online sono riferimenti da controllare: un modello di un'altra scuola "
        "non è automaticamente ufficiale o adatto al tuo istituto."
    )

    if genera_bozza:
        if not scopo.strip():
            st.warning("Descrivi brevemente lo scopo del modulo prima di generare la bozza.")
        else:
            api_key = st.secrets.get("GEMINI_API_KEY")
            if not api_key:
                st.error(
                    "Chiave API mancante. Configura GEMINI_API_KEY nei Secrets di Streamlit Cloud."
                )
            else:
                prompt_modulo = f"""
Prepara una BOZZA di modulo amministrativo per una scuola italiana.
Tipo di modulo: {categoria}
Destinatario: {destinatario.strip() or "da specificare"}
Scopo: {scopo.strip()}
Campi richiesti: {campi_richiesti.strip() or "individua i campi strettamente necessari"}
Indicazioni fornite dall'utente: {riferimenti.strip() or "nessuna"}

Regole:
- Rispondi in italiano con il testo del modulo, senza introduzioni e senza markdown decorativo.
- Prima riga: titolo breve del modulo.
- Struttura il testo in sezioni e paragrafi brevi, con spaziatura tramite righe vuote.
- Per ogni campo compilabile usa un segnaposto tra parentesi quadre, con un'etichetta chiara, ad esempio [Nome e cognome], [Classe], [Data], [Firma].
- Per le scelte usa opzioni leggibili con caselle vuote, ad esempio [ ] Sì  [ ] No.
- Non inventare norme, obblighi, loghi, nomi di istituti o riferimenti ufficiali.
- Se servono riferimenti normativi non forniti e non verificabili, inserisci una nota breve: "Riferimenti normativi da verificare prima dell'uso".
- Non chiedere né inserire dati personali reali.
- Consideralo una bozza da verificare e adattare dalla scuola, non un modulo ufficiale.
- Mantieni il documento pratico e conciso.
"""
                try:
                    with st.spinner("AVS sta preparando la bozza..."):
                        client = get_gemini_client(api_key)
                        risposta_modulo = client.models.generate_content(
                            model=MODEL_NAME,
                            contents=prompt_modulo,
                            config=types.GenerateContentConfig(
                                system_instruction=(
                                    "Sei AVS, assistente per le segreterie scolastiche italiane. "
                                    "Genera bozze prudenti, chiare e pratiche. Non inventare "
                                    "norme o dichiarare ufficiale un modello generato."
                                ),
                                temperature=0.2,
                                max_output_tokens=1200,
                            ),
                        )
                    testo_generato = (risposta_modulo.text or "").strip()
                    if not testo_generato:
                        st.error("Non è arrivato testo. Riprova con una descrizione più precisa.")
                    else:
                        st.session_state["modulo_testo_editabile"] = testo_generato
                        st.session_state["modulo_guidato_pronto"] = True
                except Exception as exc:
                    st.error(
                        "Non è stato possibile generare la bozza. Controlla la connessione "
                        "e la configurazione di Gemini."
                    )
                    st.code(str(exc))

    if st.session_state["modulo_guidato_pronto"] or st.session_state["modulo_testo_editabile"]:
        st.divider()
        st.subheader("2. Controlla e correggi la bozza")
        st.info(
            "Controlla il testo e i riferimenti prima dell'uso. Le parole tra parentesi quadre "
            "diventeranno campi compilabili nel PDF."
        )
        testo_modulo_finale = st.text_area(
            "Testo del modulo (puoi modificarlo prima di generare il PDF)",
            key="modulo_testo_editabile",
            height=380,
        )
        if testo_modulo_finale.strip():
            try:
                pdf_bytes = crea_pdf_editabile(testo_modulo_finale)
                st.download_button(
                    label="📥 Scarica PDF compilabile",
                    data=pdf_bytes,
                    file_name="AVS_modulo_compilabile.pdf",
                    mime="application/pdf",
                    key="download_pdf_guidato",
                    use_container_width=True,
                )
            except Exception as exc:
                st.error(f"Non è stato possibile generare il PDF: {exc}")
        st.caption(
            "Nota: la compatibilità dei campi compilabili dipende dal lettore PDF usato, "
            "soprattutto su smartphone. Prova il file prima di distribuirlo."
        )

else:
    # Mostra la cronologia della sessione.
    for idx, messaggio in enumerate(st.session_state["messaggi"]):
        with st.chat_message(messaggio["role"]):
            if messaggio["role"] == "assistant":
                formatta_e_mostra(messaggio["content"], idx)
            else:
                st.markdown(messaggio["content"])

    domanda = st.chat_input("Scrivi il tuo dubbio amministrativo o chiedi un modulo...")

    ricerca_web_azione_rapida = False
    if "prompt_rapido" in st.session_state:
        domanda = st.session_state.pop("prompt_rapido")
        ricerca_web_azione_rapida = st.session_state.pop("ricerca_web_azione_rapida", False)

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
                            "Chiave API mancante. Configura GEMINI_API_KEY nei Secrets di Streamlit Cloud."
                        )

                    client = get_gemini_client(api_key)

                    contenuti = []
                    # Invia solo gli ultimi 4 messaggi per mantenere le risposte rapide.
                    for messaggio in st.session_state["messaggi"][-4:]:
                        ruolo = "model" if messaggio["role"] == "assistant" else "user"
                        contenuti.append(
                            {
                                "role": ruolo,
                                "parts": [{"text": messaggio["content"]}],
                            }
                        )

                    # Nelle azioni rapide abilita la ricerca web di Gemini, così il contesto
                    # della scuola viene verificato online usando nome/località/sito, non il codice.
                    strumenti_ricerca = (
                        [types.Tool(google_search=types.GoogleSearch())]
                        if ricerca_web_azione_rapida
                        else None
                    )
                    configurazione = types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.2,
                        max_output_tokens=1400 if ricerca_web_azione_rapida else 900,
                        tools=strumenti_ricerca,
                    )

                    risposta = client.models.generate_content(
                        model=MODEL_NAME,
                        contents=contenuti,
                        config=configurazione,
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
