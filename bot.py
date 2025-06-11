import asyncio
import feedparser
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown
from dotenv import load_dotenv
from telegram import Bot
import logging
import json
import os
import re


# Cargar variables del archivo .env
load_dotenv()

# Obtener el token desde el entorno
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)

feeds = {
    "hmr": {
        "rss_url": "https://heavymetalrarities.com/forum/feed.php",
        "chat_id": "-1002721068015",
        "thread_id": 35
    }
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Archivo donde se guardarán los posts enviados
ARCHIVO_ENVIADOS = "enviados.json"

# Verifica que el archivo existe y tiene contenido válido
def cargar_enviados():
    if not os.path.exists(ARCHIVO_ENVIADOS):
        return []  # 🚀 Si el archivo no existe, retorna una lista vacía

    try:
        with open(ARCHIVO_ENVIADOS, "r", encoding="utf-8") as f:
            data = f.read().strip()  # 🔍 Asegura que el archivo no esté vacío
            return json.loads(data) if data else []
    except json.JSONDecodeError:
        logging.warning("⚠️ Archivo JSON corrupto. Se reiniciará el historial.")
        return []  # 🚀 Si hay error, retorna una lista vacía en lugar de fallar

# Guardar posts nuevos en el historial
def guardar_enviado(link):
    enviados = cargar_enviados()
    enviados.append(link)
    with open(ARCHIVO_ENVIADOS, "w", encoding="utf-8") as f:
        json.dump(enviados, f, indent=4)

def limpiar_url(url):
    url = url.strip()  # ✅ Elimina espacios extra
    url = url.replace("\\", "")  # ✅ Elimina caracteres de escape innecesarios
    url = url.replace("[Leer más](", "").replace(")", "")  # ✅ Limpia formato MarkdownV2
    
    # ✅ Validar que la URL tenga un formato correcto
    patron = re.compile(r"^https?:\/\/[\w\-\.]+[\w\-]+(\.[\w]+)+(\/.*)?$")
    if not patron.match(url):
        logging.warning(f"⚠️ URL inválida detectada: {url}")
        return None  # Si la URL es inválida, evitar enviarla

    return url

async def obtener_nuevos_posts(rss_url):
    logging.info(f"Obteniendo posts desde: {rss_url}")
    feed = feedparser.parse(rss_url)
    posts = []
    enviados = cargar_enviados()  # Obtener historial de posts ya enviados

    for entry in feed.entries[:5]:  
        categorias = [cat["term"] for cat in entry.get("tags", []) if cat is not None]
        link = entry.link if hasattr(entry, "link") else None  # ✅ Verifica si 'entry' tiene 'link'

        # **Evitar duplicados: si el post ya fue enviado, lo saltamos**
        if link and link in enviados:
            logging.info(f"Post ya enviado: {link} | Omitiendo...")
            continue  

        # Filtrar los posts que contengan "Hard Rock"
        if any("Hard Rock" in categoria for categoria in categorias):
            title = escape_markdown(entry.title, version=2) if hasattr(entry, "title") else "Sin título"
            author = escape_markdown(entry.author, version=2) if hasattr(entry, "author") else "Autor desconocido"

            # Verifica que la URL exista antes de limpiarla
            link_url = link if link else None

            if link_url:
                link_url = limpiar_url(link_url)  # ✅ Solo procesar si la URL es válida
                if link_url:  # ✅ Verificar que la función no devolvió None
                    keyboard = [[InlineKeyboardButton("🔗 Leer más", url=link_url)]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

            # Extraer imagen desde <content>
            image_url = None
            if hasattr(entry, "content"):
                contenido = entry.content[0]["value"]
                if '<img ' in contenido and 'src="' in contenido:
                    image_url = contenido.split('src="')[1].split('"')[0]

            mensaje = f"📢 *{title}*\n👤 Publicado por: {author}\n🔗 [Leer más]({link_url})"
            posts.append({"text": mensaje, "image": image_url})

            if link_url:  # ✅ Solo guardar si la URL es válida
                guardar_enviado(link_url)

            logging.info(f"Nuevo post enviado: {title} | Imagen: {image_url if image_url else 'No hay imagen'}")

    return posts

def es_url_valida(url):
    """Verifica si la URL es válida y apunta a una imagen."""
    if not url:
        return False
    
    patron = re.compile(r"^https?:\/\/.*\.(jpg|jpeg|png|gif)$", re.IGNORECASE)
    return bool(patron.match(url))

async def enviar_posts():
    logging.info("Comenzando el envío de posts...")
    for tema, config in feeds.items():
        posts = await obtener_nuevos_posts(config["rss_url"])
        
        for post in posts:
            link_url = post["text"].split("🔗 ")[1].strip()
            link_url = link_url.replace("\\", "").replace("[Leer más](", "").replace(")", "")  

            keyboard = [[InlineKeyboardButton("🔗 Leer más", url=link_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # **Verificar si la imagen es válida antes de enviarla**
            if post["image"] and es_url_valida(post["image"]):
                await bot.send_photo(
                    chat_id=config["chat_id"], 
                    photo=post["image"], 
                    caption=f"📢 *{post['text'].split('🔗')[0].strip()}*", 
                    parse_mode="MarkdownV2", 
                    message_thread_id=config["thread_id"],
                    reply_markup=reply_markup
                )
                logging.info(f"Imagen enviada: {post['image']}")
            else:
                logging.warning(f"⚠️ Imagen inválida o no disponible: {post['image']}")

                # Enviar mensaje sin imagen si la URL de la imagen no es válida
                await bot.send_message(
                    chat_id=config["chat_id"], 
                    text=f"📢 *{post['text'].split('🔗')[0].strip()}*",  
                    parse_mode="MarkdownV2",  
                    message_thread_id=config["thread_id"],  
                    reply_markup=reply_markup  
                )
                logging.info(f"Mensaje enviado sin imagen: {post['text']}")

async def ejecutar_bot():
    while True:
        await enviar_posts()
        logging.info("Esperando 5 minutos para el próximo envío...")
        await asyncio.sleep(300)  # 300 segundos = 5 minutos

asyncio.run(ejecutar_bot())