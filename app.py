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
st.title("🏫 AVS - Assistente Virtuale Scolastico")
st.caption(
    "Guida operativa per il personale amministrativo | "
    "Fonti di riferimento: MIM, Normattiva, Gazzetta Ufficiale e ARAN"
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

                    risposta = client.models.generate_content(
                        model=MODEL_NAME,
                        contents=contenuti,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            temperature=0.2,
                            max_output_tokens=900,
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
