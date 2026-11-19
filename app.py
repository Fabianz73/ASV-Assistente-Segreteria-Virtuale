import io
import csv
import re
import textwrap
import unicodedata
import time
from html import unescape
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from pathlib import Path

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

MODEL_NAME = "gemini-3.5-flash-lite"  # Modello economico, adatto a richieste frequenti


def cerca_web_pubblica(query, max_risultati=8):
    """Recupera risultati pubblici da DuckDuckGo senza usare il grounding a pagamento."""
    url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
    richiesta = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AVSOffice/1.0)"},
    )
    with urlopen(richiesta, timeout=12) as risposta:
        pagina = risposta.read().decode("utf-8", errors="replace")

    blocchi = re.findall(
        r'<div[^>]+class="result[^"]*"[^>]*>(.*?)</div>\s*</div>',
        pagina,
        flags=re.IGNORECASE | re.DOTALL,
    )
    risultati = []
    for blocco in blocchi:
        link_match = re.search(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            blocco,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not link_match:
            continue
        link = unescape(re.sub(r"<[^>]+>", "", link_match.group(1))).strip()
        titolo = unescape(re.sub(r"<[^>]+>", "", link_match.group(2))).strip()
        snippet_match = re.search(
            r'<(?:a|div)[^>]+class="result__snippet"[^>]*>(.*?)</(?:a|div)>',
            blocco,
            flags=re.IGNORECASE | re.DOTALL,
        )
        snippet = unescape(re.sub(r"<[^>]+>", " ", snippet_match.group(1))).strip() if snippet_match else ""
        if titolo and link.startswith("http"):
            risultati.append({"titolo": titolo, "url": link, "estratto": re.sub(r"\s+", " ", snippet)})
        if len(risultati) >= max_risultati:
            break
    return risultati


def normalizza_intestazione(testo):
    """Normalizza intestazioni e testi per confronti tolleranti ad accenti e punteggiatura."""
    testo = unicodedata.normalize("NFKD", str(testo or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", testo.lower())


def leggi_csv_scuole(contenuto, nome_file="archivio.csv"):
    """Legge CSV MIM con BOM e separatori comuni (;, , o tab)."""
    if isinstance(contenuto, bytes):
        testo = contenuto.decode("utf-8-sig", errors="replace")
    else:
        testo = str(contenuto).lstrip("\ufeff")
    campione = testo[:12000]
    try:
        dialetto = csv.Sniffer().sniff(campione, delimiters=";,\t|")
        delimitatore = dialetto.delimiter
    except csv.Error:
        delimitatore = ";" if campione.count(";") >= campione.count(",") else ","
    lettore = csv.DictReader(io.StringIO(testo), delimiter=delimitatore)
    if not lettore.fieldnames:
        return []
    righe = []
    for riga in lettore:
        pulita = {str(k or "").strip().lstrip("\ufeff"): str(v or "").strip() for k, v in riga.items() if k}
        if any(pulita.values()):
            pulita["__file_origine__"] = nome_file
            righe.append(pulita)
    return righe


def carica_archivi_scuole(file_caricati=None):
    """Carica automaticamente i CSV presenti accanto ad app.py e/o quelli caricati nell'interfaccia."""
    righe = []
    nomi_attesi = ("SCUANAGRAFEPAR20262720260901.csv", "SCUANAGRAFESTAT20262720260901.csv")
    cartella_app = Path(__file__).resolve().parent
    trovati_locali = []
    for nome in nomi_attesi:
        percorso = cartella_app / nome
        if percorso.is_file():
            trovati_locali.append(percorso)
    for percorso in trovati_locali:
        try:
            righe.extend(leggi_csv_scuole(percorso.read_bytes(), percorso.name))
        except Exception:
            continue
    for file in (file_caricati or []):
        try:
            file.seek(0)
            righe.extend(leggi_csv_scuole(file.read(), getattr(file, "name", "CSV caricato")))
        except Exception:
            continue
    return righe, len(trovati_locali)


def valore_colonna(riga, alias):
    """Trova una colonna usando alias, perché le intestazioni possono variare tra dataset."""
    colonne = {normalizza_intestazione(k): v for k, v in riga.items() if not str(k).startswith("__")}
    for nome in alias:
        chiave = normalizza_intestazione(nome)
        if chiave in colonne and colonne[chiave]:
            return colonne[chiave]
    # Fallback tollerante: intestazioni con suffissi/prefissi aggiuntivi.
    for nome in alias:
        chiave = normalizza_intestazione(nome)
        for intestazione, valore in colonne.items():
            if valore and chiave and (intestazione.endswith(chiave) or chiave.endswith(intestazione)):
                return valore
    return ""


def cerca_scuole_nei_csv(righe, nome_scuola, regione, massimo=12):
    """Ricerca locale per denominazione e regione; non usa Gemini né richieste web."""
    query = normalizza_intestazione(nome_scuola)
    parole = [p for p in re.findall(r"[a-z0-9]+", normalizza_intestazione(nome_scuola)) if len(p) > 1]
    regione_norm = normalizza_intestazione(regione)
    risultati = []
    for riga in righe:
        nome = valore_colonna(riga, ["DENOMINAZIONESCUOLA", "DENOMINAZIONE SCUOLA", "DENOMINAZIONE", "NOME SCUOLA"])
        if not nome:
            continue
        regione_riga = valore_colonna(riga, ["REGIONE", "DESCRIZIONEREGIONE", "REGIONE SCUOLA"])
        if regione_riga and normalizza_intestazione(regione_riga) != regione_norm:
            continue
        nome_norm = normalizza_intestazione(nome)
        # Richiede una corrispondenza significativa, evitando risultati casuali.
        if query and query in nome_norm:
            punteggio = 100 + len(query)
        elif parole and all(parola in nome_norm for parola in parole):
            punteggio = 50 + sum(len(parola) for parola in parole)
        elif parole:
            corrispondenze = sum(1 for parola in parole if parola in nome_norm)
            if corrispondenze < max(2, (len(parole) + 1) // 2):
                continue
            punteggio = corrispondenze * 10
        else:
            continue
        riga_out = {
            "denominazione": nome,
            "codice": valore_colonna(riga, ["CODICESCUOLA", "CODICE SCUOLA", "CODICE MECCANOGRAFICO", "CODICE MECCANOGRAFICO SCUOLA"]),
            "indirizzo": valore_colonna(riga, ["INDIRIZZOSCUOLA", "INDIRIZZO SCUOLA", "INDIRIZZO"]),
            "cap": valore_colonna(riga, ["CAPSCUOLA", "CAP SCUOLA", "CAP"]),
            "comune": valore_colonna(riga, ["DESCRIZIONECOMUNE", "COMUNE", "DENOMINAZIONECOMUNE", "CODICECOMUNESCUOLA"]),
            "provincia": valore_colonna(riga, ["PROVINCIA", "SIGLAPROVINCIA"]),
            "regione": regione_riga or regione,
            "telefono": valore_colonna(riga, ["TELEFONO", "TELEFONOSCUOLA", "NUMEROTELEFONO", "TELEFONO SCUOLA"]),
            "email": valore_colonna(riga, ["INDIRIZZOEMAILSCUOLA", "EMAILSCUOLA", "EMAIL", "INDIRIZZOEMAIL"]),
            "pec": valore_colonna(riga, ["INDIRIZZOPECSCUOLA", "PECSCUOLA", "PEC", "INDIRIZZOPEC"]),
            "sito": valore_colonna(riga, ["SITOWEBSCUOLA", "SITOWEB", "URLSITO", "SITO WEB", "SITOISTITUTO"]),
            "tipo": valore_colonna(riga, ["DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA", "TIPOLOGIA", "ORDINESCUOLA", "GRADOISTRUZIONE"]),
            "origine": riga.get("__file_origine__", "archivio CSV"),
            "_punteggio": punteggio,
        }
        risultati.append(riga_out)
    risultati.sort(key=lambda x: x["_punteggio"], reverse=True)
    # Evita duplicati per codice meccanografico, mantenendo il primo risultato.
    unici, visti = [], set()
    for risultato in risultati:
        chiave = risultato["codice"] or (risultato["denominazione"], risultato["origine"])
        if chiave in visti:
            continue
        visti.add(chiave)
        unici.append(risultato)
        if len(unici) >= massimo:
            break
    return unici


def mostra_schede_scuole(risultati):
    """Mostra i dati realmente presenti nei CSV; non completa né inventa i campi mancanti."""
    for i, scuola in enumerate(risultati, 1):
        with st.container(border=True):
            st.markdown(f"### 🏫 {scuola['denominazione']}")
            if scuola["codice"]:
                st.markdown(f"**Codice meccanografico:** `{scuola['codice']}`")
            else:
                st.warning("Codice meccanografico non presente nella riga del CSV.")
            if scuola["tipo"]:
                st.write(f"**Tipologia:** {scuola['tipo']}")
            indirizzo = scuola["indirizzo"]
            if scuola["cap"]:
                indirizzo = f"{indirizzo}, {scuola['cap']}" if indirizzo else scuola["cap"]
            if scuola["comune"]:
                indirizzo = f"{indirizzo} · {scuola['comune']}" if indirizzo else scuola["comune"]
            if scuola["provincia"]:
                indirizzo = f"{indirizzo} ({scuola['provincia']})" if indirizzo else scuola["provincia"]
            st.write(f"**Indirizzo:** {indirizzo or 'Non presente nel CSV'}")
            st.write(f"**Telefono:** {scuola['telefono'] or 'Non presente nel CSV'}")
            st.write(f"**Email:** {scuola['email'] or 'Non presente nel CSV'}")
            st.write(f"**PEC:** {scuola['pec'] or 'Non presente nel CSV'}")
            sito = scuola["sito"].strip()
            if sito:
                if not sito.startswith(("http://", "https://")):
                    sito = "https://" + sito
                st.markdown(f"**Sito web:** [{sito}]({sito})")
            else:
                st.write("**Sito web:** Non presente nel CSV")
            st.caption(f"Fonte: {scuola['origine']} · Anagrafica scolastica 2026/2027. I campi mancanti non sono stati dedotti.")


@st.cache_resource
def get_gemini_client(api_key):
    """Riutilizza il client Gemini invece di ricrearlo a ogni richiesta."""
    return genai.Client(api_key=api_key)


def genera_con_attesa(client, *, modello, contenuti, configurazione, max_tentativi=2):
    """Chiama Gemini e gestisce brevi limiti RPM con un conto alla rovescia discreto.

    Per limiti giornalieri non tiene aperta la pagina per ore: mostra un errore
    leggibile al chiamante, che potrà indicare all'utente di riprovare più tardi.
    """
    for tentativo in range(max_tentativi):
        try:
            return client.models.generate_content(
                model=modello, contents=contenuti, config=configurazione
            )
        except Exception as exc:
            errore = str(exc)
            if "429" not in errore and "RESOURCE_EXHAUSTED" not in errore:
                raise
            # Legge eventuale RetryInfo restituito dall'API; in assenza usa 12 s.
            match = re.search(r"(?:retryDelay|retry_delay)[^\n]{0,35}?(\d+)s", errore, re.I)
            if not match:
                match = re.search(r"RetryInfo[^\n]{0,100}?(\d+)s", errore, re.I)
            attesa = int(match.group(1)) if match else 12
            # Una pausa lunga è probabilmente un limite giornaliero: niente attese infinite.
            if attesa > 45 or tentativo >= max_tentativi - 1:
                if attesa > 45:
                    raise RuntimeError(
                        f"QUOTA_GIORNALIERA: Google ha indicato di riprovare tra circa "
                        f"{attesa // 3600} h e {(attesa % 3600) // 60} min. "
                        "AVS non ripeterà automaticamente la richiesta per evitare chiamate inutili."
                    ) from exc
                raise
            attesa = max(3, attesa)
            box_attesa = st.empty()
            for secondi in range(attesa, 0, -1):
                box_attesa.caption(f"⏳ Servizio occupato: nuovo tentativo tra {secondi} s…")
                time.sleep(1)
            box_attesa.empty()
    raise RuntimeError("Richiesta non completata. Riprova tra poco.")

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

    /* Piccoli dettagli grafici: interfaccia ariosa senza appesantire la pagina */
    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stMetric"]) {
        background: #FFFFFF;
        border: 1px solid var(--avs-border);
        border-radius: 14px;
        padding: 0.45rem 0.7rem;
    }
    [data-testid="stSidebar"] .stRadio label {
        font-weight: 650;
    }
    .stSpinner > div { border-top-color: var(--avs-lavender) !important; }

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

def torna_alla_pagina_principale():
    """Chiude la pagina di ricerca quando si cambia strumento dal menu."""
    st.session_state["pagina_ricerca_scuola"] = False


if "pagina_ricerca_scuola" not in st.session_state:
    st.session_state["pagina_ricerca_scuola"] = False

with st.sidebar:
    st.header("🧰 Strumenti AVS")
    strumento = st.radio(
        "Che cosa vuoi fare?",
        ["Assistente segreteria", "Crea modulo PDF compilabile"],
        key="strumento_avs",
        on_change=torna_alla_pagina_principale,
    )

    st.divider()

    if strumento == "Assistente segreteria":
        st.header("⚡ Azioni rapide")
        st.markdown("Seleziona una procedura frequente per avviare la richiesta.")

        if st.button("🔎 Richiesta codice meccanografico scolastico", use_container_width=True):
            st.session_state["pagina_ricerca_scuola"] = True
            st.rerun()

        # Non chiediamo più il nome dell'istituto nella barra laterale.
        # Le bozze useranno segnaposto per i dati della scuola non forniti.
        contesto_scuola = (
            "Istituto non specificato dall'utente. Usa segnaposto tra parentesi quadre "
            "per i dati mancanti. "
        )
        istruzioni_istituto = (
            "Non inventare dati ufficiali della scuola e non dichiarare di averli verificati online. "
            "Per ogni dato dell'istituto non fornito dall'utente, usa un segnaposto tra parentesi quadre "
            "e indica cosa va verificato prima dell'uso. "
        )

        if st.button("📋 Presa di servizio supplente", use_container_width=True):
            st.session_state["prompt_rapido"] = (
                f"{contesto_scuola} {istruzioni_istituto} "
                "Un docente supplente deve prendere servizio oggi ma ha la febbre "
                "e non può venire fisicamente a firmare. Come devo procedere? "
                "Prepara anche una bozza di modulo editabile per la presa di servizio. "
                "Inserisci nella bozza solo i dati della scuola che hai potuto verificare; "
                "per quelli non verificati usa segnaposto tra parentesi quadre."
            )
            st.session_state["ricerca_web_azione_rapida"] = True

        if st.button("🏥 Assenza per malattia ATA/docente", use_container_width=True):
            st.session_state["prompt_rapido"] = (
                f"{contesto_scuola} {istruzioni_istituto} "
                "Un docente mi ha comunicato stamattina di essere in malattia. "
                "Spiega i passaggi amministrativi da verificare su SIDI, Argo e NoiPA, "
                "distinguendo gli obblighi certi dalle procedure che dipendono dalla scuola. "
                "Non inventare dati specifici dell'istituto e cita le fonti web consultate."
            )
            st.session_state["ricerca_web_azione_rapida"] = True

        if st.button("✉️ Bozza convocazione interpello", use_container_width=True):
            st.session_state["prompt_rapido"] = (
                f"{contesto_scuola} {istruzioni_istituto} "
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
    elif strumento == "Crea modulo PDF compilabile":
        st.markdown(
            "Descrivi il modulo che ti serve, controlla la bozza e scarica "
            "un PDF con campi compilabili."
        )
        if st.button("🗑️ Svuota bozza modulo", use_container_width=True):
            st.session_state["modulo_testo_editabile"] = ""
            st.session_state["modulo_guidato_pronto"] = False
            st.rerun()


if st.session_state.get("pagina_ricerca_scuola", False):
    st.subheader("🔎 Richiesta codice meccanografico scolastico")
    st.write(
        "Inserisci il nome della scuola e la regione: AVS cercherà il codice meccanografico, "
        "l'indirizzo, il telefono, l'email e il sito ufficiale cliccabile."
    )
    if st.button("← Torna all'assistente segreteria"):
        st.session_state["pagina_ricerca_scuola"] = False
        st.rerun()

    regioni_italia = [
        "Abruzzo", "Basilicata", "Calabria", "Campania", "Emilia-Romagna",
        "Friuli-Venezia Giulia", "Lazio", "Liguria", "Lombardia", "Marche",
        "Molise", "Piemonte", "Puglia", "Sardegna", "Sicilia", "Toscana",
        "Trentino-Alto Adige", "Umbria", "Valle d'Aosta", "Veneto",
    ]
    with st.form("form_ricerca_dati_scuola"):
        nome_scuola_ricerca = st.text_input(
            "Nome della scuola *",
            placeholder="Es. Istituto Comprensivo Alessandro Manzoni",
        ).strip()
        regione_scuola_ricerca = st.selectbox(
            "Regione di appartenenza *",
            regioni_italia,
            index=None,
            placeholder="Seleziona la regione",
        )
        avvia_ricerca_scuola = st.form_submit_button(
            "🔎 Cerca codice e contatti", use_container_width=True
        )

    # Se i CSV non sono stati inseriti nel repository insieme ad app.py, è possibile caricarli qui.
    percorsi_csv_locali = [
        Path(__file__).resolve().parent / "SCUANAGRAFEPAR20262720260901.csv",
        Path(__file__).resolve().parent / "SCUANAGRAFESTAT20262720260901.csv",
    ]
    csv_locali_presenti = any(percorso.is_file() for percorso in percorsi_csv_locali)
    csv_caricati = []
    if not csv_locali_presenti:
        csv_caricati = st.file_uploader(
            "📂 Archivi scolastici CSV (facoltativo se già presenti nel repository)",
            type=["csv"],
            accept_multiple_files=True,
            key="csv_anagrafi_scuole",
            help="Puoi caricare l'archivio delle scuole statali e quello delle scuole paritarie. La ricerca viene eseguita localmente nei file.",
        )
        st.caption("Suggerimento: per non doverli caricare ogni volta, aggiungi entrambi i CSV nella stessa cartella di app.py nel repository GitHub.")
    else:
        st.caption("✅ Archivi scolastici CSV rilevati nel repository: la ricerca userà prima questi dati ufficiali.")

    if avvia_ricerca_scuola:
        if not nome_scuola_ricerca or not regione_scuola_ricerca:
            st.warning("Inserisci il nome della scuola e seleziona la regione.")
        else:
            try:
                with st.spinner("🔎 Cerco negli archivi scolastici 2026/2027..."):
                    archivi, numero_csv_repo = carica_archivi_scuole(csv_caricati)
                    risultati_locali = cerca_scuole_nei_csv(
                        archivi, nome_scuola_ricerca, regione_scuola_ricerca
                    )
                if risultati_locali:
                    st.success(f"Trovate {len(risultati_locali)} corrispondenze negli archivi scolastici, senza consumare richieste Gemini.")
                    mostra_schede_scuole(risultati_locali)
                    if any(not (r["telefono"] and r["email"] and r["sito"]) for r in risultati_locali):
                        query_web = f'"{nome_scuola_ricerca}" {regione_scuola_ricerca} scuola codice meccanografico telefono email sito ufficiale'
                        st.markdown("**Mancano alcuni contatti nei CSV?** Puoi cercarli sul web aprendo questa ricerca:")
                        st.markdown(f"[🔗 Cerca contatti e sito ufficiale sul web](https://www.google.com/search?q={quote_plus(query_web)})")
                        st.caption("I contatti non presenti nei CSV non vengono inventati; il collegamento apre una ricerca web manuale e non usa Gemini.")
                else:
                    if archivi:
                        st.warning("Non ho trovato una corrispondenza sufficientemente affidabile nei CSV per questa denominazione e regione.")
                    else:
                        st.info("Gli archivi CSV non sono disponibili. Puoi caricarli qui oppure continuare con la ricerca web.")
                    query_web = f'"{nome_scuola_ricerca}" {regione_scuola_ricerca} scuola codice meccanografico telefono email sito ufficiale'
                    st.markdown(f"[🔗 Cerca questa scuola sul web](https://www.google.com/search?q={quote_plus(query_web)})")
                    # La ricerca nei CSV funziona senza Gemini. La ricerca web manuale è sempre disponibile anche in caso di quota esaurita.
                    api_key = st.secrets.get("GEMINI_API_KEY")
                    if api_key:
                        try:
                            with st.spinner("Provo anche a consultare i risultati web pubblici..."):
                                risultati_web = cerca_web_pubblica(query_web)
                            if risultati_web:
                                prompt_scuola = f"""
Sei un assistente per le segreterie scolastiche italiane. Usa esclusivamente i risultati web forniti qui sotto per preparare una scheda sulla scuola richiesta.
Nome richiesto: {nome_scuola_ricerca}
Regione: {regione_scuola_ricerca}
Indica denominazione, codice meccanografico, indirizzo, telefono, email/PEC e sito ufficiale solo se supportati dai risultati. Non inventare dati; per i campi non trovati scrivi 'Non trovato nei risultati disponibili'. Seleziona i link delle fonti tra quelli forniti.
RISULTATI WEB:
""" + "\n".join(f"- {r['titolo']} | {r['url']} | {r['estratto']}" for r in risultati_web)
                                client = get_gemini_client(api_key)
                                risposta_scuola = genera_con_attesa(
                                    client, modello=MODEL_NAME, contenuti=prompt_scuola,
                                    configurazione=types.GenerateContentConfig(temperature=0.1, max_output_tokens=1400),
                                )
                                testo_scuola = (risposta_scuola.text or "").strip()
                                if testo_scuola:
                                    st.markdown("#### Risultati web aggiuntivi")
                                    st.markdown(testo_scuola, unsafe_allow_html=False)
                                else:
                                    st.caption("La ricerca automatica non ha restituito testo; usa il collegamento web qui sopra.")
                            else:
                                st.caption("Il motore web non ha restituito risultati leggibili. Il collegamento sopra consente di proseguire manualmente.")
                        except Exception as exc:
                            dettaglio = str(exc)
                            if "QUOTA_GIORNALIERA" in dettaglio:
                                st.warning("⏳ Limite temporaneo Gemini: " + dettaglio.replace("QUOTA_GIORNALIERA:", ""))
                            elif "429" in dettaglio or "RESOURCE_EXHAUSTED" in dettaglio:
                                st.warning("⏳ Quota o limite temporaneo Gemini raggiunto. La ricerca nei CSV resta disponibile e il collegamento web sopra funziona indipendentemente da Gemini.")
                            else:
                                st.caption(f"Ricerca automatica aggiuntiva non riuscita ({dettaglio[:250]}). Puoi usare il collegamento web sopra.")
            except Exception as exc:
                st.error(f"Errore durante la lettura degli archivi scolastici: {str(exc)[:300]}")

    st.info(
        "Nota: il codice meccanografico può cambiare tra istituto principale e plessi. "
        "Controlla sempre la fonte ufficiale prima di utilizzare i dati in documenti amministrativi."
    )

elif strumento == "Crea modulo PDF compilabile":
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
                        risposta_modulo = genera_con_attesa(
                            client, modello=MODEL_NAME, contenuti=prompt_modulo,
                            configurazione=types.GenerateContentConfig(
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
                    dettaglio = str(exc)
                    if "QUOTA_GIORNALIERA" in dettaglio:
                        st.warning("⏳ Limite temporaneo di Gemini raggiunto. " + dettaglio.replace("QUOTA_GIORNALIERA:", ""))
                    elif "429" in dettaglio or "RESOURCE_EXHAUSTED" in dettaglio:
                        st.warning("⏳ Gemini è momentaneamente occupato. Attendi un po' e riprova.")
                    else:
                        st.error("Non è stato possibile generare la bozza. Controlla la connessione e i Secrets.")
                        st.caption(dettaglio[:500])

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
                    # Il livello gratuito di Gemini 3.5 Flash-Lite non include Google Search grounding.
                    # Le richieste normali e le azioni rapide usano quindi il modello senza tool grounding.
                    configurazione = types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.2,
                        max_output_tokens=1400 if ricerca_web_azione_rapida else 900,
                    )

                    risposta = genera_con_attesa(
                        client, modello=MODEL_NAME, contenuti=contenuti,
                        configurazione=configurazione,
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
                    dettaglio = str(exc)
                    if "QUOTA_GIORNALIERA" in dettaglio:
                        st.warning("⏳ Limite temporaneo di Gemini raggiunto. " + dettaglio.replace("QUOTA_GIORNALIERA:", ""))
                    elif "429" in dettaglio or "RESOURCE_EXHAUSTED" in dettaglio:
                        st.warning("⏳ Troppe richieste in questo momento. Attendi qualche secondo e riprova.")
                    else:
                        st.error("Si è verificato un problema durante la richiesta a Gemini. Verifica chiave API e modello.")
                        st.caption(dettaglio[:500])
