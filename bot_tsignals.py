from dotenv import load_dotenv
load_dotenv()

from telethon import TelegramClient, events
from telethon.tl.types import MessageService
import os
import re

# --- Configuración de Credenciales ---
# Las credenciales se leen desde las variables de entorno para mayor seguridad.
api_id = os.environ.get('API_ID')
api_hash = os.environ.get('API_HASH')
session_name = 'forward_session' # El nombre del archivo de sesión
phone_number = os.environ.get('PHONE_NUMBER')

# --- Configuración de Canales ---
# Los IDs de los canales se leen desde las variables de entorno.
# Deben ser una cadena de texto con los IDs separados por comas, ej: "-100123456,-100789123"
canales_origen_str = os.environ.get('CANALES_ORIGEN', '')
destino_str = os.environ.get('DESTINO')

# --- Validación y Conversión de IDs ---
def convertir_ids(cadena_ids):
    """Convierte una cadena de IDs separados por comas en una lista de enteros."""
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
client = TelegramClient(session_name, api_id, api_hash)

async def reenviar_con_reemplazo(message):
    """
    Procesa un mensaje para reenviarlo. Si contiene texto específico,
    lo reemplaza y envía una copia nueva con la media original.
    Si no, copia el mensaje original para preservar formato y todo lo demás.
    """
    texto_a_reemplazar = 'SersanSistemas'
    texto_reemplazo = 'ASniper'
    
    # Si el mensaje no tiene texto (ej. un sticker o solo una foto sin caption), lo copiamos tal cual.
    if not message.text:
        await client.send_message(destino, message)
        print(f"Mensaje copiado (sin texto) desde {message.chat_id} hacia {destino}")
        return

    texto_original = message.text
    texto_modificado = re.sub(texto_a_reemplazar, texto_reemplazo, texto_original, flags=re.IGNORECASE)

    # Si el texto no cambió, copiamos el mensaje original para preservar todo (formato, botones, etc.)
    if texto_modificado == texto_original:
        await client.send_message(destino, message)
        print(f"Mensaje copiado (sin reemplazo) desde {message.chat_id} hacia {destino}")
    else:
        # Si el texto cambió, enviamos un nuevo mensaje con el texto modificado
        # y la media original. Se perderá el formato de texto (negritas, etc.)
        # pero es la forma más segura de evitar errores con las entidades de formato.
        await client.send_message(
            destino,
            message=texto_modificado,
            file=message.media,
            link_preview=False
        )
        print(f"Mensaje procesado (con reemplazo) desde {message.chat_id} hacia {destino}")


@client.on(events.NewMessage(chats=canales_origen))
async def manejador_nuevo_mensaje(event):
    # Ignorar mensajes de servicio (uniones, salidas, etc.)
    if isinstance(event.message, MessageService):
        return
    await reenviar_con_reemplazo(event.message)

async def sincronizacion_inicial():
    print("--- INICIANDO SINCRONIZACIÓN INICIAL DEL HISTORIAL ---")
    print("Esto puede tardar un tiempo dependiendo de la cantidad de mensajes...")
    for canal in canales_origen:
        print(f"Copiando mensajes del canal {canal}...")
        # Usamos reverse=True para obtener los mensajes desde el más antiguo al más nuevo
        async for message in client.iter_messages(canal, reverse=True):
            # Ignorar mensajes de servicio
            if isinstance(message, MessageService):
                continue
            await reenviar_con_reemplazo(message)
        print(f"Canal {canal} sincronizado.")
    
    # Crear el archivo de control para no volver a sincronizar
    with open(sync_complete_file, 'w') as f:
        f.write('completed')
    print("--- SINCRONIZACIÓN INICIAL COMPLETADA ---")

async def main():
    await client.start(phone=phone_number)
    print("\nSesión iniciada con éxito.")

    if not os.path.exists(sync_complete_file):
        await sincronizacion_inicial()
    else:
        print("El historial ya ha sido sincronizado anteriormente.")

    if not canales_origen:
        print("************************************************************")
        print("ADVERTENCIA: La lista 'canales_origen' está vacía.")
        print("El bot se ejecutará, pero no reenviará ningún mensaje.")
        print("Edita el archivo bot_tsignals.py para añadir los IDs.")
        print("************************************************************")
    
    print(f"Destino configurado: {destino}")
    print("Bot en funcionamiento. Esperando nuevos mensajes...")
    await client.run_until_disconnected()

# Ejecutar el cliente
with client:
    client.loop.run_until_complete(main())