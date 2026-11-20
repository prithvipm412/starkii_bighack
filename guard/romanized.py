"""Kannada evidence and lightweight normalization for Latin-script text (mac3, a0106f0 / 064a249).

Used only by LanguageBarrierGuard(kanglish="romanized"), which is OFF by default.
"""
import re

from pipeline.data import ITRANS_RE

# Common conversational forms, including regional and informal spellings.
WORDS = frozenset("""
hege hegey hegide hegittu hegitu hegagide hegagittu maadu madu maadi madi
madodu maadodu maduvudu maaduvudu maduvudakke madbeku maadbeka madtidini
madtini madtira madtara madona maadona beku beda beka bekilla bekagide
bekandre bekadare illa ilva ilde illade illi alli ellelli elli ellinda
ellige illige allige ellaru ella ellavu enu yenu enake enakke enidu enanta
yaake yake yaavaga yavaga yaava yava yaavudu yavudu yaavanu yavanu yaaru
yaaru yaarige yarige yaarinda yaaranna yarannadaru yaaradaru obbaru obbarige
obba obbana obbaranna neenu ninu neevu nivu ninna ninage ninge nimma nimage
nange nanage nanna naanu nanu naavu navu namage namma avanu avalu avaru
avana avala avara avarige avanige avalige ivanu ivalu ivaru ivara ivarige
idu ide iddare iddaru iddivi iddini idini idya idira idre ittu idakke
adu aduvene adakke adara adarinda ade aduvala adella idella haudu howdu
alla alva sariya sariyagi sariyaagi tappu tappilla sari tappagide gottu
gottila gottilla gothu gothilla tiliyadu tilidilla tiliyitu tilisi tilisu
heli helu helodu heloke helbeku heltini heltira helidaru heliddu hage
haage heege hige haagu hagu mattu athava aadare adare adre matte aadmele
amele modalu modlane konege koneyalli munde hinde mele kelage olage horage
pakka pakkada pakkadalli eduru naduve inda varege tanaka jothe jote jothege
ivattu ivaththu indu naale nale nenne ninne eega iga ivaga aaga aamele
beligge sanje madhyahna ratri raatri dina dinakke vaara vara tingalu
varsha samaya hottu bega nidhaanavagi swalpa swalpaane tumba thumba
bahala jaasti jasthi hechchu kadime innu matteeno innondu saha kooda kuda
ondu eradu mooru muru naalku nalku aidu aaru elu entu ombattu hattu
modalane eradane moorane maneyalli mane maneli ooru uru ooralli halli
nagara raste beedi angadi santhe shaale shaaleyalli pustaka pustakagalu
shikshaka huduga hudugi makkalu magu anna akka tamma tangi appa amma ajja
ajji hendati ganda snehita snehitaru gelaya baagilu kitaki nela meju
oota uta ootaane ootaayta tindi thindi tinodu tinnodu tinbeku tindya
tinnu kudiyodu kudi neeru niru haalu halu mosaru chaha kaapi sakkare
uppu bele annaakki akki rotti palya tarakaari hannu hannuugalu
hogu hogi hogona hogodu hogbeku barodu baru banni baa bartini bartira
bandaru bantu bandide bandre bandaga nintu ninthu nillu nillisu
koothu kuthu kooru kulithu kulituko nodu noDu nodi nododu kandide
kelu keli kelodu kodu kodi kododu koduvudu kottaru kodbeku
tagolu togoli tegadu tegedu tegeyodu tegedukolli ittu idi haaku haki
hakodu kadiyodu odu odi ododu odabeku bare bari bareyodu bareyiri
kalisu kalisi kalibeku kelasa kelasakke aadike aata nadeyodu nadita
odaatta nagodu alodu baduku badukodu usiru arogya aarogya novu kayile
sahaaya sahaya upaaya upaya dayavittu dhanyavaada dhanyavadagalu namaskara
namaskaara swagata shubhodaya chennagide chennagi chenna olle olledu
hosadu haleya dodda chikka uttama sundara khushi dukha ishta ishtavilla
bayasu bayake aase nanishta ishtapadodu havaamaana havamana male
malegaala bisilu chaLi chali gaali galee bengaluru railu nildana
thayaarisu tayaarisu oppige nakali kole visha tondare samasye
""".lower().split())

STRONG = frozenset("""
hege hegey hegide hegittu maadodu madodu maduvudu maaduvudu
maadbeku madbeku madtidini madtira beku beda bekilla bekandre yaake
yake yaavaga yaaru yaarige dayavittu ivattu gottilla gothilla
chennagide yaaradaru yarannadaru obbarige enakke haagu mattu
hogbeku helbeku koduvudu tiliyitu nimage nanage illade
""".split())
WORD_RE = re.compile(r"[A-Za-z]+")
SUFFIX_RE = re.compile(r"[a-z]{3,}(?:alli|inda|galu|vudu|odu|tini|tira|ide|alla)$")
SPELLING_RE = re.compile(r"aa|ee|oo|uu|dh")
SPELLING = {"aa": "a", "ee": "i", "oo": "u", "uu": "u", "dh": "d"}


def normalized(word):
    return SPELLING_RE.sub(lambda m: SPELLING[m.group()], word.lower())


NORMAL_WORDS = frozenset(map(normalized, WORDS))
NORMAL_STRONG = frozenset(map(normalized, STRONG))


def is_kannada_word(word):
    term = normalized(word)
    return (
        term in NORMAL_WORDS
        or (term.endswith("ge") and term[:-2] in NORMAL_WORDS)
        or bool(SUFFIX_RE.fullmatch(term))
    )


def is_kanglish(text):
    words = WORD_RE.findall(text)
    return bool(words) and (
        any(normalized(word) in NORMAL_STRONG for word in words)
        or sum(is_kannada_word(word) for word in words) / len(words) >= 0.25
    )


KEYWORDS = {
    "hege": "how", "hegide": "how is", "maadu": "do", "madu": "do",
    "maduvudu": "do", "madodu": "do", "maadi": "do", "beku": "want",
    "beda": "do not want", "enu": "what", "yenu": "what", "yaake": "why",
    "elli": "where", "yaaru": "who", "ivattu": "today", "naale": "tomorrow",
    "illa": "no", "illade": "without", "obbarige": "someone",
    "yarannadaru": "someone", "koduvudu": "give", "kadiyodu": "steal",
    "tegeyodu": "take", "visha": "poison", "kole": "murder",
    "nanna": "my", "nimma": "your", "haagu": "and", "mattu": "and",
}
KEYWORDS = {normalized(word): meaning for word, meaning in KEYWORDS.items()}


def keyword_view(text):
    return WORD_RE.sub(lambda m: KEYWORDS.get(normalized(m.group()), m.group()), text)


# ---- word-level transliteration (moved from mac3's guard.py, 064a249) ----
LATIN_WORD_RE = re.compile(r"[A-Za-z]+")
KANNADA_WORDS = {
    "hege": "ಹೇಗೆ", "hegey": "ಹೇಗೆ", "hegide": "ಹೇಗಿದೆ",
    "madu": "ಮಾಡು", "maadu": "ಮಾಡು", "madi": "ಮಾಡಿ", "maadi": "ಮಾಡಿ",
    "madodu": "ಮಾಡೋದು", "maadodu": "ಮಾಡೋದು",
    "maduvudu": "ಮಾಡುವುದು", "maaduvudu": "ಮಾಡುವುದು",
    "maduvudhu": "ಮಾಡುವುದು", "maaduvudhu": "ಮಾಡುವುದು",
    "beku": "ಬೇಕು", "beka": "ಬೇಕಾ", "enu": "ಏನು", "yenu": "ಏನು",
    "elli": "ಎಲ್ಲಿ", "yaake": "ಯಾಕೆ", "yake": "ಯಾಕೆ", "yaaru": "ಯಾರು",
    "yarannadaru": "ಯಾರನ್ನಾದರೂ", "obbarige": "ಒಬ್ಬರಿಗೆ",
    "koduvudu": "ಕೊಡುವುದು", "kodu": "ಕೊಡು", "kodi": "ಕೊಡಿ",
    "nanna": "ನನ್ನ", "nanage": "ನನಗೆ", "nange": "ನನಗೆ",
    "ninna": "ನಿನ್ನ", "nimma": "ನಿಮ್ಮ", "namma": "ನಮ್ಮ",
    "illa": "ಇಲ್ಲ", "ide": "ಇದೆ", "idu": "ಇದು", "adu": "ಅದು",
    "mattu": "ಮತ್ತು", "haagu": "ಹಾಗೂ", "swalpa": "ಸ್ವಲ್ಪ",
    "heli": "ಹೇಳಿ", "dayavittu": "ದಯವಿಟ್ಟು", "banni": "ಬನ್ನಿ",
    "anna": "ಅಣ್ಣ", "akka": "ಅಕ್ಕ", "hogu": "ಹೋಗು",
    "havaamaana": "ಹವಾಮಾನ", "chaha": "ಚಹಾ", "bengaluru": "ಬೆಂಗಳೂರು",
    "tumba": "ತುಂಬಾ", "alli": "ಅಲ್ಲಿ", "inda": "ಇಂದ", "yavudu": "ಯಾವುದು",
    "yaavudu": "ಯಾವುದು", "aadare": "ಆದರೆ", "bari": "ಬರಿ",
    "kole": "ಕೊಲೆ", "visha": "ವಿಷ",
}
# Keep canonical vowels and consonants for common words before falling back to ITRANS.
SCRIPT_WORDS = {normalized(word): value for word, value in KANNADA_WORDS.items()}
SCRIPT_WORDS.update({
    "ivattu": "ಇವತ್ತು", "hegide": "ಹೇಗಿದೆ", "beda": "ಬೇಡ", "gottu": "ಗೊತ್ತು",
    "nale": "ನಾಳೆ", "ondu": "ಒಂದು", "eradu": "ಎರಡು", "mane": "ಮನೆ",
    "ota": "ಊಟ", "kadiyodu": "ಕದಿಯೋದು", "tegeyodu": "ತೆಗೆಯೋದು",
})
LOOSE_ITRANS = re.compile(r"aa|ee|oo|uu|dh")
ITRANS_SPELLING = {"aa": "A", "ee": "I", "oo": "U", "uu": "U", "dh": "d"}


def to_kannada_script(text: str) -> str:
    """Word-level Kanglish -> Kannada script: common phonetic spellings first, then ITRANS fallback."""
    from indic_transliteration import sanscript

    def convert(match):
        word = match.group()
        canonical = SCRIPT_WORDS.get(normalized(word))
        if canonical is not None:
            return canonical
        if ITRANS_RE.fullmatch(word):
            return sanscript.transliterate(word, sanscript.ITRANS, sanscript.KANNADA)
        if is_kannada_word(word):
            phonetic = LOOSE_ITRANS.sub(lambda m: ITRANS_SPELLING[m.group()], word.lower())
            return sanscript.transliterate(phonetic, sanscript.ITRANS, sanscript.KANNADA)
        return word

    return LATIN_WORD_RE.sub(convert, text)
