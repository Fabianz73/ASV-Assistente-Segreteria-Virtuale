import hashlib, io, os, re, unicodedata
from urllib.parse import quote_plus
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

st.set_page_config(page_title="AVS - Assistente Virtuale Scolastico", page_icon="🏫", layout="wide")
MODEL_NAME = "gemini-2.5-flash"

SIGLE_PROVINCE = {
    "AG": "AGRIGENTO", "AL": "ALESSANDRIA", "AN": "ANCONA", "AO": "AOSTA", "AR": "AREZZO",
    "AP": "ASCOLI PICENO", "AT": "ASTI", "AV": "AVELLINO", "BA": "BARI", "BT": "BARLETTA-ANDRIA-TRANI",
    "BL": "BELLUNO", "BN": "BENEVENTO", "BG": "BERGAMO", "BI": "BIELLA", "BO": "BOLOGNA",
    "BZ": "BOLZANO", "BS": "BRESCIA", "BR": "BRINDISI", "CA": "CAGLIARI", "CL": "CALTANISSETTA",
    "CB": "CAMPOBASSO", "CE": "CASERTA", "CT": "CATANIA", "CZ": "CATANZARO", "CH": "CHIETI",
    "CO": "COMO", "CS": "COSENZA", "CR": "CREMONA", "KR": "CROTONE", "CN": "CUNEO",
    "EN": "ENNA", "FM": "FERMO", "FE": "FERRARA", "FI": "FIRENZE", "FG": "FOGGIA",
    "FC": "FORLI'-CESENA", "FR": "FROSINONE", "GE": "GENOVA", "GO": "GORIZIA", "GR": "GROSSETO",
    "IM": "IMPERIA", "IS": "ISERNIA", "AQ": "L'AQUILA", "SP": "LA SPEZIA", "LT": "LATINA",
    "LE": "LECCE", "LC": "LECCO", "LI": "LIVORNO", "LO": "LODI", "LU": "LUCCA",
    "MC": "MACERATA", "MN": "MANTOVA", "MS": "MASSA-CARRARA", "MT": "MATERA", "ME": "MESSINA",
    "MI": "MILANO", "MO": "MODENA", "MB": "MONZA E BRIANZA", "NA": "NAPOLI", "NO": "NOVARA",
    "NU": "NUORO", "OR": "ORISTANO", "PD": "PADOVA", "PA": "PALERMO", "PR": "PARMA",
    "PV": "PAVIA", "PG": "PERUGIA", "PU": "PESARO E URBINO", "PE": "PESCARA", "PC": "PIACENZA",
    "PI": "PISA", "PT": "PISTOIA", "PN": "PORDENONE", "PZ": "POTENZA", "PO": "PRATO",
    "RG": "RAGUSA", "RA": "RAVENNA", "RC": "REGGIO CALABRIA", "RE": "REGGIO EMILIA", "RI": "RIETI",
    "RN": "RIMINI", "RM": "ROMA", "RO": "ROVIGO", "SA": "SALERNO", "SS": "SASSARI",
    "SV": "SAVONA", "SI": "SIENA", "SR": "SIRACUSA", "SO": "SONDRIO", "SU": "SUD SARDEGNA",
    "TA": "TARANTO", "TE": "TERAMO", "TR": "TERNI", "TO": "TORINO", "TP": "TRAPANI",
    "TN": "TRENTO", "TV": "TREVISO", "TS": "TRIESTE", "UD": "UDINE", "VA": "VARESE",
    "VE": "VENEZIA", "VB": "VERBANO-CUSIO-OSSOLA", "VC": "VERCELLI", "VR": "VERONA",
    "VV": "VIBO VALENTIA", "VI": "VICENZA", "VT": "VITERBO",
}

@st.cache_resource
def get_gemini_client(api_key):
    return genai.Client(api_key=api_key)

def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except (KeyError, FileNotFoundError):
        return os.getenv("GEMINI_API_KEY")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@400;500;600;700;800;900&display=swap');
:root{--lav:#8172B8;--lavd:#62548F;--lavp:#F1EDFA;--sage:#6F9D8C;--sagep:#EAF4EF;--cream:#FBF9F6;--ink:#302D38;--muted:#77727F;--border:#E6E0EA}
html,body,[class*="css"],[data-testid="stAppViewContainer"]{font-family:'Nunito Sans',sans-serif;color:var(--ink)}
[data-testid="stAppViewContainer"]{background:var(--cream)}
[data-testid="stHeader"]{background:rgba(251,249,246,0.92)}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#F3EFFA 0%,#F8F6F3 58%,#EEF5F0 100%);border-right:1px solid var(--border)}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{color:var(--ink);font-weight:800;letter-spacing:-0.025em}
h1,h2,h3{font-family:'Nunito Sans',sans-serif!important;color:var(--ink);font-weight:800!important;letter-spacing:-0.035em}
h1{line-height:1.18}
p,label,li,.stMarkdown,.stCaption{font-family:'Nunito Sans',sans-serif}
[data-testid="stCaptionContainer"] p{color:var(--muted);font-size:0.94rem}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{line-height:1.6}
.stButton>button,.stDownloadButton>button,.stLinkButton>a,[data-testid="stFormSubmitButton"] button{border-radius:13px;border:1px solid #DED6E8;background:#FFF;color:var(--lavd);font-family:'Nunito Sans',sans-serif;font-weight:700;transition:all .18s ease;box-shadow:0 2px 7px rgba(65,48,87,.04)}
.stButton>button:hover,.stDownloadButton>button:hover,.stLinkButton>a:hover,[data-testid="stFormSubmitButton"] button:hover{border-color:var(--lav);background:var(--lavp);color:#493B75;transform:translateY(-1px)}
[data-testid="stFormSubmitButton"] button,.stDownloadButton>button{background:var(--lav);border-color:var(--lav);color:#FFF}
[data-testid="stFormSubmitButton"] button:hover,.stDownloadButton>button:hover{background:var(--lavd);color:#FFF}
.stTextInput input,.stTextArea textarea,.stSelectbox [data-baseweb="select"],.stMultiSelect [data-baseweb="select"]{border-radius:12px;border-color:#DCD5E4;background:#FFF}
.stTextInput input:focus,.stTextArea textarea:focus{border-color:var(--lav);box-shadow:0 0 0 2px rgba(129,114,184,.14)}
[data-testid="stChatMessage"]{border:1px solid var(--border);border-radius:18px;padding:1rem 1.15rem;background:#FFF;box-shadow:0 3px 12px rgba(55,45,68,.035)}
[data-testid="stChatInput"]{border-radius:16px;border-color:#DCD5E4;background:#FFF;box-shadow:0 4px 18px rgba(55,45,68,.06)}
[data-testid="stExpander"]{border:1px solid var(--border);border-radius:14px;background:rgba(255,255,255,.78)}
[data-testid="stAlert"]{border-radius:14px}
.trappola-box{background:#FFF0ED;border-left:5px solid #C96D61;padding:15px 17px;border-radius:12px;margin:15px 0;color:#843E37;font-weight:700;font-size:1.02em}
.risposta-diretta{background:var(--sagep);border-left:5px solid var(--sage);padding:15px 17px;border-radius:12px;margin-top:20px;color:#285B49;font-weight:700;font-size:1.02em}
[data-testid="stRadio"] label{border-radius:10px}
hr{border-color:var(--border)}
@media (max-width:768px){h1{font-size:1.8rem!important}[data-testid="stChatMessage"]{padding:.8rem}}
</style>
""", unsafe_allow_html=True)

SYSTEM_PROMPT = """
Sei AVS, Assistente Virtuale Scolastico per le segreterie scolastiche italiane.
Rispondi in italiano, in modo pratico, chiaro e conciso.
ACCURATEZZA:
- Non inventare leggi, circolari, date, link o procedure.
- Non dire di aver consultato siti se non hai davvero effettuato una ricerca.
- Se non puoi verificare l'attualità di una norma, dichiaralo e indica di controllare le fonti ufficiali: MIM (mim.gov.it), Normattiva (normattiva.it), Gazzetta Ufficiale (gazzettaufficiale.it) e ARAN (aranagenzia.it).
- Distingui gli obblighi normativi dalle prassi che possono variare da scuola a scuola.
- Se l'utente chiede informazioni su una scuola specifica, chiedi nome e località prima di rispondere.
FORMATO:
- Parti dalla risposta concreta, senza introduzioni o saluti.
- Per le procedure, usa al massimo 3-4 passaggi brevi e spiega le sigle necessarie.
- Quando utile, indica i riferimenti normativi solo se li conosci con sufficiente sicurezza.
- Termina con: [TRAPPOLE] l'errore principale da evitare [/TRAPPOLE]
- Termina inoltre con: [DIRETTA] l'azione concreta da fare, in 1-2 righe [/DIRETTA]
- Se l'utente chiede una mail, fornisci una bozza pronta da copiare.
- Se chiede un modulo/documento da creare in PDF, racchiudilo tra [MODULO_PDF] e [/MODULO_PDF] e usa segnaposto come [NOME_COGNOME] per i campi compilabili.
- Non creare un modulo PDF se non è richiesto.
- Evita ripetizioni, spiegazioni lunghe e linguaggio burocratico superfluo.
"""

def nome_campo_sicuro(testo, indice):
    t = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^A-Za-z0-9_]+", "_", t).strip("_")
    return f"campo_{indice}_{t[:24] or 'testo'}"

def normalizza_url(url):
    if not isinstance(url, str):
        return None
    u = url.strip().split(";")[0].strip()
    if not u or u.lower() in {"nan", "none", "null", "-", "n.d.", "nd"}:
        return None
    if not re.match(r"^https?://", u, re.IGNORECASE):
        u = "https://" + u
    if re.match(r"^https?://[^\s]+$", u, re.IGNORECASE):
        return u
    return None

def crea_pdf_editabile(testo_modulo, intestazione_istituto="ISTITUTO SCOLASTICO - SEGRETERIA AMMINISTRATIVA"):
    if not testo_modulo or not testo_modulo.strip():
        raise ValueError("Il testo del modulo è vuoto.")
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    larghezza, altezza = A4
    ms, md = 50, 50
    lt = larghezza - ms - md
    y = altezza - 82
    num = 0
    titolo_header = (intestazione_istituto or "ISTITUTO SCOLASTICO - SEGRETERIA AMMINISTRATIVA").strip().upper()[:85]

    def intestazione():
        pdf.setFont("Helvetica-Bold", 9.5)
        pdf.drawString(ms, altezza - 40, titolo_header)
        pdf.setStrokeColor(colors.grey)
        pdf.line(ms, altezza - 50, larghezza - md, altezza - 50)

    def nuova_pagina():
        nonlocal y
        pdf.showPage()
        intestazione()
        y = altezza - 72

    def disegna(testo, font="Helvetica", dim=10):
        nonlocal y
        linea = ""
        for parola in testo.split():
            cand = f"{linea} {parola}".strip()
            if pdf.stringWidth(cand, font, dim) <= lt:
                linea = cand
            else:
                if linea:
                    pdf.setFont(font, dim)
                    pdf.drawString(ms, y, linea)
                    y -= 15
                    if y < 65:
                        nuova_pagina()
                linea = parola
        if linea:
            pdf.setFont(font, dim)
            pdf.drawString(ms, y, linea)
            y -= 17
            if y < 65:
                nuova_pagina()

    intestazione()
    for i, riga_orig in enumerate(testo_modulo.strip().splitlines()):
        riga = riga_orig.strip()
        if not riga:
            y -= 12
            if y < 65:
                nuova_pagina()
            continue
        if y < 70:
            nuova_pagina()
        if i == 0:
            pdf.setFont("Helvetica-Bold", 13)
            linea = ""
            for parola in riga.split():
                cand = f"{linea} {parola}".strip()
                if pdf.stringWidth(cand, "Helvetica-Bold", 13) <= lt:
                    linea = cand
                else:
                    pdf.drawString(ms, y, linea)
                    y -= 18
                    linea = parola
            if linea:
                pdf.drawString(ms, y, linea)
                y -= 26
            continue
        parti = re.split(r"(\[[^\]]+\])", riga)
        pdf.setFont("Helvetica", 10)
        corrente = ""
        for parte in parti:
            if parte.startswith("[") and parte.endswith("]"):
                if corrente.strip():
                    disegna(corrente.strip())
                    corrente = ""
                etichetta = parte[1:-1].strip() or "Campo"
                pdf.setFont("Helvetica", 9)
                pdf.drawString(ms, y, f"{etichetta}:")
                y -= 19
                if y < 75:
                    nuova_pagina()
                num += 1
                pdf.acroForm.textfield(
                    name=nome_campo_sicuro(etichetta, num),
                    tooltip=etichetta,
                    x=ms,
                    y=y - 3,
                    width=lt,
                    height=20,
                    borderStyle="underlined",
                    borderWidth=1,
                    borderColor=colors.darkblue,
                    fillColor=colors.Color(.97, .98, 1),
                    textColor=colors.black,
                    forceBorder=True,
                    fontName="Helvetica",
                    fontSize=10,
                )
                y -= 29
                if y < 65:
                    nuova_pagina()
            else:
                corrente += parte
        if corrente.strip():
            disegna(corrente.strip())
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()

@st.cache_data
def carica_dati_scuole():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_sorgenti = [
        (os.path.join(script_dir, "SCUANAGRAFESTAT20262720260901.csv"), "STATALE"),
        (os.path.join(script_dir, "SCUANAGRAFEPAR20262720260901.csv"), "PARITARIA"),
    ]
    dfs = []
    for file_path, tipo_gestione in file_sorgenti:
        if not os.path.exists(file_path):
            continue
        try:
            try:
                df = pd.read_csv(file_path, encoding="latin-1", sep=",")
                if len(df.columns) == 1:
                    raise ValueError
            except Exception:
                df = pd.read_csv(file_path, encoding="latin-1", sep=";")
            for col in ["DENOMINAZIONESCUOLA", "DESCRIZIONECOMUNE", "CODICESCUOLA", "REGIONE", "PROVINCIA"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()
            df["TIPO_GESTIONE_AVS"] = tipo_gestione
            dfs.append(df)
        except Exception as e:
            st.warning(f"Impossibile leggere {file_path}: {e}")

    if not dfs:
        st.error("Nessun file CSV trovato. Carica i file su GitHub.")
        return None

    return pd.concat(dfs, ignore_index=True)

def cerca_scuole(query, regione=None, provincia=None, solo_paritarie=False, limite=100):
    df = carica_dati_scuole()
    if df is None:
        return [], "Impossibile caricare i dati delle scuole."

    if query and query.strip():
        q = query.strip()
        m_nome = df["DENOMINAZIONESCUOLA"].str.contains(q, case=False, na=False, regex=False)
        m_comune = df["DESCRIZIONECOMUNE"].str.contains(q, case=False, na=False, regex=False)
        m_codice = df["CODICESCUOLA"].str.contains(q, case=False, na=False, regex=False)
        df = df[m_nome | m_comune | m_codice]

    if regione:
        df = df[df["REGIONE"].str.upper() == regione.strip().upper()]

    if provincia and provincia.strip():
        p_in = provincia.strip().upper()
        p_estesa = SIGLE_PROVINCE.get(p_in, p_in)
        prov_col = df["PROVINCIA"].str.upper()
        df = df[(prov_col == p_in) | (prov_col == p_estesa) | prov_col.str.contains(p_estesa, na=False, regex=False)]

    if solo_paritarie:
        df = df[df["TIPO_GESTIONE_AVS"] == "PARITARIA"]

    totale_trovate = len(df)
    risultati = df.head(limite).to_dict("records")
    return risultati, (totale_trovate if totale_trovate > limite else None)

def trova_sito_scuola(record):
    possibili_colonne = (
        "URLSITOWEBSCUOLA",
        "SITOWEBSCUOLA",
        "SITO_WEB_SCUOLA",
        "SITOWEB",
        "URLSITO",
        "SITO_INTERNET",
        "SITOWEBISTITUZIONALE",
    )
    record_normalizzato = {
        re.sub(r"[^A-Z0-9]", "", str(k).upper()): v
        for k, v in record.items()
    }
    chiavi_da_provare = [re.sub(r"[^A-Z0-9]", "", c.upper()) for c in possibili_colonne]
    chiavi_da_provare.extend(
        chiave for chiave in record_normalizzato
        if chiave not in chiavi_da_provare
        and (("SITO" in chiave and ("WEB" in chiave or "SCUOLA" in chiave))
             or ("URL" in chiave and ("SCUOLA" in chiave or "SITO" in chiave)))
    )
    for chiave in chiavi_da_provare:
        valore = record_normalizzato.get(chiave)
        if valore is None or pd.isna(valore):
            continue
        url_valido = normalizza_url(str(valore))
        if url_valido:
            return url_valido
    return None

def formatta_e_mostra(testo, indice_msg):
    testo_pulito = testo or ""
    m_trappola = re.search(r"\[TRAPPOLE\](.*?)\[/TRAPPOLE\]", testo_pulito, re.DOTALL | re.IGNORECASE)
    trappola_html = ""
    if m_trappola:
        trappola_html = '<div class="trappola-box">🚨 ERRORE DA EVITARE: ' + m_trappola.group(1).strip() + "</div>"
        testo_pulito = testo_pulito.replace(m_trappola.group(0), "")
    m_modulo = re.search(r"\[MODULO_PDF\](.*?)\[/MODULO_PDF\]", testo_pulito, re.DOTALL | re.IGNORECASE)
    testo_modulo = None
    if m_modulo:
        testo_modulo = m_modulo.group(1).strip()
        testo_pulito = testo_pulito.replace(m_modulo.group(0), "\n\n**📄 Modulo generato e pronto per il download qui sotto.**\n\n")
    m_diretta = re.search(r"\[DIRETTA\](.*?)\[/DIRETTA\]", testo_pulito, re.DOTALL | re.IGNORECASE)
    diretta_html = ""
    if m_diretta:
        diretta_html = '<div class="risposta-diretta">✅ RISPOSTA DIRETTA: ' + m_diretta.group(1).strip() + "</div>"
        testo_pulito = testo_pulito.replace(m_diretta.group(0), "")
    if testo_pulito.strip():
        st.markdown(testo_pulito.strip())
    if trappola_html:
        st.markdown(trappola_html, unsafe_allow_html=True)
    if testo_modulo:
        with st.expander("Anteprima del testo del modulo", expanded=False):
            st.text(testo_modulo)
        try:
            intestazione = st.session_state.get("intestazione_istituto", "")
            pdf_bytes = crea_pdf_editabile(testo_modulo, intestazione_istituto=intestazione)
            h = hashlib.md5(testo_modulo.encode()).hexdigest()[:8]
            st.download_button(
                label="📥 Scarica PDF compilabile",
                data=pdf_bytes,
                file_name=f"Modulo_Segreteria_{h}.pdf",
                mime="application/pdf",
                key=f"btn_pdf_{indice_msg}_{h}",
            )
        except Exception as exc:
            st.error(f"Non è stato possibile generare il PDF: {exc}")
    if diretta_html:
        st.markdown(diretta_html, unsafe_allow_html=True)

st.title("🏫 AVS Office")
st.caption("Assistente Virtuale Scolastico · Un supporto pratico, chiaro e gentile per la segreteria")

if "anim_seed" not in st.session_state:
    st.session_state["anim_seed"] = 0

hero_iframe = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@400;700;800&display=swap" rel="stylesheet">
<style>
  body {{
    margin: 0;
    padding: 0;
    background: transparent;
    font-family: 'Nunito Sans', sans-serif;
  }}
  .hero {{
    position: relative;
    overflow: hidden;
    background: linear-gradient(115deg, #F0EBFA 0%, #F8F5FB 54%, #EAF4EF 100%);
    border: 1px solid #E6E0EA;
    border-radius: 18px;
    padding: 16px 22px 28px 22px;
    box-sizing: border-box;
  }}
  .decor {{
    position: absolute;
    right: 18px;
    top: 12px;
    color: rgba(98, 84, 143, 0.25);
    font-size: 16px;
    letter-spacing: 7px;
    pointer-events: none;
  }}
  .title {{
    font-size: 17px;
    font-weight: 800;
    color: #40384F;
  }}
  .sub {{
    font-size: 14.5px;
    color: #716B79;
    margin-top: 4px;
    padding-right: 110px;
  }}
  .track {{
    position: absolute;
    left: 16px;
    right: 16px;
    bottom: 4px;
    height: 26px;
    pointer-events: none;
  }}
  .mouse, .cat {{
    position: absolute;
    bottom: 0;
    line-height: 1;
    will-change: transform, opacity;
  }}
  .mouse {{
    right: 0;
    font-size: 17px;
    animation: run-mouse 4.2s ease-in-out 0.2s infinite;
  }}
  .cat {{
    right: 32px;
    font-size: 22px;
    animation: run-cat 4.2s ease-in-out 0.35s infinite;
  }}
  @keyframes run-mouse {{
    0% {{ transform: translateX(30px) translateY(0); opacity: 0; }}
    10% {{ opacity: 1; }}
    45% {{ transform: translateX(-180px) translateY(-3px); opacity: 1; }}
    80% {{ transform: translateX(-340px) translateY(0); opacity: 1; }}
    100% {{ transform: translateX(-420px) translateY(0); opacity: 0; }}
  }}
  @keyframes run-cat {{
    0% {{ transform: translateX(30px) translateY(0); opacity: 0; }}
    10% {{ opacity: 1; }}
    45% {{ transform: translateX(-165px) translateY(-4px); opacity: 1; }}
    80% {{ transform: translateX(-320px) translateY(0); opacity: 1; }}
    100% {{ transform: translateX(-400px) translateY(0); opacity: 0; }}
  }}
</style>
</head>
<body>
  <div class="hero" data-seed="{st.session_state['anim_seed']}">
    <div class="decor">✦ · ♡</div>
    <div class="title">La tua segreteria, un po’ più semplice ✨</div>
    <div class="sub">Procedure, risposte operative e moduli compilabili in un unico spazio.</div>
    <div class="track">
      <span class="mouse">🐭</span>
      <span class="cat">🐈</span>
    </div>
  </div>
</body>
</html>
"""
components.html(hero_iframe, height=106)

if "messaggi" not in st.session_state:
    st.session_state["messaggi"] = []
if "modulo_testo_editabile" not in st.session_state:
    st.session_state["modulo_testo_editabile"] = ""
if "modulo_guidato_pronto" not in st.session_state:
    st.session_state["modulo_guidato_pronto"] = False
if "intestazione_istituto" not in st.session_state:
    st.session_state["intestazione_istituto"] = "ISTITUTO SCOLASTICO - SEGRETERIA AMMINISTRATIVA"

with st.sidebar:
    st.header("🧰 Strumenti AVS")
    strumento = st.radio(
        "Che cosa vuoi fare?",
        ["Assistente segreteria", "Crea modulo PDF compilabile", "Cerca codici meccanografici"],
        key="strumento_avs",
    )
    st.divider()
    st.text_input(
        "🏫 Intestazione PDF del tuo istituto",
        key="intestazione_istituto",
        help="Viene stampata in alto in tutti i PDF generati. Puoi anche impostarla dalla ricerca scuole.",
    )
    st.divider()
    if strumento == "Assistente segreteria":
        st.header("⚡ Azioni rapide")
        st.markdown("Seleziona una procedura frequente per avviare la richiesta.")
        contesto = f"Istituto dell'utente: {st.session_state['intestazione_istituto']}. "
        istr = "Non inventare dati ufficiali non forniti e non dichiarare di averli verificati online. Usa segnaposto tra parentesi quadre per i dati mancanti. "
        if st.button("📋 Presa di servizio supplente", use_container_width=True):
            st.session_state["prompt_rapido"] = f"{contesto} {istr} Un docente supplente deve prendere servizio oggi ma ha la febbre e non può venire fisicamente a firmare. Come devo procedere? Prepara anche una bozza di modulo editabile per la presa di servizio."
        if st.button("🏥 Assenza per malattia ATA/docente", use_container_width=True):
            st.session_state["prompt_rapido"] = f"{contesto} {istr} Un docente mi ha comunicato stamattina di essere in malattia. Spiega i passaggi amministrativi da verificare su SIDI, Argo e NoiPA, distinguendo gli obblighi certi dalle procedure che dipendono dalla scuola."
        if st.button("✉️ Bozza convocazione interpello", use_container_width=True):
            st.session_state["prompt_rapido"] = f"{contesto} {istr} Devo inviare una convocazione urgente per supplenza breve tramite interpello. Prepara una mail formale e una bozza di modulo di accettazione editabile. Indica quali dati devo verificare prima dell'invio."
        st.divider()
        if st.button("🗑️ Nuova conversazione", use_container_width=True):
            st.session_state["messaggi"] = []
            st.rerun()
    elif strumento == "Crea modulo PDF compilabile":
        st.markdown("Descrivi il modulo che ti serve, controlla la bozza e scarica un PDF con campi compilabili.")
        if st.button("🗑️ Svuota bozza modulo", use_container_width=True):
            st.session_state["modulo_testo_editabile"] = ""
            st.session_state["modulo_guidato_pronto"] = False
            st.rerun()

if strumento == "Crea modulo PDF compilabile":
    st.subheader("📄 Crea un modulo PDF compilabile")
    st.write("Descrivi il documento che ti serve. AVS preparerà una bozza da controllare; potrai correggerla prima di scaricare il PDF.")
    categorie = ["Richiesta o istanza alla scuola", "Autorizzazione o consenso", "Delega", "Autodichiarazione", "Presa di servizio o documentazione del personale", "Verbale o scheda di rilevazione", "Altro modulo"]
    with st.form("form_modulo_guidato"):
        categoria = st.selectbox("Tipo di modulo", categorie)
        destinatario = st.text_input("A chi è destinato?", placeholder="Es. famiglie, docenti, personale ATA, dirigente scolastico")
        scopo = st.text_area("Che cosa deve permettere di fare il modulo?", placeholder="Descrivi la richiesta o la procedura. Non inserire dati personali reali.", height=100)
        campi_richiesti = st.text_area("Quali campi vuoi inserire? (facoltativo)", placeholder="Es. nome e cognome, classe, data, motivazione, firma", height=80)
        riferimenti = st.text_area("Indicazioni o testo da rispettare (facoltativo)", placeholder="Incolla eventuali istruzioni della scuola o riferimenti già verificati.", height=80)
        genera_bozza = st.form_submit_button("✨ Prepara la bozza con AVS", use_container_width=True)
    query = "modulo scolastico " + categoria
    if destinatario.strip():
        query += " " + destinatario.strip()
    if scopo.strip():
        query += " " + scopo.strip()
    st.link_button("🔎 Cerca modelli pubblicati online", "https://www.google.com/search?q=" + quote_plus(query + " sito scuola istituto MIM"), help="Apre una ricerca web in una nuova scheda. AVS non scarica né verifica automaticamente i risultati.", use_container_width=True)
    st.caption("I risultati online sono riferimenti da controllare: un modello di un'altra scuola non è automaticamente ufficiale o adatto al tuo istituto.")
    if genera_bozza:
        if not scopo.strip():
            st.warning("Descrivi brevemente lo scopo del modulo prima di generare la bozza.")
        else:
            api_key = get_api_key()
            if not api_key:
                st.error("Chiave API mancante. Configura GEMINI_API_KEY nei Secrets di Streamlit Cloud.")
            else:
                prompt_modulo = f"""Prepara una BOZZA di modulo amministrativo per una scuola italiana.
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
- Mantieni il documento pratico e conciso."""
                try:
                    with st.spinner("AVS sta preparando la bozza..."):
                        client = get_gemini_client(api_key)
                        risposta_modulo = client.models.generate_content(
                            model=MODEL_NAME,
                            contents=prompt_modulo,
                            config=types.GenerateContentConfig(
                                system_instruction="Sei AVS, assistente per le segreterie scolastiche italiane. Genera bozze prudenti, chiare e pratiche. Non inventare norme o dichiarare ufficiale un modello generato.",
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
                    st.error("Non è stato possibile generare la bozza. Controlla la connessione e la configurazione di Gemini.")
                    st.code(str(exc))
    if st.session_state["modulo_guidato_pronto"] or st.session_state["modulo_testo_editabile"]:
        st.divider()
        st.subheader("2. Controlla e correggi la bozza")
        st.info("Controlla il testo e i riferimenti prima dell'uso. Le parole tra parentesi quadre diventeranno campi compilabili nel PDF.")
        testo_modulo_finale = st.text_area("Testo del modulo (puoi modificarlo prima di generare il PDF)", key="editor_modulo", value=st.session_state["modulo_testo_editabile"], height=380)
        if testo_modulo_finale.strip():
            try:
                pdf_bytes = crea_pdf_editabile(testo_modulo_finale, intestazione_istituto=st.session_state["intestazione_istituto"])
                st.download_button(label="📥 Scarica PDF compilabile", data=pdf_bytes, file_name="AVS_modulo_compilabile.pdf", mime="application/pdf", key="download_pdf_guidato", use_container_width=True)
            except Exception as exc:
                st.error(f"Non è stato possibile generare il PDF: {exc}")
        st.caption("Nota: la compatibilità dei campi compilabili dipende dal lettore PDF usato, soprattutto su smartphone. Prova il file prima di distribuirlo.")

elif strumento == "Cerca codici meccanografici":
    st.subheader("🔍 Cerca codici meccanografici")
    st.write("Cerca per nome scuola, comune o codice meccanografico. I dati provengono dal dataset ufficiale del Ministero.")
    col1, col2, col3 = st.columns([2, 1.5, 1])
    with col1:
        query_scuola = st.text_input("Nome scuola, comune o codice", placeholder="Es. Ghiberti, Firenze, FIIS...")
    with col2:
        regioni = {
            "Tutte": None,
            "ABRUZZO": "ABRUZZO", "BASILICATA": "BASILICATA", "CALABRIA": "CALABRIA",
            "CAMPANIA": "CAMPANIA", "EMILIA ROMAGNA": "EMILIA ROMAGNA",
            "FRIULI-VENEZIA G.": "FRIULI-VENEZIA G.", "LAZIO": "LAZIO", "LIGURIA": "LIGURIA",
            "LOMBARDIA": "LOMBARDIA", "MARCHE": "MARCHE", "MOLISE": "MOLISE",
            "PIEMONTE": "PIEMONTE", "PUGLIA": "PUGLIA", "SARDEGNA": "SARDEGNA",
            "SICILIA": "SICILIA", "TOSCANA": "TOSCANA", "TRENTINO ALTO ADIGE": "TRENTINO ALTO ADIGE",
            "UMBRIA": "UMBRIA", "VALLE D'AOSTA": "VALLE D'AOSTA", "VENETO": "VENETO",
        }
        regione_sel = st.selectbox("Regione (facoltativo)", list(regioni.keys()))
    with col3:
        provincia_sel = st.text_input("Provincia (sigla o nome)", placeholder="Es. FI o FIRENZE")
    solo_paritarie = st.checkbox("Solo scuole paritarie", value=False)

    if st.button("🔎 Cerca", use_container_width=True):
        if not query_scuola.strip() and regione_sel == "Tutte" and not provincia_sel.strip() and not solo_paritarie:
            st.warning("Inserisci almeno un criterio di ricerca.")
        else:
            with st.spinner("Ricerca in corso..."):
                scuole, troncati = cerca_scuole(query_scuola, regioni.get(regione_sel), provincia_sel, solo_paritarie)
            if isinstance(troncati, str):
                st.error(f"Errore: {troncati}")
            elif not scuole:
                st.info("Nessuna scuola trovata.")
                st.session_state["risultati_scuole"] = []
            else:
                st.session_state["risultati_scuole"] = scuole
                st.session_state["risultati_troncati"] = troncati

    scuole = st.session_state.get("risultati_scuole", [])
    troncati = st.session_state.get("risultati_troncati")
    if scuole:
        msg_ris = f"Mostrate {len(scuole)} scuole" + (f" (su {troncati} totali: affina la ricerca)." if troncati else ".")
        st.success(msg_ris)

        df_export = pd.DataFrame(scuole)
        csv_export = df_export.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button("📊 Esporta elenco in CSV (Excel)", data=csv_export, file_name="elenco_scuole_avs.csv", mime="text/csv")

        scuole_per_comune = {}
        for s in scuole:
            comune = s.get("DESCRIZIONECOMUNE", "Comune sconosciuto")
            scuole_per_comune.setdefault(comune, []).append(s)

        for comune in sorted(scuole_per_comune.keys()):
            st.markdown(f"### 📍 {comune}")
            for idx_s, s in enumerate(scuole_per_comune[comune]):
                codice = s.get("CODICESCUOLA", "")
                denominazione = s.get("DENOMINAZIONESCUOLA", "")
                provincia = s.get("PROVINCIA", "")
                email = s.get("INDIRIZZOEMAILSCUOLA", "")
                pec = s.get("INDIRIZZOPECSCUOLA", "")
                indirizzo = s.get("INDIRIZZOSCUOLA", "")
                tipo_g = s.get("TIPO_GESTIONE_AVS", "")
                sito_scuola = trova_sito_scuola(s)
                query_google = quote_plus(f'"{denominazione}" "{comune}" sito ufficiale scuola')
                link_google = f"https://www.google.com/search?q={query_google}"

                with st.expander(f"{denominazione} ({codice}) · {tipo_g} - {indirizzo}, {comune} ({provincia})"):
                    st.write(f"**Codice meccanografico:** {codice}")
                    st.write(f"**Indirizzo:** {indirizzo} - {comune} ({provincia})")
                    st.write(f"**Email:** {email}")
                    st.write(f"**PEC:** {pec}")
                    st.divider()

                    col_sito, col_google = st.columns(2)
                    with col_sito:
                        if sito_scuola:
                            st.link_button("🌐 Apri il sito della scuola", sito_scuola, use_container_width=True)
                        else:
                            st.caption("Sito diretto non presente nei dati disponibili.")
                    with col_google:
                        st.link_button("🔎 Cerca il sito su Google", link_google, use_container_width=True)
                    st.caption("Il link Google apre una ricerca per nome della scuola e comune: verifica che il risultato sia il sito ufficiale prima di usarlo.")

                    col_act1, col_act2 = st.columns(2)
                    with col_act1:
                        if st.button("📌 Imposta come mia scuola", key=f"set_mio_{codice}_{idx_s}", use_container_width=True):
                            st.session_state["intestazione_istituto"] = f"{denominazione} ({codice}) - {comune}"
                            st.toast("Intestazione aggiornata per tutti i PDF!")
                    with col_act2:
                        if st.button("✉️ Scrivi mail a questa scuola", key=f"mail_{codice}_{idx_s}", use_container_width=True):
                            st.session_state["prompt_rapido"] = (
                                f"Prepara una bozza di comunicazione ufficiale via PEC/email indirizzata a:\n"
                                f"- Scuola: {denominazione} (Cod. Mecc. {codice})\n"
                                f"- Indirizzo: {indirizzo}, {comune} ({provincia})\n"
                                f"- PEC: {pec} | Email: {email}\n"
                                f"Oggetto da completare: [OGGETTO_COMUNICAZIONE, es. richiesta nulla osta / trasmissione fascicolo alunno]. "
                                f"Mittente: {st.session_state['intestazione_istituto']}."
                            )
                            st.session_state["strumento_avs"] = "Assistente segreteria"
                            st.rerun()

        st.caption("Fonte dei dati anagrafici: Open Data del Ministero dell'Istruzione e del Merito. I siti web sono mostrati solo se presenti nel CSV; la ricerca Google è un'alternativa e non costituisce una verifica automatica.")

else:
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
                    api_key = get_api_key()
                    if not api_key:
                        raise ValueError("Chiave API mancante. Configura GEMINI_API_KEY nei Secrets di Streamlit Cloud.")
                    client = get_gemini_client(api_key)
                    contenuti = []
                    for m in st.session_state["messaggi"][-6:]:
                        ruolo = "model" if m["role"] == "assistant" else "user"
                        contenuti.append({"role": ruolo, "parts": [{"text": m["content"]}]})
                    configurazione = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.2, max_output_tokens=1100)
                    risposta = client.models.generate_content(model=MODEL_NAME, contents=contenuti, config=configurazione)
                    try:
                        testo_risposta = (risposta.text or "").strip()
                    except ValueError:
                        testo_risposta = "La risposta è stata bloccata dai filtri di sicurezza. Riformula la domanda in modo più neutro."
                    if not testo_risposta:
                        testo_risposta = "Non è arrivato testo nella risposta del modello. Riprova con una domanda più specifica."
                    formatta_e_mostra(testo_risposta, len(st.session_state["messaggi"]))
                    st.session_state["messaggi"].append({"role": "assistant", "content": testo_risposta})
                except Exception as exc:
                    st.error("Si è verificato un problema durante la richiesta a Gemini. Controlla la chiave API, la connessione e il nome del modello.")
                    st.code(str(exc))

