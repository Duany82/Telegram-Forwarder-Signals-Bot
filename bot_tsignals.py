from dotenv import load_dotenv
load_dotenv()

from telethon import TelegramClient, events
from telethon.tl.types import MessageService
import os
import re

# --- Configuración de Credenciales ---
api_id = os.environ.get('API_ID')
api_hash = os.environ.get('API_HASH')
session_name = 'forward_session'
phone_number = os.environ.get('PHONE_NUMBER')

# --- Configuración de Canales ---
canales_origen_str = os.environ.get('CANALES_ORIGEN', '')
destino_str = os.environ.get('DESTINO')

# --- Configuración de Lógica de Mensajes ---
AVISO_PHRASE = "Aviso de Responsabilidad"
PINNED_ID_FILE = 'pinned_message.id' # Archivo para guardar el ID del mensaje fijado

# --- Variables Globales ---
# Usamos una lista para que sea mutable dentro de las funciones async
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

# --- Archivo de Control de Sincronización ---
sync_complete_file = '.initial_sync_complete'

# --- Lógica del Bot ---
import socks
client = TelegramClient(
    session_name, 
    api_id, 
    api_hash,
    proxy=(socks.HTTP, 'proxy.server', 3128)
)

def procesar_texto(texto_original):
    """Aplica todos los reemplazos y eliminaciones de texto."""
    reemplazos = {
        'SersanSistemas': 'ASniper',
        'Apolo': ''  # Elimina la palabra "Apolo"
    }
    
    texto_modificado = texto_original
    for palabra_a_buscar, palabra_a_poner in reemplazos.items():
        patron = r'\b' + re.escape(palabra_a_buscar) + r'\b'
        texto_modificado = re.sub(patron, palabra_a_poner, texto_modificado, flags=re.IGNORECASE)
    
    # Limpiar espacios en blanco dobles que puedan quedar después de una eliminación
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

    if pinned_message_info['id'] is None:
        # No hay mensaje fijado, lo creamos
        print(f"Creando nuevo mensaje de '{AVISO_PHRASE}'...")
        sent_message = await client.send_message(
            destino,
            message=texto_modificado,
            file=message.media,
            link_preview=False
        )
        await client.pin_message(destino, sent_message.id)
        pinned_message_info['id'] = sent_message.id
        with open(PINNED_ID_FILE, 'w') as f:
            f.write(str(pinned_message_info['id']))
        print(f"Nuevo mensaje de aviso CREADO, FIJADO y GUARDADO con ID: {pinned_message_info['id']}")
    else:
        # Ya existe un mensaje, lo editamos
        try:
            # Primero, verificamos si el texto realmente cambió para no hacer llamadas innecesarias
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
            # Si el mensaje fue borrado manualmente, reseteamos para que se cree de nuevo
            print(f"Error al editar el mensaje fijado (ID: {pinned_message_info['id']}): {e}")
            print("El mensaje pudo haber sido borrado. Se creará uno nuevo la próxima vez.")
            pinned_message_info['id'] = None
            if os.path.exists(PINNED_ID_FILE):
                os.remove(PINNED_ID_FILE)


@client.on(events.NewMessage(chats=canales_origen))
async def manejador_principal(event):
    if isinstance(event.message, MessageService):
        return
    
    # Enrutador: decide qué función llamar
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
            
            # Durante la sincronización, también aplicamos la lógica del enrutador
            if message.text and AVISO_PHRASE in message.text:
                await manejar_aviso_responsabilidad(message)
            else:
                await reenviar_mensaje_normal(message)
        print(f"Canal {canal} sincronizado.")
    
    with open(sync_complete_file, 'w') as f:
        f.write('completed')
    print("--- SINCRONIZACIÓN INICIAL COMPLETADA ---")

async def main():
    global pinned_message_info
    await client.start(phone=phone_number)
    print("\nSesión iniciada con éxito.")

    # Cargar el ID del mensaje fijado si existe
    if os.path.exists(PINNED_ID_FILE):
        with open(PINNED_ID_FILE, 'r') as f:
            content = f.read().strip()
            if content.isdigit():
                pinned_message_info['id'] = int(content)
                print(f"ID del mensaje fijado cargado desde archivo: {pinned_message_info['id']}")

    if not os.path.exists(sync_complete_file):
        await sincronizacion_inicial()
    else:
        print("El historial ya ha sido sincronizado anteriormente.")

    if not canales_origen:
        print("************************************************************")
        print("ADVERTENCIA: La lista 'canales_origen' está vacía.")
        print("************************************************************")
    
    print(f"Destino configurado: {destino}")
    print("Bot en funcionamiento. Esperando nuevos mensajes...")
    await client.run_until_disconnected()

# Ejecutar el cliente
with client:
    client.loop.run_until_complete(main())
