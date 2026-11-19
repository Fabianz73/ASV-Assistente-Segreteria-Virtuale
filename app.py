import hashlib, io, re, unicodedata
from urllib.parse import quote_plus
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
 
st.set_page_config(page_title="AVS - Assistente Virtuale Scolastico", page_icon="🏫", layout="wide")
MODEL_NAME = "gemini-2.0-flash"  # verificare che il modello sia disponibile nel proprio account
 
@st.cache_resource
def get_gemini_client(api_key):
    return genai.Client(api_key=api_key)
 
def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except (KeyError, FileNotFoundError):
        return None
 
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
.avs-hero{position:relative;overflow:hidden;isolation:isolate}
.avs-hero::after{content:"✦   ·   ♡";position:absolute;right:18px;top:12px;color:rgba(98,84,143,.20);font-size:1.05rem;letter-spacing:7px;pointer-events:none;z-index:-1}
.avs-cat-chase{position:absolute;right:13px;bottom:9px;width:145px;height:32px;pointer-events:none;user-select:none;opacity:.88}
.avs-cat-chase .avs-mouse,.avs-cat-chase .avs-cat{position:absolute;bottom:0;display:inline-block;line-height:1;filter:saturate(.78);will-change:transform,opacity}
.avs-cat-chase .avs-mouse{right:7px;font-size:17px;animation:avs-mouse-run 2.7s ease-in-out .15s 1 both}
.avs-cat-chase .avs-cat{right:24px;font-size:23px;animation:avs-cat-run 2.7s ease-in-out 1 both}
@keyframes avs-mouse-run{0%{transform:translateX(0);opacity:0}8%{opacity:.82}55%{transform:translateX(-100px) translateY(-2px);opacity:.82}76%{transform:translateX(-118px) translateY(0);opacity:.7}100%{transform:translateX(-145px);opacity:0}}
@keyframes avs-cat-run{0%{transform:translateX(0);opacity:0}10%{opacity:.9}54%{transform:translateX(-90px) translateY(-3px);opacity:.9}76%{transform:translateX(-111px) translateY(0);opacity:.78}100%{transform:translateX(-142px);opacity:0}}
@media (prefers-reduced-motion:reduce){.avs-cat-chase{display:none!important}*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important}}
[data-testid="stRadio"] label{border-radius:10px}
hr{border-color:var(--border)}
@media (max-width:768px){.avs-cat-chase{right:8px;bottom:5px;transform:scale(.82);transform-origin:bottom right}h1{font-size:1.8rem!important}[data-testid="stChatMessage"]{padding:.8rem}}
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
    """Restituisce un URL cliccabile valido, oppure None se il campo è vuoto/non valido."""
    if not isinstance(url, str):
        return None
    u = url.strip().split(";")[0].strip()
    if not u or u.lower() in {"nan", "none", "-", "n.d.", "nd"}:
        return None
    if not re.match(r"^https?://", u, re.IGNORECASE):
        u = "https://" + u
    return u
 
def crea_pdf_editabile(testo_modulo):
    if not testo_modulo or not testo_modulo.strip():
        raise ValueError("Il testo del modulo è vuoto.")
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    larghezza, altezza = A4
    ms, md = 50, 50
    lt = larghezza - ms - md
    y = altezza - 82
    num = 0
 
    def intestazione():
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(ms, altezza - 40, "ISTITUTO SCOLASTICO STATALE - SEGRETERIA AMMINISTRATIVA")
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
                pdf.acroForm.textfield(name=nome_campo_sicuro(etichetta, num), tooltip=etichetta, x=ms, y=y - 3, width=lt, height=20, borderStyle="underlined", borderWidth=1, borderColor=colors.darkblue, fillColor=colors.Color(.97, .98, 1), textColor=colors.black, forceBorder=True, fontName="Helvetica", fontSize=10)
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
    """Carica e unisce i dati delle scuole statali e paritarie dai file CSV."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
 
    file_statali = os.path.join(script_dir, "SCUANAGRAFESTAT20262720260901.csv")
    file_paritarie = os.path.join(script_dir, "SCUANAGRAFEPAR20262720260901.csv")
 
    dfs = []
    for file_path in [file_statali, file_paritarie]:
        if not os.path.exists(file_path):
            continue
        try:
            try:
                df = pd.read_csv(file_path, encoding='latin-1', sep=',')
                if len(df.columns) == 1:
                    raise ValueError
            except Exception:
                df = pd.read_csv(file_path, encoding='latin-1', sep=';')
            dfs.append(df)
        except Exception as e:
            st.warning(f"Impossibile leggere {file_path}: {e}")
 
    if not dfs:
        st.error("Nessun file CSV trovato. Carica i file su GitHub.")
        return None
 
    df_totale = pd.concat(dfs, ignore_index=True)
    return df_totale
 
def cerca_scuole(query, regione=None, solo_paritarie=False):
    """Cerca scuole nei dati locali."""
    df = carica_dati_scuole()
    if df is None:
        return [], "Impossibile caricare i dati delle scuole."
 
    colonne_attese = ["DENOMINAZIONESCUOLA", "REGIONE", "DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA"]
    mancanti = [c for c in colonne_attese if c not in df.columns]
    if mancanti:
        return [], f"Colonne mancanti nel CSV: {', '.join(mancanti)}"
 
    if query:
        maschera_nome = df['DENOMINAZIONESCUOLA'].astype(str).str.contains(query, case=False, na=False)
        df = df[maschera_nome]
 
    if regione:
        maschera_regione = df['REGIONE'].astype(str).str.upper() == regione.upper()
        df = df[maschera_regione]
 
    if solo_paritarie:
        df = df[df['DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA'].astype(str).str.contains('NON STATALE', case=False, na=False)]
 
    df = df.head(50)
    risultati = df.to_dict('records')
    return risultati, None
 
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
            pdf_bytes = crea_pdf_editabile(testo_modulo)
            h = hashlib.md5(testo_modulo.encode()).hexdigest()[:8]
            st.download_button(label="📥 Scarica PDF compilabile", data=pdf_bytes, file_name=f"Modulo_Segreteria_{h}.pdf", mime="application/pdf", key=f"btn_pdf_{h}")
        except Exception as exc:
            st.error(f"Non è stato possibile generare il PDF: {exc}")
    if diretta_html:
        st.markdown(diretta_html, unsafe_allow_html=True)
 
st.title("🏫 AVS Office")
st.caption("Assistente Virtuale Scolastico · Un supporto pratico, chiaro e gentile per la segreteria")
 
mostra_anim = not st.session_state.get("avs_animazione_mostrata", False)
st.session_state["avs_animazione_mostrata"] = True
 
hero_html = """
<div class="avs-hero" style="background:linear-gradient(115deg,#F0EBFA 0%,#F8F5FB 54%,#EAF4EF 100%);border:1px solid #E6E0EA;border-radius:18px;padding:17px 22px 24px 22px;margin:8px 0 22px 0;">
<div style="font-size:1.08rem;font-weight:800;color:#40384F;">La tua segreteria, un po’ più semplice ✨</div>
<div style="font-size:0.92rem;color:#716B79;margin-top:4px;padding-right:95px;">Procedure, risposte operative e moduli compilabili in un unico spazio.</div>
__AVS_CAT_ANIMATION__
</div>
"""
anim = """
<div class="avs-cat-chase" aria-hidden="true" title="Una piccola pausa felina">
<span class="avs-mouse">🐭</span>
<span class="avs-cat">🐈</span>
</div>
""" if mostra_anim else ""
st.markdown(hero_html.replace("__AVS_CAT_ANIMATION__", anim), unsafe_allow_html=True)
 
if "messaggi" not in st.session_state:
    st.session_state["messaggi"] = []
if "modulo_testo_editabile" not in st.session_state:
    st.session_state["modulo_testo_editabile"] = ""
if "modulo_guidato_pronto" not in st.session_state:
    st.session_state["modulo_guidato_pronto"] = False
 
with st.sidebar:
    st.header("🧰 Strumenti AVS")
    strumento = st.radio("Che cosa vuoi fare?", ["Assistente segreteria", "Crea modulo PDF compilabile", "Cerca codici meccanografici"], key="strumento_avs")
    st.divider()
    if strumento == "Assistente segreteria":
        st.header("⚡ Azioni rapide")
        st.markdown("Seleziona una procedura frequente per avviare la richiesta.")
        contesto = "Istituto non specificato dall'utente. Usa segnaposto tra parentesi quadre per i dati mancanti. "
        istr = "Non inventare dati ufficiali della scuola e non dichiarare di averli verificati online. Per ogni dato dell'istituto non fornito dall'utente, usa un segnaposto tra parentesi quadre e indica cosa va verificato prima dell'uso. "
        if st.button("📋 Presa di servizio supplente", use_container_width=True):
            st.session_state["prompt_rapido"] = f"{contesto} {istr} Un docente supplente deve prendere servizio oggi ma ha la febbre e non può venire fisicamente a firmare. Come devo procedere? Prepara anche una bozza di modulo editabile per la presa di servizio. Inserisci nella bozza solo i dati della scuola che hai potuto verificare; per quelli non verificati usa segnaposto tra parentesi quadre."
            st.session_state["ricerca_web_azione_rapida"] = False
        if st.button("🏥 Assenza per malattia ATA/docente", use_container_width=True):
            st.session_state["prompt_rapido"] = f"{contesto} {istr} Un docente mi ha comunicato stamattina di essere in malattia. Spiega i passaggi amministrativi da verificare su SIDI, Argo e NoiPA, distinguendo gli obblighi certi dalle procedure che dipendono dalla scuola. Non inventare dati specifici dell'istituto e cita le fonti web consultate."
            st.session_state["ricerca_web_azione_rapida"] = False
        if st.button("✉️ Bozza convocazione interpello", use_container_width=True):
            st.session_state["prompt_rapido"] = f"{contesto} {istr} Devo inviare una convocazione urgente per supplenza breve tramite interpello. Prepara una mail formale e una bozza di modulo di accettazione editabile. Indica quali dati devo verificare prima dell'invio. Inserisci nella bozza solo dati della scuola confermati da fonti affidabili; usa segnaposto tra parentesi quadre per le informazioni mancanti e cita le fonti consultate."
            st.session_state["ricerca_web_azione_rapida"] = False
        st.divider()
        if st.button("🗑️ Nuova conversazione", use_container_width=True):
            st.session_state["messaggi"] = []
            st.rerun()
    else:
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
                        risposta_modulo = client.models.generate_content(model=MODEL_NAME, contents=prompt_modulo, config=types.GenerateContentConfig(system_instruction="Sei AVS, assistente per le segreterie scolastiche italiane. Genera bozze prudenti, chiare e pratiche. Non inventare norme o dichiarare ufficiale un modello generato.", temperature=0.2, max_output_tokens=1200))
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
                pdf_bytes = crea_pdf_editabile(testo_modulo_finale)
                st.download_button(label="📥 Scarica PDF compilabile", data=pdf_bytes, file_name="AVS_modulo_compilabile.pdf", mime="application/pdf", key="download_pdf_guidato", use_container_width=True)
            except Exception as exc:
                st.error(f"Non è stato possibile generare il PDF: {exc}")
        st.caption("Nota: la compatibilità dei campi compilabili dipende dal lettore PDF usato, soprattutto su smartphone. Prova il file prima di distribuirlo.")
elif strumento == "Cerca codici meccanografici":
    st.subheader("🔍 Cerca codici meccanografici")
    st.write("Cerca per nome scuola o comune. I dati provengono dal dataset ufficiale del Ministero.")
    col1, col2 = st.columns(2)
    with col1:
        query_scuola = st.text_input("Nome scuola o comune", placeholder="Es. Manzoni, Ghirotti, Roma")
    with col2:
        regioni = {
            "Tutte": None,
            "ABRUZZO": "ABRUZZO", "BASILICATA": "BASILICATA", "CALABRIA": "CALABRIA",
            "CAMPANIA": "CAMPANIA", "EMILIA ROMAGNA": "EMILIA ROMAGNA",
            "FRIULI-VENEZIA G.": "FRIULI-VENEZIA G.", "LAZIO": "LAZIO", "LIGURIA": "LIGURIA",
            "LOMBARDIA": "LOMBARDIA", "MARCHE": "MARCHE", "MOLISE": "MOLISE",
            "PIEMONTE": "PIEMONTE", "PUGLIA": "PUGLIA", "SARDEGNA": "SARDEGNA",
            "SICILIA": "SICILIA", "TOSCANA": "TOSCANA", "TRENTINO ALTO ADIGE": "TRENTINO ALTO ADIGE",
            "UMBRIA": "UMBRIA", "VALLE D'AOSTA": "VALLE D'AOSTA", "VENETO": "VENETO"
        }
        regione_sel = st.selectbox("Regione (facoltativo)", list(regioni.keys()))
        solo_paritarie = st.checkbox("Solo scuole paritarie", value=False)
    if st.button("🔎 Cerca", use_container_width=True):
        if not query_scuola.strip() and regione_sel == "Tutte" and not solo_paritarie:
            st.warning("Inserisci almeno un criterio di ricerca.")
        else:
            with st.spinner("Ricerca in corso..."):
                scuole, errore = cerca_scuole(query_scuola.strip(), regioni.get(regione_sel), solo_paritarie)
            if errore:
                st.error(f"Errore: {errore}")
            elif not scuole:
                st.info("Nessuna scuola trovata.")
            else:
                st.success(f"Trovate {len(scuole)} scuole.")
 
                scuole_per_comune = {}
                for s in scuole:
                    comune = s.get("DESCRIZIONECOMUNE", "Comune sconosciuto")
                    if comune not in scuole_per_comune:
                        scuole_per_comune[comune] = []
                    scuole_per_comune[comune].append(s)
 
                for comune in sorted(scuole_per_comune.keys()):
                    st.markdown(f"### 📍 {comune}")
                    for s in scuole_per_comune[comune]:
                        codice = s.get("CODICESCUOLA", "")
                        denominazione = s.get("DENOMINAZIONESCUOLA", "")
                        provincia = s.get("PROVINCIA", "")
                        email = s.get("INDIRIZZOEMAILSCUOLA", "")
                        pec = s.get("INDIRIZZOPECSCUOLA", "")
                        indirizzo = s.get("INDIRIZZOSCUOLA", "")
                        sito = normalizza_url(s.get("SITOWEBSCUOLA", ""))
 
                        titolo = f"{denominazione} ({codice}) - {indirizzo}, {comune} ({provincia})"
                        if sito:
                            titolo = "🌐 " + titolo
 
                        with st.expander(titolo):
                            st.write(f"**Indirizzo:** {indirizzo}")
                            st.write(f"**Email:** {email}")
                            st.write(f"**PEC:** {pec}")
                            if sito:
                                st.markdown(f"**Sito web:** [{sito}]({sito})")
                                st.link_button("🌐 Apri il sito della scuola", sito, use_container_width=False)
                            else:
                                st.caption("Sito web non presente nel dataset per questo istituto.")
 
                st.caption("Fonte: Open Data del Ministero dell'Istruzione e del Merito.")
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
        st.session_state.pop("ricerca_web_azione_rapida", None)
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
                    for m in st.session_state["messaggi"][-4:]:
                        ruolo = "model" if m["role"] == "assistant" else "user"
                        contenuti.append({"role": ruolo, "parts": [{"text": m["content"]}]})
                    configurazione = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.2, max_output_tokens=900)
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
