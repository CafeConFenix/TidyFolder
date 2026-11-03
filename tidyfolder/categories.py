"""File-type tables, topic keywords and bilingual folder names."""
from __future__ import annotations

import re
import unicodedata

IMAGE_EXT = {
    "jpg", "jpeg", "jfif", "png", "gif", "bmp", "webp", "tif", "tiff", "heic", "heif",
    "svg", "ico", "avif", "raw", "cr2", "cr3", "nef", "arw", "dng", "orf", "rw2", "psd",
}
VIDEO_EXT = {
    "mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "mpg", "mpeg", "3gp",
    "mts", "m2ts", "vob", "ogv",
}
AUDIO_EXT = {
    "mp3", "wav", "flac", "aac", "ogg", "oga", "m4a", "wma", "opus", "aiff", "aif",
    "mid", "midi", "amr",
}
ARCHIVE_EXT = {"zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz", "iso"}
SOFTWARE_EXT = {"exe", "msi", "apk", "dmg", "pkg", "deb", "rpm", "appimage"}
CODE_EXT = {
    "py", "js", "ts", "jsx", "tsx", "java", "c", "cpp", "h", "hpp", "cs", "go", "rs",
    "php", "rb", "sh", "bat", "ps1", "sql", "json", "xml", "yml", "yaml", "toml",
    "css", "scss",
}
DOCUMENT_EXT = {
    "pdf", "doc", "docx", "dotx", "docm", "odt", "rtf", "txt", "md", "tex", "epub",
    "mobi", "pages", "xls", "xlsx", "xlsm", "ods", "csv", "tsv", "numbers", "ppt",
    "pptx", "odp", "key", "html", "htm", "eml", "msg", "log", "rst",
}

TOPIC_IDS = [
    "finance", "legal", "health", "education", "work", "travel",
    "technology", "home", "science", "shopping",
]

# (English name, Spanish name). Names must be valid on Windows, macOS and Linux.
FOLDER_NAMES: dict[str, tuple[str, str]] = {
    "photos": ("Photos", "Fotos"),
    "videos": ("Videos", "Vídeos"),
    "audio": ("Audio", "Audios"),
    "archives": ("Archives", "Comprimidos"),
    "software": ("Software", "Programas"),
    "code": ("Code", "Código"),
    "other": ("Other files", "Otros archivos"),
    "docs_general": ("Other documents", "Otros documentos"),
    "finance": ("Finance", "Finanzas"),
    "legal": ("Legal", "Legal"),
    "health": ("Health", "Salud"),
    "education": ("Education", "Educación"),
    "work": ("Work", "Trabajo"),
    "travel": ("Travel", "Viajes"),
    "technology": ("Technology", "Tecnología"),
    "home": ("Home", "Hogar"),
    "science": ("Science", "Ciencia"),
    "shopping": ("Shopping", "Compras"),
}


def folder_name(category: str, lang: str) -> str:
    en, es = FOLDER_NAMES[category]
    return es if lang == "es" else en


def all_folder_names() -> set[str]:
    return {name for pair in FOLDER_NAMES.values() for name in pair}


def category_for_extension(ext: str) -> str:
    """Return a media category, ``"document"`` (needs content analysis) or ``"other"``."""
    ext = ext.lower().lstrip(".")
    if ext in IMAGE_EXT:
        return "photos"
    if ext in VIDEO_EXT:
        return "videos"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in ARCHIVE_EXT:
        return "archives"
    if ext in SOFTWARE_EXT:
        return "software"
    if ext in CODE_EXT:
        return "code"
    if ext in DOCUMENT_EXT:
        return "document"
    return "other"


def normalize(text: str) -> str:
    """Lower-case, strip accents and collapse whitespace."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text)


# Keywords are English + Spanish, accent-free. A keyword matches the *start* of a
# word (so "factur" matches "factura"/"facturas"); a trailing "!" means whole word.
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "finance": [
        "invoice", "factura", "receipt", "recibo", "bank", "banco", "tax", "impuesto",
        "irpf", "iva!", "payment", "pago", "salary", "nomina", "budget", "presupuesto",
        "invest", "inversion", "loan", "prestamo", "mortgage", "hipoteca", "balance",
        "accounting", "contabilidad", "transferencia", "credit", "credito", "iban",
        "saldo", "extracto", "bancari", "dividend", "pension",
    ],
    "legal": [
        "contract", "contrato", "agreement", "acuerdo", "law!", "ley!", "legal",
        "lawyer", "abogado", "court", "juzgado", "tribunal", "clause", "clausula",
        "notar", "sentencia", "demanda", "lawsuit", "terms and conditions",
        "condiciones", "gdpr", "proteccion de datos", "poder notarial", "licencia",
        "power of attorney", "testamento", "will and testament", "denuncia",
    ],
    "health": [
        "medical", "medico", "doctor", "hospital", "patient", "paciente",
        "prescription", "receta medica", "diagnos", "treatment", "tratamiento",
        "symptom", "sintoma", "medicin", "vaccin", "vacuna", "clinic", "analitica",
        "blood test", "sangre", "salud", "health", "dental", "dentista",
        "seguro medico", "radiograf", "fisioterapia", "therapy",
    ],
    "education": [
        "universit", "school", "colegio", "student", "estudiante", "course", "curso",
        "thesis", "tesis", "homework", "deberes", "exam", "lecture", "apuntes",
        "assignment", "tarea", "syllabus", "temario", "calificacion", "degree",
        "master", "tfg", "tfm", "bachillerato", "profesor", "professor", "teacher",
        "learning", "aprendizaje", "asignatura", "curriculum academico",
    ],
    "work": [
        "resume", "curriculum", "cv!", "cover letter", "carta de presentacion",
        "meeting", "reunion", "project", "proyecto", "client", "cliente", "report",
        "informe", "proposal", "propuesta", "employee", "empleado", "empresa",
        "company", "manager", "deadline", "agenda!", "minutes", "acta!", "empleo",
        "oferta de trabajo", "entrevista", "interview", "sales", "ventas", "marketing",
        "kpi", "quarter", "trimestre", "presentation", "presentacion",
    ],
    "travel": [
        "flight", "vuelo", "hotel", "booking", "reserva", "ticket", "billete",
        "passport", "pasaporte", "visa!", "itinerary", "itinerario", "trip!", "viaje",
        "airline", "aerolinea", "boarding", "embarque", "tourist", "turismo",
        "airbnb", "hostel", "excursion", "destination", "destino", "train!", "tren!",
        "crucero", "cruise", "vacation", "vacaciones", "holiday",
    ],
    "technology": [
        "software", "hardware", "programming", "programacion", "source code",
        "codigo fuente", "server", "servidor", "database", "base de datos", "network",
        "api!", "algorithm", "algoritmo", "computer", "ordenador", "computador",
        "cloud", "linux", "windows", "python", "javascript", "firewall",
        "cybersecurity", "ciberseguridad", "github", "user manual", "manual de usuario",
        "installation", "instalacion", "firmware", "driver", "aplicacion",
        "application", "artificial intelligence", "inteligencia artificial",
    ],
    "home": [
        "rent!", "alquiler", "lease", "arrendamiento", "electricity", "electricidad",
        "comunidad de vecinos", "neighbor", "vecino", "furniture", "mueble", "repair",
        "reparacion", "insurance", "seguro", "appliance", "electrodomestico", "warranty",
        "garantia", "apartment", "apartamento", "piso!", "house!", "casa!", "hogar",
        "renovation", "reforma", "cleaning", "limpieza", "heating", "calefaccion",
        "garden", "jardin", "utilities", "suministros",
    ],
    "science": [
        "research", "investigacion", "experiment", "hypothesis", "hipotesis",
        "laboratory", "laboratorio", "physics", "fisica", "chemistry", "quimica",
        "biology", "biologia", "mathematic", "matematica", "astronomy", "astronomia",
        "scientific", "cientific", "journal", "abstract", "doi!", "equation",
        "ecuacion", "theorem", "teorema", "molecul", "genetic", "climate",
        "statistic", "estadistica", "data analysis", "analisis de datos",
    ],
    "shopping": [
        "order!", "pedido", "purchase", "compra", "cart!", "carrito", "shipping",
        "envio", "delivery", "entrega", "amazon", "aliexpress", "product", "producto",
        "store", "tienda", "discount", "descuento", "coupon", "cupon", "refund",
        "devolucion", "catalog", "catalogo", "wishlist", "lista de deseos",
    ],
}


def _compile(keyword: str) -> re.Pattern[str]:
    if keyword.endswith("!"):
        return re.compile(r"\b" + re.escape(keyword[:-1]) + r"\b")
    return re.compile(r"\b" + re.escape(keyword))


COMPILED_KEYWORDS: dict[str, list[re.Pattern[str]]] = {
    topic: [_compile(k) for k in words] for topic, words in TOPIC_KEYWORDS.items()
}
