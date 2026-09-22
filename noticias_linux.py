#!/usr/bin/env python3

import os
import re
import html
import sys

import feedparser
import requests

from dotenv import load_dotenv


# ============================================================
# CARGAR CONFIGURACIÓN DESDE .env
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURACIÓN
# ============================================================

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://192.168.0.16:11434"
).rstrip("/")

OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/chat"

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3:0.6b"
)

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID"
)

NOTICIAS_POR_FEED = int(
    os.getenv("NOTICIAS_POR_FEED", "1")
)

MAX_CONTEXTO_NOTICIA = int(
    os.getenv("MAX_CONTEXTO_NOTICIA", "1000")
)

OLLAMA_TIMEOUT = int(
    os.getenv("OLLAMA_TIMEOUT", "150")
)

# Edad máxima de una noticia (en días).
# Noticias más viejas se ignoran para evitar
# revivir contenido antiguo cuando el feed
# trae mezclado histórico. 0 = sin límite.
MAX_EDAD_DIAS = int(
    os.getenv("MAX_EDAD_DIAS", "7")
)


# ============================================================
# FEEDS RSS
# ============================================================

FEEDS_LINUX = [
    "https://www.muylinux.com/feed/",
    "https://www.phoronix.com/phoronix-rss.php",
    "https://ubunlog.com/feed/",
    "https://unaaldia.hispasec.com/feed",
    "https://feeds.feedburner.com/TheHackerNews",
    "https://archlinux.org/feeds/news/",
    "https://www.cyberciti.biz/feed/"
]


# ============================================================
# VALIDAR CONFIGURACIÓN
# ============================================================

def validar_configuracion():
    errores = []

    if not TELEGRAM_BOT_TOKEN:
        errores.append(
            "Falta TELEGRAM_BOT_TOKEN en el archivo .env"
        )

    if not TELEGRAM_CHAT_ID:
        errores.append(
            "Falta TELEGRAM_CHAT_ID en el archivo .env"
        )

    if not OLLAMA_BASE_URL:
        errores.append(
            "Falta OLLAMA_BASE_URL en el archivo .env"
        )

    if not OLLAMA_MODEL:
        errores.append(
            "Falta OLLAMA_MODEL en el archivo .env"
        )

    if errores:
        print("\n[-] ERROR DE CONFIGURACIÓN")

        for error in errores:
            print(f"    - {error}")

        return False

    return True


# ============================================================
# LIMPIEZA HTML
# ============================================================

def limpiar_html(texto_html):
    if not texto_html:
        return ""

    # Convierte entidades:
    # &amp; -> &
    # &quot; -> "
    texto = html.unescape(texto_html)

    # Elimina etiquetas HTML
    texto = re.sub(
        r"<[^>]+>",
        " ",
        texto
    )

    # Elimina espacios repetidos
    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ============================================================
# OBTENER CUERPO DE UNA NOTICIA RSS
# ============================================================

def obtener_cuerpo(entry):
    if "content" in entry and entry.content:
        return limpiar_html(
            entry.content[0].value
        )

    if "summary" in entry:
        return limpiar_html(
            entry.summary
        )

    if "description" in entry:
        return limpiar_html(
            entry.description
        )

    return ""


# ============================================================
# COMPROBAR OLLAMA
# ============================================================

def comprobar_ollama():
    print(
        f"[*] Comprobando Ollama en "
        f"{OLLAMA_BASE_URL}..."
    )

    try:
        response = requests.get(
            f"{OLLAMA_BASE_URL}/api/tags",
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        modelos = data.get(
            "models",
            []
        )

        nombres_modelos = [
            modelo.get("name", "")
            for modelo in modelos
        ]

        print("[+] Ollama responde correctamente.")

        if OLLAMA_MODEL in nombres_modelos:
            print(
                f"[+] Modelo disponible: "
                f"{OLLAMA_MODEL}"
            )
            return True

        print(
            f"[!] Ollama responde, pero no encuentro "
            f"el modelo '{OLLAMA_MODEL}'."
        )

        print("[!] Modelos encontrados:")

        for modelo in nombres_modelos:
            print(
                f"    - {modelo}"
            )

        return False

    except requests.exceptions.ConnectionError:
        print(
            f"[-] No puedo conectar con Ollama en "
            f"{OLLAMA_BASE_URL}"
        )

    except requests.exceptions.Timeout:
        print(
            "[-] Timeout conectando con Ollama."
        )

    except requests.RequestException as e:
        print(
            f"[-] Error HTTP conectando con Ollama: "
            f"{e}"
        )

    return False


# ============================================================
# NORMALIZAR TAGS PRODUCIDOS POR LA IA
# ============================================================

def normalizar_tags(texto):
    if not texto:
        return "sin tags"

    texto = texto.strip()

    # Elimina elementos innecesarios que pueda generar
    # el modelo pequeño
    texto = texto.replace("#", "")
    texto = texto.replace("*", "")
    texto = texto.replace("`", "")

    # Separa por coma, punto y coma o salto de línea
    posibles_tags = re.split(
        r"[,;\n]+",
        texto
    )

    tags = []
    tags_lower = set()

    for tag in posibles_tags:
        tag = tag.strip(
            " .:-\t"
        )

        if not tag:
            continue

        # Evitamos frases excesivamente largas
        if len(tag) > 60:
            continue

        tag_lower = tag.lower()

        # Evitamos duplicados
        if tag_lower in tags_lower:
            continue

        tags.append(tag)
        tags_lower.add(tag_lower)

        if len(tags) >= 10:
            break

    if not tags:
        return "sin tags"

    return ", ".join(tags)


# ============================================================
# CONSULTAR OLLAMA
# ============================================================

def consultar_ia_tags(
    titulo_noticia,
    cuerpo_noticia
):
    print(
        f"    [AI] Analizando: "
        f"{titulo_noticia[:70]}"
    )

    prompt_sistema = (
        "Eres un extractor de metadatos técnicos "
        "especializado en Linux, informática, "
        "software, infraestructura y ciberseguridad. "
        "Lee el título y contenido proporcionados. "
        "Devuelve solamente tecnologías, productos, "
        "proyectos, distribuciones Linux, lenguajes, "
        "protocolos, vulnerabilidades, herramientas "
        "y conceptos técnicos realmente presentes "
        "en la noticia. "
        "No inventes información. "
        "Máximo 10 tags. "
        "Devuelve una única línea con los tags "
        "separados por comas. "
        "No escribas explicaciones ni introducciones."
    )

    cuerpo_recortado = cuerpo_noticia[
        :MAX_CONTEXTO_NOTICIA
    ]

    texto_contexto = (
        f"TÍTULO:\n"
        f"{titulo_noticia}\n\n"
        f"CONTENIDO:\n"
        f"{cuerpo_recortado}"
    )

    payload = {
        "model": OLLAMA_MODEL,

        "messages": [
            {
                "role": "system",
                "content": prompt_sistema
            },
            {
                "role": "user",
                "content": texto_contexto
            }
        ],

        # Muy importante en Qwen3.
        # Desactiva el razonamiento interno largo.
        "think": False,

        # Esperamos respuesta completa.
        "stream": False,

        # Reducimos contexto y creatividad para el teléfono.
        "options": {
            "num_ctx": 1024,
            "temperature": 0.1
        },

        # Mantiene el modelo cargado durante el procesamiento
        # de varios feeds.
        "keep_alive": "10m"
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        resultado = (
            data
            .get("message", {})
            .get("content", "")
            .strip()
        )

        tags = normalizar_tags(
            resultado
        )

        print(
            f"    [+] Tags: {tags}"
        )

        return tags

    except requests.exceptions.Timeout:
        print(
            "    [!] TIMEOUT: Ollama tardó "
            "demasiado."
        )

        return "timeout IA"

    except requests.exceptions.ConnectionError:
        print(
            "    [-] Se perdió la conexión "
            "con Ollama."
        )

        return "IA no disponible"

    except requests.RequestException as e:
        print(
            f"    [-] Error HTTP Ollama: {e}"
        )

        return "error IA"

    except Exception as e:
        print(
            f"    [-] Error procesando Ollama: {e}"
        )

        return "error IA"


# ============================================================
# TELEGRAM
# ============================================================

def dividir_mensaje(
    texto,
    limite=3900
):
    """
    Telegram permite mensajes de hasta 4096 caracteres.
    Dejamos margen usando 3900.
    """

    if len(texto) <= limite:
        return [texto]

    bloques = []
    bloque_actual = ""

    for linea in texto.splitlines():
        candidato = (
            f"{bloque_actual}\n{linea}"
            if bloque_actual
            else linea
        )

        if len(candidato) <= limite:
            bloque_actual = candidato

        else:
            if bloque_actual:
                bloques.append(
                    bloque_actual
                )

            # Caso excepcional:
            # una sola línea supera 3900 caracteres
            while len(linea) > limite:
                bloques.append(
                    linea[:limite]
                )

                linea = linea[
                    limite:
                ]

            bloque_actual = linea

    if bloque_actual:
        bloques.append(
            bloque_actual
        )

    return bloques


def enviar_telegram(mensaje):
    if not TELEGRAM_BOT_TOKEN:
        print(
            "[-] TELEGRAM_BOT_TOKEN no configurado."
        )

        return False

    if not TELEGRAM_CHAT_ID:
        print(
            "[-] TELEGRAM_CHAT_ID no configurado."
        )

        return False

    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    bloques = dividir_mensaje(
        mensaje
    )

    for numero, bloque in enumerate(
        bloques,
        start=1
    ):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": bloque,

            # Evita previews gigantes de todos los RSS.
            "link_preview_options": {
                "is_disabled": True
            }
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=30
            )

            response.raise_for_status()

            data = response.json()

            if not data.get("ok"):
                print(
                    "[-] Telegram rechazó "
                    "el mensaje."
                )

                return False

            print(
                f"    [+] Telegram enviado "
                f"{numero}/{len(bloques)}"
            )

        except requests.exceptions.Timeout:
            print(
                "[-] Timeout enviando Telegram."
            )

            return False

        except requests.RequestException as e:
            print(
                f"[-] Error HTTP Telegram: {e}"
            )

            return False

        except Exception as e:
            print(
                f"[-] Error Telegram: {e}"
            )

            return False

    return True


# ============================================================
# DESCARGAR FEED
# ============================================================

def descargar_feed(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Linux News Agent/1.0; RSS Reader)"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    return feedparser.parse(
        response.content
    )


# ============================================================
# FECHA DE UNA ENTRADA
# ============================================================

def fecha_entry(entry):
    """
    Devuelve la fecha de publicación de un entry como
    datetime, usando published_parsed o updated_parsed
    como fallback. None si el feed no trae fecha.
    """
    import datetime as _dt

    ts = entry.get("published_parsed") or entry.get(
        "updated_parsed"
    )

    if not ts:
        return None

    try:
        return _dt.datetime(
            *ts[:6],
            tzinfo=_dt.timezone.utc
        )
    except Exception:
        return None


def seleccionar_mejores_entries(
    feed,
    maximo,
    max_edad_dias
):
    """
    Devuelve hasta `maximo` entradas, ordenadas de
    más reciente a más vieja.

    Si max_edad_dias > 0, descarta entradas más
    viejas que esa ventana. Entradas sin fecha se
    incluyen al final (asumimos que son nuevas
    si el feed no las pudo fechar).
    """
    import datetime as _dt

    ahora = _dt.datetime.now(
        _dt.timezone.utc
    )

    entradas = list(feed.entries)

    # Filtra por edad si corresponde
    if max_edad_dias > 0:
        filtradas = []
        for e in entradas:
            fecha = fecha_entry(e)
            if fecha is None:
                # Sin fecha: las dejamos pasar al
                # final; el feed probablemente es
                # reciente.
                filtradas.append(
                    (_dt.datetime.min.replace(
                        tzinfo=_dt.timezone.utc
                    ), e)
                )
                continue

            edad = ahora - fecha
            if edad.days <= max_edad_dias:
                filtradas.append((fecha, e))
            else:
                print(
                    f"    [-] Descartada por edad "
                    f"({edad.days}d): "
                    f"{e.get('title', '')[:60]}"
                )
        entradas_con_fecha = filtradas
    else:
        entradas_con_fecha = [
            (
                fecha_entry(e)
                or _dt.datetime.min.replace(
                    tzinfo=_dt.timezone.utc
                ),
                e
            )
            for e in entradas
        ]

    # Ordena de más reciente a más viejo
    entradas_con_fecha.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return [
        e for _, e in entradas_con_fecha[:maximo]
    ]


# ============================================================
# FORMATEAR NOTICIA PARA TELEGRAM
# ============================================================

def formatear_noticia(
    numero,
    titulo,
    tags,
    enlace
):
    texto = (
        f"📰 {numero}. {titulo}\n\n"
        f"🏷️ {tags}\n"
    )

    if enlace:
        texto += (
            f"\n🔗 {enlace}\n"
        )

    return texto


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print(
        "=============================================="
    )
    print(
        "      AGENTE LOCAL DE NOTICIAS LINUX"
    )
    print(
        "=============================================="
    )
    print()

    # --------------------------------------------------------
    # Configuración
    # --------------------------------------------------------

    if not validar_configuracion():
        sys.exit(1)

    print(
        f"[+] Ollama: {OLLAMA_BASE_URL}"
    )

    print(
        f"[+] Modelo: {OLLAMA_MODEL}"
    )

    print(
        f"[+] Noticias por feed: "
        f"{NOTICIAS_POR_FEED}"
    )

    print(
        f"[+] Contexto máximo por noticia: "
        f"{MAX_CONTEXTO_NOTICIA} caracteres"
    )

    print()

    # --------------------------------------------------------
    # Ollama
    # --------------------------------------------------------

    ia_disponible = comprobar_ollama()

    if not ia_disponible:
        print()
        print(
            "[!] Ollama no está disponible."
        )

        print(
            "[!] Las noticias se enviarán igualmente, "
            "pero sin tags generados por IA."
        )

    # --------------------------------------------------------
    # Procesar feeds
    # --------------------------------------------------------

    total_noticias = 0
    feeds_ok = 0
    feeds_error = 0

    for url in FEEDS_LINUX:
        print()
        print(
            "----------------------------------------------"
        )

        print(
            f"[*] Descargando: {url}"
        )

        try:
            feed = descargar_feed(
                url
            )

            nombre_feed = (
                feed.feed.get(
                    "title"
                )
                or url
            )

            print(
                f"[+] Feed: {nombre_feed}"
            )

            if not feed.entries:
                print(
                    "    [!] El feed no contiene "
                    "noticias."
                )

                continue

            entradas = seleccionar_mejores_entries(
                feed,
                NOTICIAS_POR_FEED,
                MAX_EDAD_DIAS
            )

            if not entradas:
                print(
                    "    [!] El feed no contiene "
                    "noticias dentro de la ventana."
                )

                continue

            if len(entradas) < NOTICIAS_POR_FEED:
                print(
                    f"    [i] {len(entradas)}/{NOTICIAS_POR_FEED} "
                    "noticias tras filtrar."
                )

            reporte_feed = (
                f"🐧 {nombre_feed}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
            )

            noticias_feed = 0

            for i, entry in enumerate(
                entradas,
                start=1
            ):
                titulo = entry.get(
                    "title",
                    "Sin título"
                )

                enlace = entry.get(
                    "link",
                    ""
                )

                cuerpo = obtener_cuerpo(
                    entry
                )

                print(
                    f"    -> Noticia {i}: "
                    f"{titulo[:80]}"
                )

                # --------------------------------------------
                # Generar tags
                # --------------------------------------------

                if ia_disponible:
                    tags = consultar_ia_tags(
                        titulo,
                        cuerpo
                    )

                else:
                    tags = (
                        "IA no disponible"
                    )

                # --------------------------------------------
                # Crear bloque Telegram
                # --------------------------------------------

                reporte_feed += (
                    formatear_noticia(
                        i,
                        titulo,
                        tags,
                        enlace
                    )
                )

                reporte_feed += "\n"

                noticias_feed += 1
                total_noticias += 1

            # --------------------------------------------
            # Enviar feed completo a Telegram
            # --------------------------------------------

            if noticias_feed > 0:
                print(
                    f"[*] Enviando '{nombre_feed}' "
                    f"a Telegram..."
                )

                enviado = enviar_telegram(
                    reporte_feed
                )

                if enviado:
                    feeds_ok += 1

                else:
                    feeds_error += 1

        except requests.exceptions.Timeout:
            print(
                "[-] Timeout descargando feed."
            )

            feeds_error += 1

        except requests.RequestException as e:
            print(
                f"[-] Error HTTP descargando feed: "
                f"{e}"
            )

            feeds_error += 1

        except Exception as e:
            print(
                f"[-] Error procesando feed: {e}"
            )

            feeds_error += 1

    # ========================================================
    # RESUMEN FINAL
    # ========================================================

    print()
    print(
        "=============================================="
    )
    print(
        "                  RESUMEN"
    )
    print(
        "=============================================="
    )

    print(
        f"Noticias procesadas : {total_noticias}"
    )

    print(
        f"Feeds enviados       : {feeds_ok}"
    )

    print(
        f"Feeds con error      : {feeds_error}"
    )

    print(
        f"Modelo IA            : {OLLAMA_MODEL}"
    )

    print(
        f"Ollama               : {OLLAMA_BASE_URL}"
    )

    # Opcionalmente mandamos un resumen final
    resumen = (
        "✅ Agente Linux finalizado\n\n"
        f"📰 Noticias procesadas: {total_noticias}\n"
        f"📡 Feeds enviados: {feeds_ok}\n"
        f"⚠️ Feeds con error: {feeds_error}\n"
        f"🤖 Modelo: {OLLAMA_MODEL}"
    )

    enviar_telegram(
        resumen
    )

    print()
    print(
        "[+] Proceso terminado."
    )
    print()


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    main()
