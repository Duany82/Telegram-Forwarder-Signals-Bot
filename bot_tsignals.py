from dotenv import load_dotenv
load_dotenv()

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageService
import os
import re

# --- Configuración de Credenciales ---
api_id = os.environ.get('API_ID')
api_hash = os.environ.get('API_HASH')
session_string = os.environ.get('SESSION_STRING')

# --- Configuración de Canales ---
canales_origen_str = os.environ.get('CANALES_ORIGEN', '')
destino_str = os.environ.get('DESTINO')

# --- Configuración de Lógica de Mensajes ---
AVISO_PHRASE = "Aviso de Responsabilidad"

# --- Variables Globales ---
# El ID del mensaje fijado se manejará en memoria.
# Si el bot se reinicia, lo buscará o creará de nuevo.
pinned_message_info = {'id': None}

# --- Validación y Conversión de IDs ---
def convertir_ids(cadena_ids):
    if not cadena_ids:
        return []
    try:
        return [int(id_str.strip()) for id_str in cadena_ids.split(',')]
    except ValueError:
        print("Error: La variable de entorno CANALES_ORIGEN o DESTINO no tiene un formato válido.")
        return []

canales_origen = convertir_ids(canales_origen_str)
destino = int(destino_str) if destino_str and destino_str.lstrip('-').isdigit() else None

# --- Lógica del Bot ---
if not session_string:
    raise ValueError("La variable de entorno SESSION_STRING no está configurada.")

client = TelegramClient(
    StringSession(session_string),
    api_id,
    api_hash
)

def procesar_texto(texto_original):
    """Aplica todos los reemplazos y eliminaciones de texto."""
    reemplazos = {
        'SersanSistemas': 'ASniper',
        'Apolo': ''
    }
    texto_modificado = texto_original
    for palabra_a_buscar, palabra_a_poner in reemplazos.items():
        patron = r'\b' + re.escape(palabra_a_buscar) + r'\b'
        texto_modificado = re.sub(patron, palabra_a_poner, texto_modificado, flags=re.IGNORECASE)
    texto_modificado = re.sub(r'\s+', ' ', texto_modificado).strip()
    return texto_modificado

async def reenviar_mensaje_normal(message):
    """Procesa y reenvía un mensaje estándar."""
    if not message.text:
        await client.send_message(destino, message)
        print(f"Mensaje copiado (sin texto) desde {message.chat_id} hacia {destino}")
        return

    texto_modificado = procesar_texto(message.text)

    if texto_modificado == message.text:
        await client.send_message(destino, message)
        print(f"Mensaje copiado (sin reemplazo) desde {message.chat_id} hacia {destino}")
    else:
        await client.send_message(
            destino,
            message=texto_modificado,
            file=message.media,
            link_preview=False
        )
        print(f"Mensaje procesado (con reemplazo) desde {message.chat_id} hacia {destino}")

async def manejar_aviso_responsabilidad(message):
    """Maneja la lógica del mensaje especial 'Aviso de Responsabilidad'."""
    global pinned_message_info
    texto_modificado = procesar_texto(message.text)

    # Si no conocemos el ID, intentamos buscarlo entre los mensajes fijados del canal
    if pinned_message_info['id'] is None:
        print("No se conoce el ID del mensaje de aviso. Buscando en el canal...")
        async for msg in client.iter_messages(destino, limit=100): # Busca en los últimos 100 mensajes
             if msg.pinned:
                 if AVISO_PHRASE in msg.text:
                     pinned_message_info['id'] = msg.id
                     print(f"Mensaje de aviso encontrado y cargado. ID: {pinned_message_info['id']}")
                     break

    if pinned_message_info['id'] is None:
        print(f"No se encontró mensaje de aviso existente. Creando uno nuevo...")
        sent_message = await client.send_message(
            destino,
            message=texto_modificado,
            file=message.media,
            link_preview=False
        )
        await client.pin_message(destino, sent_message.id)
        pinned_message_info['id'] = sent_message.id
        print(f"Nuevo mensaje de aviso CREADO y FIJADO con ID: {pinned_message_info['id']}")
    else:
        try:
            # Comprobamos si el texto ha cambiado antes de editar
            old_message = await client.get_messages(destino, ids=pinned_message_info['id'])
            if old_message and old_message.text == texto_modificado:
                print(f"Aviso de Responsabilidad sin cambios. No se necesita editar.")
                return

            print(f"Actualizando mensaje de aviso existente (ID: {pinned_message_info['id']})...")
            await client.edit_message(
                destino,
                pinned_message_info['id'],
                message=texto_modificado,
                file=message.media,
                link_preview=False
            )
            print("Mensaje de aviso ACTUALIZADO.")
        except Exception as e:
            print(f"Error al editar el mensaje fijado (ID: {pinned_message_info['id']}): {e}")
            print("El mensaje pudo haber sido borrado. Se creará uno nuevo la próxima vez.")
            pinned_message_info['id'] = None

@client.on(events.NewMessage(chats=canales_origen))
async def manejador_principal(event):
    if isinstance(event.message, MessageService):
        return
    if event.message.text and AVISO_PHRASE in event.message.text:
        await manejar_aviso_responsabilidad(event.message)
    else:
        await reenviar_mensaje_normal(event.message)

async def sincronizacion_inicial():
    print("""--- INICIANDO SINCRONIZACIÓN INICIAL DEL HISTORIAL ---
Esto puede tardar...""")
    for canal in canales_origen:
        print(f"Sincronizando canal {canal}...")
        async for message in client.iter_messages(canal, reverse=True):
            if isinstance(message, MessageService):
                continue
            if message.text and AVISO_PHRASE in message.text:
                await manejar_aviso_responsabilidad(message)
            else:
                await reenviar_mensaje_normal(message)
        print(f"Canal {canal} sincronizado.")
    print("--- SINCRONIZACIÓN INICIAL COMPLETADA ---")

async def main():
    await client.start()
    print("\nSesión iniciada con éxito.")

    # Comprueba la variable de entorno para decidir si ejecutar la sincronización
    perform_sync = os.environ.get('PERFORM_INITIAL_SYNC', 'false').lower() == 'true'

    if perform_sync:
        await sincronizacion_inicial()
    else:
        print("El historial ya ha sido sincronizado anteriormente (PERFORM_INITIAL_SYNC=false).")

    if not canales_origen:
        print("************************************************************")
        print("ADVERTENCIA: La lista 'canales_origen' está vacía.")
        print("************************************************************")
    
    print(f"Destino configurado: {destino}")
    print("Bot en funcionamiento. Esperando nuevos mensajes...")
    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())
