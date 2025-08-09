from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Lee las credenciales desde tu archivo .env local
from dotenv import load_dotenv
import os
load_dotenv()

api_id = os.environ.get('API_ID')
api_hash = os.environ.get('API_HASH')

print("Iniciando generador de sesión...")
print("Se te pedirá tu número de teléfono, código y contraseña (si tienes una).")

# Usamos una sesión en memoria para no interferir con tu archivo .session
with TelegramClient(StringSession(), api_id, api_hash) as client:
    session_string = client.session.save()
    print("\n¡Sesión generada con éxito!\n")
    print("Copia la siguiente cadena de texto completa. Esta es tu variable SESSION_STRING.")
    print("===============================================================================")
    print(session_string)
    print("===============================================================================")
    print("\nGuarda esta cadena en un lugar seguro. La usaremos en el panel de Render.")
