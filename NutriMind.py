# nutribio_app.py
import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import plotly.express as px
from sklearn.linear_model import LinearRegression
from sklearn.cluster import KMeans
import numpy as np
import io
from google.cloud import vision
import base64
from unidecode import unidecode # NUEVO: Para quitar acentosgunhs
import random # NUEVO: Para mensajes aleatorios

st.set_page_config(page_title="NutriBioMind", layout="centered")
st.title("🌱 La regla de oro: ¡30 plantas distintas por semana!")

# --- Credenciales de Google Cloud (sin cambios) ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    google_services_available = True
except Exception as e:
    st.error(f"Error al cargar las credenciales de Google: {e}. Algunas funciones pueden no estar disponibles.")
    google_services_available = False
    creds = None # Asegurar que creds está definido

# --- Configuración de Clientes de Google Cloud ---

# Cliente para gspread (usa oauth2client)
creds_gspread = None
@st.cache_resource(ttl=600) # Cache para evitar reconexiones constantes
def get_sheet(): # <--- SIN PARÁMETROS AQUÍ
    # Accede a 'creds_gspread' y 'google_services_available' directamente
    # ya que están disponibles en el ámbito del módulo.
    if not google_services_available or creds_gspread is None: # Usa la variable global/del módulo
        st.warning("Los servicios de Google (gspread) no están disponibles. No se puede acceder a la hoja de cálculo.")
        return None
    try:
        # Utiliza la variable creds_gspread del ámbito del módulo
        client_gspread = gspread.authorize(creds_gspread) 
        return client_gspread.open("habitos_microbiota").sheet1
    except gspread.exceptions.SpreadsheetNotFound:
        # La variable global creds_info_dict debería estar disponible si las credenciales se cargaron
        email_cuenta_servicio = "EMAIL_NO_ENCONTRADO"
        if creds_info_dict and 'client_email' in creds_info_dict:
            email_cuenta_servicio = creds_info_dict['client_email']
        elif isinstance(st.secrets.get("gcp_service_account"), dict) and "client_email" in st.secrets["gcp_service_account"]:
             # Intento alternativo de obtener el email si creds_info_dict no estuviera poblado globalmente aquí
            email_cuenta_servicio = st.secrets["gcp_service_account"]["client_email"]

        st.error(f"Hoja de cálculo 'habitos_microbiota' no encontrada. "
                 f"Asegúrate de que existe y está compartida con el email de la cuenta de servicio: "
                 f"{email_cuenta_servicio}")
        return None
    except Exception as e:
        st.error(f"No se pudo conectar a Google Sheets: {type(e).__name__} - {e}")
        return None
        
# Cliente para Google Vision (usa google-auth)
vision_client = None

google_services_available = False # Bandera general para saber si los servicios están listos
gcp_secret_content_type_for_error = "unknown" # For debugging

try:
    gcp_secret_content = st.secrets["gcp_service_account"]
    gcp_secret_content_type_for_error = str(type(gcp_secret_content))
    creds_info_dict = None

    if isinstance(gcp_secret_content, str):
        # If the secret is a string, it's likely the full JSON string that needs parsing.
        creds_info_dict = json.loads(gcp_secret_content)
    elif hasattr(gcp_secret_content, 'to_dict') and callable(gcp_secret_content.to_dict):
        # If it's an AttrDict or similar Streamlit secrets object that has a to_dict() method
        creds_info_dict = gcp_secret_content.to_dict()
    elif isinstance(gcp_secret_content, dict):
        # If it's already a plain dictionary (less likely for st.secrets top-level, but possible)
        creds_info_dict = gcp_secret_content
    else:
        # Fallback for other dictionary-like objects (e.g., AttrDict that might not have to_dict directly)
        # Attempt to convert it to a dictionary.
        try:
            creds_info_dict = dict(gcp_secret_content)
        except (TypeError, ValueError) as convert_err:
            st.error(f"El contenido del secreto 'gcp_service_account' no es un string JSON ni un diccionario/AttrDict convertible. Error de conversión: {convert_err}")
            raise ValueError(f"Formato de secreto no compatible: {gcp_secret_content_type_for_error}")


    if creds_info_dict is None or not isinstance(creds_info_dict, dict):
        st.error(f"No se pudo interpretar el contenido del secreto 'gcp_service_account' como un diccionario. Tipo obtenido: {gcp_secret_content_type_for_error}")
        raise ValueError("Fallo al interpretar el secreto como diccionario.")

    # Now creds_info_dict should be a standard Python dictionary

    # 1. Inicializar credenciales para gspread
    scope_gspread = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_gspread = ServiceAccountCredentials.from_json_keyfile_dict(creds_info_dict, scope_gspread)

    # 2. Inicializar cliente de Vision con las credenciales cargadas explícitamente
    from google.oauth2 import service_account as google_service_account
    vision_credentials = google_service_account.Credentials.from_service_account_info(creds_info_dict)
    vision_client = vision.ImageAnnotatorClient(credentials=vision_credentials)

    google_services_available = True
    # st.sidebar.success("Servicios de Google conectados.") # Optional: uncomment for visual feedback

except KeyError:
    st.error("Error Crítico: La clave 'gcp_service_account' no se encontró en los secretos de Streamlit (secrets.toml). "
             "Asegúrate de haberla configurado correctamente.")
except json.JSONDecodeError:
    st.error("Error Crítico: El valor de 'gcp_service_account' (si se interpretó como string) no es un JSON válido. "
             "Verifica la estructura del JSON si lo pegaste como un string completo en secrets.toml.")
except ValueError as ve: # Catch specific ValueErrors from our checks
    st.error(f"Error de configuración o interpretación de secretos: {ve}")
except Exception as e:
    st.error(f"Error inesperado al inicializar los servicios de Google: {e}. "
             f"Tipo de contenido del secreto procesado: {gcp_secret_content_type_for_error}. Algunas funciones podrían no estar disponibles.")


def normalize_text(text):
    if text is None:
        return ""
    return unidecode(str(text)).lower().strip() # Añadido strip()

PLANT_CATEGORIES_KEYS = [
    "🥦 Verduras y hortalizas", "🍎 Frutas", "🌰 Frutos secos y semillas",
    "🫘 Legumbres", "🌾 Cereales y pseudocereales", "🍄 Setas y hongos", "🌿 Hierbas y especias"
]

food_details_db = {
    # Verduras y Hortalizas (Existentes)
    normalize_text("acelga"): {"original_name": "Acelga", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["vitamina K", "magnesio", "fibra", "antioxidantes"], "tags": ["hoja verde", "detox"]},
    normalize_text("apio"): {"original_name": "Apio", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["fibra", "antioxidantes", "electrolitos", "ftalidas (relajante muscular)"], "tags": ["crujiente", "diurético", "bajo en calorías"]},
    normalize_text("berenjena"): {"original_name": "Berenjena", "category_key": "🥦 Verduras y hortalizas", "color": "morado", "pni_benefits": ["nasunina", "fibra", "antioxidantes"], "tags": ["solanacea", "versátil"]},
    normalize_text("brócoli"): {"original_name": "Brócoli", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["sulforafano", "fibra", "vitamina C", "indol-3-carbinol"], "tags": ["cruciferas", "detox", "anticancerígeno potencial"]},
    normalize_text("calabacín"): {"original_name": "Calabacín", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["bajo en calorías", "vitamina A", "fibra", "potasio"], "tags": ["cucurbitacea", "suave", "hidratante"]},
    normalize_text("calabaza"): {"original_name": "Calabaza", "category_key": "🥦 Verduras y hortalizas", "color": "naranja", "pni_benefits": ["betacaroteno", "fibra", "vitamina C", "potasio"], "tags": ["cucurbitacea", "otoño", "dulce", "versátil"]},
    normalize_text("cebolla"): {"original_name": "Cebolla", "category_key": "🥦 Verduras y hortalizas", "color": "varios (blanco, amarillo, morado)", "pni_benefits": ["quercetina", "prebiótico (inulina)", "compuestos azufrados", "aliicina (al cortarla)"], "tags": ["aliacea", "base de sofrito", "inmunidad"]},
    normalize_text("coliflor"): {"original_name": "Coliflor", "category_key": "🥦 Verduras y hortalizas", "color": "blanco", "pni_benefits": ["glucosinolatos", "fibra", "vitamina C", "colina"], "tags": ["cruciferas", "versátil", "bajo en carbohidratos"]},
    normalize_text("espinaca"): {"original_name": "Espinaca", "category_key": "🥦 Verduras y hortalizas", "color": "verde oscuro", "pni_benefits": ["hierro", "folato", "vitamina K", "luteína", "zeaxantina"], "tags": ["hoja verde", "rica en nutrientes", "salud ocular"]},
    normalize_text("pimiento rojo"): {"original_name": "Pimiento Rojo", "category_key": "🥦 Verduras y hortalizas", "color": "rojo", "pni_benefits": ["vitamina C (muy alta)", "capsantina", "betacaroteno", "antioxidantes"], "tags": ["solanacea", "dulce", "vitamina C potente"]},
    normalize_text("puerro"): {"original_name": "Puerro", "category_key": "🥦 Verduras y hortalizas", "color": "verde claro/blanco", "pni_benefits": ["prebiótico (inulina)", "kaempferol", "vitaminas A, C, K"], "tags": ["aliacea", "suave", "sopas y cremas"]},
    normalize_text("tomate"): {"original_name": "Tomate", "category_key": "🥦 Verduras y hortalizas", "color": "rojo", "pni_benefits": ["licopeno", "vitamina C", "potasio", "antioxidantes"], "tags": ["solanacea", "fruta botanicamente", "versátil", "antiinflamatorio"]},
    normalize_text("zanahoria"): {"original_name": "Zanahoria", "category_key": "🥦 Verduras y hortalizas", "color": "naranja", "pni_benefits": ["betacaroteno", "fibra", "vitamina K", "antioxidantes"], "tags": ["raiz", "salud ocular", "crujiente"]},
    normalize_text("ajo"): {"original_name": "Ajo", "category_key": "🥦 Verduras y hortalizas", "color": "blanco", "pni_benefits": ["alicina", "prebiótico", "compuestos azufrados", "inmunomodulador"], "tags": ["aliacea", "especias", "antibacteriano", "inmunidad"]},
    normalize_text("alcachofa"): {"original_name": "Alcachofa", "category_key": "🥦 Verduras y hortalizas", "color": "verde/morado", "pni_benefits": ["cinarina", "fibra prebiótica (inulina)", "silimarina", "antioxidantes"], "tags": ["flor comestible", "detox hepático", "digestiva"]},
    normalize_text("esparrago"): {"original_name": "Espárrago", "category_key": "🥦 Verduras y hortalizas", "color": "verde/blanco/morado", "pni_benefits": ["asparagina", "prebiótico (inulina)", "folato", "glutation"], "tags": ["diurético", "detox", "primavera"]},

    # Nuevas Verduras y Hortalizas
    normalize_text("remolacha"): {"original_name": "Remolacha", "category_key": "🥦 Verduras y hortalizas", "color": "rojo/morado", "pni_benefits": ["nitratos (vasodilatador)", "betanina", "folato", "fibra"], "tags": ["raiz", "colorante natural", "rendimiento deportivo", "detox"]},
    normalize_text("col rizada"): {"original_name": "Col Rizada (Kale)", "category_key": "🥦 Verduras y hortalizas", "color": "verde oscuro", "pni_benefits": ["vitamina K", "vitamina C", "glucosinolatos", "luteína", "zeaxantina"], "tags": ["hoja verde", "cruciferas", "superalimento", "rica en nutrientes"]},
    normalize_text("kale"): {"original_name": "Kale (Col Rizada)", "category_key": "🥦 Verduras y hortalizas", "color": "verde oscuro", "pni_benefits": ["vitamina K", "vitamina C", "glucosinolatos", "luteína", "zeaxantina"], "tags": ["hoja verde", "cruciferas", "superalimento", "rica en nutrientes"]}, # Alias
    normalize_text("nabo"): {"original_name": "Nabo", "category_key": "🥦 Verduras y hortalizas", "color": "blanco/morado", "pni_benefits": ["fibra", "vitamina C", "glucosinolatos"], "tags": ["raiz", "cruciferas", "sabor terroso"]},
    normalize_text("chirivia"): {"original_name": "Chirivía", "category_key": "🥦 Verduras y hortalizas", "color": "blanco crema", "pni_benefits": ["fibra", "potasio", "vitamina C", "folato"], "tags": ["raiz", "dulce", "invierno"]},
    normalize_text("guisante"): {"original_name": "Guisante", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["fibra", "proteína vegetal", "vitamina K", "manganeso"], "tags": ["leguminosa verde", "dulce", "primavera"]}, # Culinariamente verdura
    normalize_text("judia verde"): {"original_name": "Judía Verde", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["fibra", "vitamina K", "vitamina C", "silicio"], "tags": ["leguminosa verde", "crujiente", "baja en calorías"]},
    normalize_text("habas"): {"original_name": "Habas", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["fibra", "proteína vegetal", "folato", "levodopa (precursor dopamina)"], "tags": ["leguminosa verde", "primavera"]}, # Culinariamente verdura
    normalize_text("pimiento verde"): {"original_name": "Pimiento Verde", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["vitamina C", "fibra", "clorofila"], "tags": ["solanacea", "sabor más amargo que otros pimientos"]},
    normalize_text("pimiento amarillo"): {"original_name": "Pimiento Amarillo", "category_key": "🥦 Verduras y hortalizas", "color": "amarillo", "pni_benefits": ["vitamina C (alta)", "betacaroteno", "luteína", "zeaxantina"], "tags": ["solanacea", "dulce", "antioxidante"]},
    normalize_text("cebolla morada"): {"original_name": "Cebolla Morada", "category_key": "🥦 Verduras y hortalizas", "color": "morado", "pni_benefits": ["quercetina", "antocianinas", "prebiótico"], "tags": ["aliacea", "color vibrante", "cruda en ensaladas"]},
    normalize_text("cebolleta"): {"original_name": "Cebolleta", "category_key": "🥦 Verduras y hortalizas", "color": "blanco/verde", "pni_benefits": ["flavonoides", "vitamina K", "fibra"], "tags": ["aliacea", "suave", "fresca"]},
    normalize_text("chalota"): {"original_name": "Chalota", "category_key": "🥦 Verduras y hortalizas", "color": "marrón/morado claro", "pni_benefits": ["compuestos azufrados", "antioxidantes", "vitaminas B"], "tags": ["aliacea", "sabor delicado", "gourmet"]},
    normalize_text("rabano"): {"original_name": "Rábano", "category_key": "🥦 Verduras y hortalizas", "color": "rojo/blanco/negro", "pni_benefits": ["glucosinolatos", "vitamina C", "fibra", "efecto detoxificante"], "tags": ["raiz", "cruciferas", "picante", "digestivo"]},
    normalize_text("endivia"): {"original_name": "Endivia", "category_key": "🥦 Verduras y hortalizas", "color": "blanco/amarillo claro", "pni_benefits": ["inulina (prebiótico)", "folato", "vitamina K"], "tags": ["hoja amarga", "digestiva", "achicoria"]},
    normalize_text("escarola"): {"original_name": "Escarola", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["fibra", "folato", "vitamina A", "intibina (amargor)"], "tags": ["hoja amarga", "invierno", "digestiva"]},
    normalize_text("lechuga iceberg"): {"original_name": "Lechuga Iceberg", "category_key": "🥦 Verduras y hortalizas", "color": "verde claro", "pni_benefits": ["agua (hidratante)", "baja en calorías", "fibra (menor que otras hojas)"], "tags": ["hoja crujiente", "ensaladas"]},
    normalize_text("lechuga romana"): {"original_name": "Lechuga Romana", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["vitamina K", "vitamina A", "folato", "fibra"], "tags": ["hoja verde", "ensaladas", "crujiente"]},
    normalize_text("canonigos"): {"original_name": "Canónigos", "category_key": "🥦 Verduras y hortalizas", "color": "verde oscuro", "pni_benefits": ["vitamina C", "betacaroteno", "hierro", "ácido fólico"], "tags": ["hoja verde", "sabor suave", "delicada"]},
    normalize_text("rucula"): {"original_name": "Rúcula", "category_key": "🥦 Verduras y hortalizas", "color": "verde oscuro", "pni_benefits": ["glucosinolatos", "vitamina K", "nitratos", "antioxidantes"], "tags": ["hoja verde", "sabor picante", "cruciferas"]},
    normalize_text("boniato"): {"original_name": "Boniato (Batata)", "category_key": "🥦 Verduras y hortalizas", "color": "naranja/morado/blanco", "pni_benefits": ["betacaroteno (naranja)", "antocianinas (morado)", "fibra", "vitamina C", "manganeso"], "tags": ["tuberculo", "dulce", "antiinflamatorio", "versátil"]},
    normalize_text("batata"): {"original_name": "Batata (Boniato)", "category_key": "🥦 Verduras y hortalizas", "color": "naranja/morado/blanco", "pni_benefits": ["betacaroteno (naranja)", "antocianinas (morado)", "fibra", "vitamina C", "manganeso"], "tags": ["tuberculo", "dulce", "antiinflamatorio", "versátil"]}, # Alias
    normalize_text("patata"): {"original_name": "Patata", "category_key": "🥦 Verduras y hortalizas", "color": "varios", "pni_benefits": ["potasio", "vitamina C", "almidón resistente (enfriada)", "vitamina B6"], "tags": ["tuberculo", "versátil", "fuente de energía", "solanacea"]}, # Mejor consumirla enfriada para el almidón resistente
    normalize_text("hinojo"): {"original_name": "Hinojo", "category_key": "🥦 Verduras y hortalizas", "color": "blanco/verde claro", "pni_benefits": ["anetol (digestivo)", "fibra", "vitamina C", "potasio"], "tags": ["bulbo", "sabor anisado", "digestivo", "carminativo"]},
    normalize_text("pak choi"): {"original_name": "Pak Choi (Bok Choy)", "category_key": "🥦 Verduras y hortalizas", "color": "verde/blanco", "pni_benefits": ["glucosinolatos", "vitamina C", "vitamina K", "calcio"], "tags": ["col china", "cruciferas", "salteados", "suave"]},
    normalize_text("bok choy"): {"original_name": "Bok Choy (Pak Choi)", "category_key": "🥦 Verduras y hortalizas", "color": "verde/blanco", "pni_benefits": ["glucosinolatos", "vitamina C", "vitamina K", "calcio"], "tags": ["col china", "cruciferas", "salteados", "suave"]}, # Alias
    normalize_text("coles de bruselas"): {"original_name": "Coles de Bruselas", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["glucosinolatos", "fibra", "vitamina K", "vitamina C", "antioxidantes"], "tags": ["cruciferas", "detox", "sabor amargo/dulce al cocinar"]},
    normalize_text("tirabeque"): {"original_name": "Tirabeque", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["fibra", "vitamina C", "vitamina A", "hierro"], "tags": ["leguminosa verde", "crujiente", "dulce", "se come entero"]},
    normalize_text("okra"): {"original_name": "Okra", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["mucílago (fibra soluble)", "vitamina K", "folato", "antioxidantes"], "tags": ["textura mucilaginosa", "espesante", "cocina sureña/india/africana"]},
    normalize_text("cardo"): {"original_name": "Cardo", "category_key": "🥦 Verduras y hortalizas", "color": "verde/blanco", "pni_benefits": ["cinarina", "silimarina", "fibra", "potasio"], "tags": ["similar alcachofa", "depurativo", "invierno"]},
    normalize_text("borraja"): {"original_name": "Borraja", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["mucílago", "vitamina C", "potasio", "ácido gamma-linolénico (semillas)"], "tags": ["mucilaginosa", "diurética", "tradicional"]},
    normalize_text("grelos"): {"original_name": "Grelos", "category_key": "🥦 Verduras y hortalizas", "color": "verde oscuro", "pni_benefits": ["glucosinolatos", "vitamina K", "folato", "hierro"], "tags": ["hojas de nabo", "sabor amargo", "tradicional gallega", "cruciferas"]},
    normalize_text("pepino"): {"original_name": "Pepino", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["hidratante (alto contenido de agua)", "sílice (piel)", "cucurbitacinas", "electrolitos"], "tags": ["cucurbitacea", "refrescante", "ensaladas", "bajo en calorías"]},
    normalize_text("rábano picante"): {"original_name": "Rábano Picante (Horseradish)", "category_key": "🥦 Verduras y hortalizas", "color": "blanco/beige", "pni_benefits": ["sinigrina (glucosinolato)", "propiedades antibacterianas", "descongestionante"], "tags": ["raiz", "muy picante", "condimento", "cruciferas"]},
    normalize_text("wasabi"): {"original_name": "Wasabi (raíz)", "category_key": "🥦 Verduras y hortalizas", "color": "verde claro", "pni_benefits": ["isotiocianatos (antibacterianos, antiinflamatorios)", "propiedades antimicrobianas"], "tags": ["raiz", "muy picante", "condimento japonés", "cruciferas"]}, # Auténtico, no la pasta de rábano picante teñida
    normalize_text("col lombarda"): {"original_name": "Col Lombarda", "category_key": "🥦 Verduras y hortalizas", "color": "morado", "pni_benefits": ["antocianinas", "vitamina C", "fibra", "glucosinolatos"], "tags": ["cruciferas", "color vibrante", "antioxidante"]},
    normalize_text("berros"): {"original_name": "Berros", "category_key": "🥦 Verduras y hortalizas", "color": "verde oscuro", "pni_benefits": ["feniletil isotiocianato (PEITC)", "vitamina K", "vitamina C", "antioxidantes"], "tags": ["hoja verde", "cruciferas", "sabor picante", "depurativo"]},
    normalize_text("diente de leon (hojas)"): {"original_name": "Diente de León (hojas)", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["vitaminas A, C, K", "hierro", "calcio", "prebiótico (inulina en raíz)", "efecto diurético"], "tags": ["hoja amarga", "silvestre comestible", "depurativo", "nutritivo"]},
    normalize_text("topinambur"): {"original_name": "Topinambur (Alcachofa de Jerusalén)", "category_key": "🥦 Verduras y hortalizas", "color": "marrón claro/amarillo", "pni_benefits": ["inulina (alto contenido, prebiótico)", "hierro", "potasio"], "tags": ["tuberculo", "prebiótico potente", "sabor dulce anuezado", "produce gases en algunos"]},


    # Frutas (Existentes y Nuevas)
    normalize_text("manzana"): {"original_name": "Manzana", "category_key": "🍎 Frutas", "color": "varios (rojo, verde, amarillo)", "pni_benefits": ["pectina (fibra soluble, prebiótico)", "quercetina", "vitamina C", "antioxidantes"], "tags": ["con piel", "salud intestinal", "versátil"]},
    normalize_text("platano"): {"original_name": "Plátano", "category_key": "🍎 Frutas", "color": "amarillo", "pni_benefits": ["potasio", "vitamina B6", "prebiótico (si no muy maduro - almidón resistente)", "triptófano"], "tags": ["energético", "salud muscular", "estado de ánimo"]},
    normalize_text("naranja"): {"original_name": "Naranja", "category_key": "🍎 Frutas", "color": "naranja", "pni_benefits": ["vitamina C", "hesperidina", "fibra (si se come entera)", "folato"], "tags": ["cítrico", "inmunidad", "antioxidante"]},
    normalize_text("fresa"): {"original_name": "Fresa", "category_key": "🍎 Frutas", "color": "rojo", "pni_benefits": ["antocianinas", "vitamina C", "manganeso", "fisetin"], "tags": ["baya", "antioxidante", "antiinflamatoria", "delicada"]},
    normalize_text("arandano"): {"original_name": "Arándano", "category_key": "🍎 Frutas", "color": "azul/morado", "pni_benefits": ["antocianinas (muy alta)", "pterostilbeno", "antioxidantes potentes", "salud cerebral"], "tags": ["baya", "superfood", "antiinflamatorio", "salud urinaria (arándano rojo)"]},
    normalize_text("kiwi"): {"original_name": "Kiwi", "category_key": "🍎 Frutas", "color": "verde (pulpa)/marrón (piel)", "pni_benefits": ["vitamina C (muy alta)", "actinidina (enzima digestiva)", "fibra", "serotonina"], "tags": ["digestivo", "inmunidad", "rico en vitamina C"]},
    normalize_text("mango"): {"original_name": "Mango", "category_key": "🍎 Frutas", "color": "naranja/amarillo/rojo", "pni_benefits": ["vitamina A (betacaroteno)", "vitamina C", "mangiferina (antioxidante)", "fibra"], "tags": ["tropical", "antioxidante", "dulce"]},
    normalize_text("aguacate"): {"original_name": "Aguacate", "category_key": "🍎 Frutas", "color": "verde (pulpa)/negro-verde (piel)", "pni_benefits": ["grasas saludables (ácido oleico)", "fibra", "potasio", "vitamina E", "folato"], "tags": ["grasa monoinsaturada", "salud cardiovascular", "antiinflamatorio", "fruta botanicamente"]},
    normalize_text("limon"): {"original_name": "Limón", "category_key": "🍎 Frutas", "color": "amarillo", "pni_benefits": ["vitamina C", "limonoides", "flavonoides", "efecto alcalinizante (en el cuerpo)"], "tags": ["cítrico", "detox", "antioxidante", "ácido"]},
    normalize_text("lima"): {"original_name": "Lima", "category_key": "🍎 Frutas", "color": "verde", "pni_benefits": ["vitamina C", "flavonoides", "antioxidantes"], "tags": ["cítrico", "refrescante", "cócteles", "ácida"]},
    normalize_text("pomelo"): {"original_name": "Pomelo", "category_key": "🍎 Frutas", "color": "rosa/rojo/blanco", "pni_benefits": ["vitamina C", "licopeno (rosa/rojo)", "naringenina", "fibra"], "tags": ["cítrico", "amargo", "interacción con medicamentos", "quema grasa (popular)"]},
    normalize_text("mandarina"): {"original_name": "Mandarina", "category_key": "🍎 Frutas", "color": "naranja", "pni_benefits": ["vitamina C", "nobiletina", "fibra", "criptoxantina"], "tags": ["cítrico", "fácil de pelar", "dulce"]},
    normalize_text("uva"): {"original_name": "Uva", "category_key": "🍎 Frutas", "color": "varios (verde, roja, negra)", "pni_benefits": ["resveratrol (piel uvas oscuras)", "antocianinas (uvas oscuras)", "quercetina", "antioxidantes"], "tags": ["baya", "antioxidante", "salud cardiovascular"]},
    normalize_text("melon"): {"original_name": "Melón", "category_key": "🍎 Frutas", "color": "varios (verde, naranja, amarillo)", "pni_benefits": ["hidratante (alto contenido de agua)", "vitamina C", "potasio", "betacaroteno (cantalupo)"], "tags": ["cucurbitacea", "verano", "refrescante", "diurético"]},
    normalize_text("sandia"): {"original_name": "Sandía", "category_key": "🍎 Frutas", "color": "rojo/rosa (pulpa), verde (corteza)", "pni_benefits": ["licopeno", "citrulina (vasodilatador)", "hidratante (muy alta en agua)", "vitamina C"], "tags": ["cucurbitacea", "verano", "refrescante", "hidratación"]},
    normalize_text("piña"): {"original_name": "Piña", "category_key": "🍎 Frutas", "color": "amarillo (pulpa)", "pni_benefits": ["bromelina (enzima digestiva, antiinflamatoria)", "vitamina C", "manganeso"], "tags": ["tropical", "digestiva", "antiinflamatoria"]},
    normalize_text("papaya"): {"original_name": "Papaya", "category_key": "🍎 Frutas", "color": "naranja (pulpa)", "pni_benefits": ["papaína (enzima digestiva)", "vitamina C", "betacaroteno", "licopeno"], "tags": ["tropical", "digestiva", "antioxidante"]},
    normalize_text("granada"): {"original_name": "Granada", "category_key": "🍎 Frutas", "color": "rojo (arilos y cáscara)", "pni_benefits": ["punicalaginas (potente antioxidante)", "ácido púnicico", "antiinflamatoria", "vitamina C"], "tags": ["superfruta", "antioxidante potente", "otoño"]},
    normalize_text("higo"): {"original_name": "Higo", "category_key": "🍎 Frutas", "color": "morado/verde/negro", "pni_benefits": ["fibra (laxante suave)", "calcio", "potasio", "polifenoles"], "tags": ["dulce", "fibra", "otoño"]},
    normalize_text("cereza"): {"original_name": "Cereza", "category_key": "🍎 Frutas", "color": "rojo/negro", "pni_benefits": ["antocianinas", "melatonina (ayuda al sueño)", "antiinflamatoria", "vitamina C"], "tags": ["baya (drupa)", "antiinflamatoria", "ácido úrico", "verano"]},
    normalize_text("ciruela"): {"original_name": "Ciruela", "category_key": "🍎 Frutas", "color": "varios (rojo, morado, amarillo)", "pni_benefits": ["fibra (sorbitol - laxante)", "antioxidantes", "vitamina K", "potasio"], "tags": ["laxante natural", "fibra", "verano"]},
    normalize_text("melocoton"): {"original_name": "Melocotón", "category_key": "🍎 Frutas", "color": "amarillo/naranja/rojo", "pni_benefits": ["vitamina C", "betacaroteno", "fibra", "antioxidantes"], "tags": ["verano", "dulce", "piel aterciopelada"]},
    normalize_text("albaricoque"): {"original_name": "Albaricoque", "category_key": "🍎 Frutas", "color": "naranja", "pni_benefits": ["betacaroteno", "vitamina C", "fibra", "catequinas"], "tags": ["verano", "dulce", "salud ocular"]},
    normalize_text("frambuesa"): {"original_name": "Frambuesa", "category_key": "🍎 Frutas", "color": "rojo/rosa", "pni_benefits": ["cetonas de frambuesa (discutido)", "ácido elágico", "antocianinas", "fibra", "vitamina C"], "tags": ["baya", "antioxidante", "baja en azúcar"]},
    normalize_text("mora"): {"original_name": "Mora", "category_key": "🍎 Frutas", "color": "negro/morado oscuro", "pni_benefits": ["antocianinas (muy alta)", "vitamina C", "vitamina K", "fibra"], "tags": ["baya", "antioxidante potente", "verano"]},
    normalize_text("kaki"): {"original_name": "Kaki (Persimón)", "category_key": "🍎 Frutas", "color": "naranja", "pni_benefits": ["vitamina A", "vitamina C", "fibra", "taninos (astringente si no maduro)", "antioxidantes"], "tags": ["otoño", "dulce", "fibra"]},
    normalize_text("chirimoya"): {"original_name": "Chirimoya", "category_key": "🍎 Frutas", "color": "verde (piel), blanco (pulpa)", "pni_benefits": ["vitamina C", "vitamina B6", "fibra", "annonacina"], "tags": ["tropical", "dulce", "textura cremosa"]},
    normalize_text("maracuya"): {"original_name": "Maracuyá (Fruta de la pasión)", "category_key": "🍎 Frutas", "color": "morado/amarillo (piel), amarillo/naranja (pulpa)", "pni_benefits": ["vitamina C", "vitamina A", "fibra", "flavonoides"], "tags": ["tropical", "ácido/dulce", "aromático"]},
    normalize_text("lichi"): {"original_name": "Lichi", "category_key": "🍎 Frutas", "color": "rojo (piel), blanco translúcido (pulpa)", "pni_benefits": ["vitamina C", "oligopeptidos", "flavonoides"], "tags": ["tropical", "dulce", "aromático"]},

    # Frutos secos y semillas (Existentes y Nuevas)
    normalize_text("almendra"): {"original_name": "Almendra", "category_key": "🌰 Frutos secos y semillas", "color": "marrón (piel), blanco (interior)", "pni_benefits": ["vitamina E", "grasas saludables (monoinsaturadas)", "fibra", "magnesio", "proteína"], "tags": ["fruto seco", "salud cardiovascular", "piel sana"]},
    normalize_text("nuez"): {"original_name": "Nuez", "category_key": "🌰 Frutos secos y semillas", "color": "marrón claro", "pni_benefits": ["omega-3 (ALA)", "antioxidantes (polifenoles)", "melatonina", "salud cerebral"], "tags": ["fruto seco", "cerebro", "antiinflamatorio"]},
    normalize_text("semilla de chia"): {"original_name": "Semilla de Chía", "category_key": "🌰 Frutos secos y semillas", "color": "gris/negro/blanco", "pni_benefits": ["omega-3 (ALA)", "fibra soluble (mucílago)", "calcio", "proteína"], "tags": ["semilla", "superfood", "gelificante", "salud intestinal"]},
    normalize_text("semilla de lino"): {"original_name": "Semilla de Lino", "category_key": "🌰 Frutos secos y semillas", "color": "marrón/dorado", "pni_benefits": ["omega-3 (ALA)", "lignanos (fitoestrógenos)", "fibra soluble e insoluble"], "tags": ["semilla", "moler para absorber", "salud hormonal", "salud intestinal"]},
    normalize_text("pipa de calabaza"): {"original_name": "Pipa de Calabaza", "category_key": "🌰 Frutos secos y semillas", "color": "verde oscuro", "pni_benefits": ["magnesio", "zinc", "grasas saludables", "cucurbitina (antiparasitario leve)"], "tags": ["semilla", "salud prostática", "magnesio"]},
    normalize_text("anacardo"): {"original_name": "Anacardo", "category_key": "🌰 Frutos secos y semillas", "color": "blanco crema", "pni_benefits": ["magnesio", "cobre", "grasas monoinsaturadas", "triptófano"], "tags": ["fruto seco", "textura cremosa", "versátil"]}, # Crudos son tóxicos, siempre tostados/cocidos
    normalize_text("nuez de brasil"): {"original_name": "Nuez de Brasil", "category_key": "🌰 Frutos secos y semillas", "color": "marrón oscuro (piel), blanco (interior)", "pni_benefits": ["selenio (muy alta - 1-2 al día suficiente)", "grasas saludables", "vitamina E"], "tags": ["fruto seco", "selenio", "tiroides", "moderación"]},
    normalize_text("pistacho"): {"original_name": "Pistacho", "category_key": "🌰 Frutos secos y semillas", "color": "verde/morado (nuez), beige (cáscara)", "pni_benefits": ["vitamina B6", "luteína", "zeaxantina", "grasas saludables", "fibra"], "tags": ["fruto seco", "salud ocular", "colorido"]},
    normalize_text("avellana"): {"original_name": "Avellana", "category_key": "🌰 Frutos secos y semillas", "color": "marrón", "pni_benefits": ["vitamina E", "grasas monoinsaturadas", "manganeso", "folato"], "tags": ["fruto seco", "salud cardiovascular", "sabor dulce"]},
    normalize_text("semilla de girasol"): {"original_name": "Semilla de Girasol (Pipa)", "category_key": "🌰 Frutos secos y semillas", "color": "gris/negro (cáscara), blanco (semilla)", "pni_benefits": ["vitamina E", "selenio", "magnesio", "grasas saludables"], "tags": ["semilla", "vitamina E", "antiinflamatorio"]},
    normalize_text("semilla de sesamo"): {"original_name": "Semilla de Sésamo (Ajonjolí)", "category_key": "🌰 Frutos secos y semillas", "color": "blanco/negro/marrón", "pni_benefits": ["calcio", "hierro", "magnesio", "lignanos (sesamina, sesamolina)"], "tags": ["semilla", "calcio", "tahini", "antioxidante"]},
    normalize_text("semilla de cañamo"): {"original_name": "Semilla de Cáñamo", "category_key": "🌰 Frutos secos y semillas", "color": "verde/marrón claro", "pni_benefits": ["proteína completa", "omega-3 y omega-6 (ratio ideal)", "fibra", "vitamina E"], "tags": ["semilla", "proteína vegetal", "superfood", "sin CBD/THC psicoactivo"]},
    normalize_text("nuez pecana"): {"original_name": "Nuez Pecana", "category_key": "🌰 Frutos secos y semillas", "color": "marrón", "pni_benefits": ["antioxidantes", "grasas monoinsaturadas", "zinc", "vitamina E"], "tags": ["fruto seco", "dulce", "salud cardiovascular"]},
    normalize_text("nuez de macadamia"): {"original_name": "Nuez de Macadamia", "category_key": "🌰 Frutos secos y semillas", "color": "blanco crema", "pni_benefits": ["grasas monoinsaturadas (ácido palmitoleico)", "fibra", "manganeso"], "tags": ["fruto seco", "rica en grasa saludable", "textura mantecosa", "cara"]},


    # Legumbres (Existentes y Nuevas)
    normalize_text("lenteja"): {"original_name": "Lenteja", "category_key": "🫘 Legumbres", "color": "varios (marrón, verde, roja, negra)", "pni_benefits": ["fibra (soluble e insoluble)", "proteína vegetal", "hierro", "folato", "prebiótico"], "tags": ["versátil", "económica", "rica en nutrientes"]},
    normalize_text("garbanzo"): {"original_name": "Garbanzo", "category_key": "🫘 Legumbres", "color": "beige", "pni_benefits": ["fibra", "proteína vegetal", "manganeso", "folato", "almidón resistente (enfriado)"], "tags": ["versátil", "hummus", "salud intestinal"]},
    normalize_text("judia negra"): {"original_name": "Judía Negra", "category_key": "🫘 Legumbres", "color": "negro", "pni_benefits": ["fibra", "antocianinas", "proteína vegetal", "molibdeno"], "tags": ["antioxidante", "rica en fibra", "cocina latina"]},
    normalize_text("judia pinta"): {"original_name": "Judía Pinta", "category_key": "🫘 Legumbres", "color": "marrón rojizo con motas", "pni_benefits": ["fibra", "proteína vegetal", "folato", "hierro"], "tags": ["tradicional", "rica en fibra"]},
    normalize_text("judia blanca"): {"original_name": "Judía Blanca (Alubia)", "category_key": "🫘 Legumbres", "color": "blanco", "pni_benefits": ["fibra", "proteína vegetal", "fósforo", "molibdeno"], "tags": ["versátil", "textura cremosa"]},
    normalize_text("soja"): {"original_name": "Soja (Haba)", "category_key": "🫘 Legumbres", "color": "amarillo/verde (edamame)", "pni_benefits": ["proteína completa", "isoflavonas (fitoestrógenos)", "fibra", "ácidos grasos omega-3 y omega-6"], "tags": ["proteína vegetal", "versátil (tofu, tempeh, miso, edamame)", "salud hormonal (discutido)"]},
    normalize_text("edamame"): {"original_name": "Edamame (Haba de Soja Verde)", "category_key": "🫘 Legumbres", "color": "verde", "pni_benefits": ["proteína completa", "fibra", "folato", "vitamina K", "isoflavonas"], "tags": ["snack saludable", "japonés", "proteína vegetal"]}, # Técnicamente una forma de soja
    normalize_text("azuki"): {"original_name": "Azuki (Judía Roja Japonesa)", "category_key": "🫘 Legumbres", "color": "rojo oscuro", "pni_benefits": ["fibra", "proteína vegetal", "molibdeno", "antioxidantes"], "tags": ["dulce natural", "cocina asiática", "postres saludables"]},
    normalize_text("lupino"): {"original_name": "Lupino (Altramuz)", "category_key": "🫘 Legumbres", "color": "amarillo", "pni_benefits": ["proteína muy alta", "fibra", "prebiótico", "aminoácidos esenciales"], "tags": ["aperitivo", "salmuera", "alto en proteína", "legumbre"]},

    # Cereales y pseudocereales (Existentes y Nuevas)
    normalize_text("avena"): {"original_name": "Avena", "category_key": "🌾 Cereales y pseudocereales", "color": "beige", "pni_benefits": ["betaglucanos (fibra soluble)", "prebiótico", "avenantramidas (antioxidantes)", "manganeso"], "tags": ["integral", "desayuno", "salud cardiovascular", "energía sostenida"]},
    normalize_text("quinoa"): {"original_name": "Quinoa", "category_key": "🌾 Cereales y pseudocereales", "color": "varios (blanca, roja, negra)", "pni_benefits": ["proteína completa (todos los aminoácidos esenciales)", "fibra", "hierro", "magnesio", "flavonoides (quercetina, kaempferol)"], "tags": ["pseudocereal", "sin gluten", "versátil", "rica en nutrientes"]},
    normalize_text("arroz integral"): {"original_name": "Arroz Integral", "category_key": "🌾 Cereales y pseudocereales", "color": "marrón", "pni_benefits": ["fibra", "magnesio", "selenio", "manganeso", "índice glucémico más bajo que el blanco"], "tags": ["integral", "grano entero", "versátil"]},
    normalize_text("trigo sarraceno"): {"original_name": "Trigo Sarraceno (Alforfón)", "category_key": "🌾 Cereales y pseudocereales", "color": "marrón/grisáceo", "pni_benefits": ["rutina (flavonoide, salud vascular)", "magnesio", "fibra", "D-chiro-inositol (regulación glucosa)"], "tags": ["pseudocereal", "sin gluten", "alforfón", "sabor intenso"]},
    normalize_text("mijo"): {"original_name": "Mijo", "category_key": "🌾 Cereales y pseudocereales", "color": "amarillo claro", "pni_benefits": ["magnesio", "fósforo", "fibra", "antioxidantes", "alcalinizante"], "tags": ["pseudocereal", "sin gluten", "versátil", "fácil digestión"]},
    normalize_text("amaranto"): {"original_name": "Amaranto", "category_key": "🌾 Cereales y pseudocereales", "color": "beige/dorado", "pni_benefits": ["proteína completa (lisina)", "calcio", "hierro", "fibra", "escualeno"], "tags": ["pseudocereal", "sin gluten", "rico en proteínas", "ancestral"]},
    normalize_text("arroz salvaje"): {"original_name": "Arroz Salvaje", "category_key": "🌾 Cereales y pseudocereales", "color": "negro/marrón oscuro", "pni_benefits": ["fibra (alta)", "proteína", "antioxidantes", "magnesio"], "tags": ["semilla acuática", "no es arroz verdadero", "textura firme", "sabor anuezado"]},
    normalize_text("centeno"): {"original_name": "Centeno", "category_key": "🌾 Cereales y pseudocereales", "color": "marrón grisáceo", "pni_benefits": ["fibra (alta)", "lignanos", "magnesio", "manganeso"], "tags": ["cereal con gluten", "pan denso", "sabor fuerte"]},
    normalize_text("espelta"): {"original_name": "Espelta", "category_key": "🌾 Cereales y pseudocereales", "color": "marrón claro", "pni_benefits": ["fibra", "proteína", "vitaminas B", "mejor tolerada que el trigo común por algunos"], "tags": ["trigo ancestral", "con gluten (diferente al trigo moderno)", "sabor anuezado"]},
    normalize_text("sorgo"): {"original_name": "Sorgo", "category_key": "🌾 Cereales y pseudocereales", "color": "varios (blanco, rojo, marrón)", "pni_benefits": ["fibra", "antioxidantes (taninos en variedades oscuras)", "hierro", "fósforo"], "tags": ["cereal", "sin gluten", "versátil (harina, grano entero)", "resistente a la sequía"]},
    normalize_text("teff"): {"original_name": "Teff", "category_key": "🌾 Cereales y pseudocereales", "color": "varios (blanco, marrón, rojo)", "pni_benefits": ["hierro", "calcio", "proteína", "fibra", "almidón resistente"], "tags": ["pseudocereal", "sin gluten", "grano diminuto", "base del injera etíope"]},


    # Setas y hongos (Existentes y Nuevas)
    normalize_text("champiñon"): {"original_name": "Champiñón (Portobello, Cremini)", "category_key": "🍄 Setas y hongos", "color": "blanco/marrón", "pni_benefits": ["selenio", "vitaminas B (B2, B3, B5)", "betaglucanos", "ergotioneína (antioxidante)"], "tags": ["versátil", "común", "bajo en calorías"]},
    normalize_text("shiitake"): {"original_name": "Shiitake", "category_key": "🍄 Setas y hongos", "color": "marrón", "pni_benefits": ["lentinano (betaglucano inmunomodulador)", "eritadenina (colesterol)", "vitamina D (si expuesto al sol)", "cobre"], "tags": ["medicinal", "sabor umami", "inmunidad"]},
    normalize_text("seta de ostra"): {"original_name": "Seta de Ostra", "category_key": "🍄 Setas y hongos", "color": "varios (gris, rosa, amarillo)", "pni_benefits": ["betaglucanos", "lovastatina natural (colesterol)", "niacina", "antioxidantes"], "tags": ["sabor suave", "textura delicada", "fácil de cultivar"]},
    normalize_text("maitake"): {"original_name": "Maitake (Grifola frondosa)", "category_key": "🍄 Setas y hongos", "color": "marrón/gris", "pni_benefits": ["grifolano (betaglucano)", "factor D-fracción (inmunidad, antitumoral potencial)", "regulación glucosa"], "tags": ["medicinal", "adaptógeno", "inmunidad"]},
    normalize_text("reishi"): {"original_name": "Reishi (Ganoderma lucidum)", "category_key": "🍄 Setas y hongos", "color": "rojo/marrón brillante", "pni_benefits": ["triterpenos (antiinflamatorio, antihistamínico)", "polisacáridos (inmunomodulador)", "adaptógeno", "calmante"], "tags": ["medicinal", "no culinario (amargo)", "extracto/polvo", "longevidad"]},
    normalize_text("enoki"): {"original_name": "Enoki", "category_key": "🍄 Setas y hongos", "color": "blanco", "pni_benefits": ["fibra", "vitaminas B", "antioxidantes", "proflamina (potencial antitumoral)"], "tags": ["largas y finas", "crujientes", "cocina asiática", "sopas"]},
    normalize_text("melena de leon"): {"original_name": "Melena de León (Hericium erinaceus)", "category_key": "🍄 Setas y hongos", "color": "blanco", "pni_benefits": ["hericenonas y erinacinas (neuroprotector, estimula NGF)", "salud digestiva", "inmunomodulador"], "tags": ["medicinal", "nootrópico", "salud cerebral", "sabor similar al marisco"]},
    normalize_text("cordyceps"): {"original_name": "Cordyceps", "category_key": "🍄 Setas y hongos", "color": "naranja/marrón", "pni_benefits": ["cordicepina (energía, antiinflamatorio)", "adenosina", "polisacáridos", "rendimiento físico"], "tags": ["medicinal", "adaptógeno", "energizante", "resistencia"]},
    normalize_text("trufa"): {"original_name": "Trufa (negra, blanca)", "category_key": "🍄 Setas y hongos", "color": "negro/blanco/marrón", "pni_benefits": ["antioxidantes", "compuestos fenólicos", "fibra", "minerales (pequeñas cantidades)"], "tags": ["gourmet", "aroma intenso", "condimento caro", "afrodisíaco (popular)"]},


    # Hierbas y especias (Existentes y Nuevas)
    normalize_text("curcuma"): {"original_name": "Cúrcuma", "category_key": "🌿 Hierbas y especias", "color": "naranja", "pni_benefits": ["curcumina (potente antiinflamatorio)", "antioxidante", "mejora función endotelial"], "tags": ["especia", "con pimienta negra (para absorción)", "antiinflamatorio", "dorada"]},
    normalize_text("jengibre"): {"original_name": "Jengibre", "category_key": "🌿 Hierbas y especias", "color": "amarillo claro (interior)", "pni_benefits": ["gingerol (antiinflamatorio, antioxidante)", "antinauseas", "mejora digestión", "termogénico"], "tags": ["raiz", "especia", "picante", "digestivo"]},
    normalize_text("perejil"): {"original_name": "Perejil", "category_key": "🌿 Hierbas y especias", "color": "verde", "pni_benefits": ["vitamina K", "vitamina C", "apiol", "miristicina", "apigenina (flavonoide)"], "tags": ["hierba fresca", "decoración", "diurético suave"]},
    normalize_text("cilantro"): {"original_name": "Cilantro (hojas y semillas)", "category_key": "🌿 Hierbas y especias", "color": "verde (hojas), marrón (semillas)", "pni_benefits": ["antioxidantes (hojas)", "quelante suave de metales pesados (hojas)", "digestivo (semillas)", "linalol"], "tags": ["hierba fresca", "especia (semilla)", "sabor distintivo (amor/odio)"]},
    normalize_text("canela"): {"original_name": "Canela (Cassia y Ceylan)", "category_key": "🌿 Hierbas y especias", "color": "marrón", "pni_benefits": ["cinamaldehído (antioxidante, antimicrobiano)", "regulación glucosa", "antiinflamatorio"], "tags": ["especia", "ceylan mejor (menos cumarina)", "dulce", "postres"]},
    normalize_text("oregano"): {"original_name": "Orégano", "category_key": "🌿 Hierbas y especias", "color": "verde", "pni_benefits": ["carvacrol y timol (potentes antimicrobianos)", "antioxidantes", "antiinflamatorio"], "tags": ["hierba", "especia", "cocina mediterránea", "antimicrobiano"]},
    normalize_text("albahaca"): {"original_name": "Albahaca", "category_key": "🌿 Hierbas y especias", "color": "verde", "pni_benefits": ["eugenol (antiinflamatorio)", "linalol", "flavonoides", "adaptógeno (albahaca sagrada/tulsi)"], "tags": ["hierba fresca", "aromática", "cocina italiana", "pesto"]},
    normalize_text("menta"): {"original_name": "Menta / Hierbabuena", "category_key": "🌿 Hierbas y especias", "color": "verde", "pni_benefits": ["mentol (descongestionante, digestivo)", "ácido rosmarínico", "antiespasmódico", "refrescante"], "tags": ["hierba fresca", "digestiva", "aromática", "infusiones"]},
    normalize_text("romero"): {"original_name": "Romero", "category_key": "🌿 Hierbas y especias", "color": "verde", "pni_benefits": ["ácido carnósico y carnosol (antioxidante, neuroprotector)", "mejora memoria (aroma)", "antiinflamatorio"], "tags": ["hierba", "aromática", "cocina mediterránea", "memoria"]},
    normalize_text("tomillo"): {"original_name": "Tomillo", "category_key": "🌿 Hierbas y especias", "color": "verde", "pni_benefits": ["timol (antiséptico, antioxidante)", "expectorante", "antimicrobiano"], "tags": ["hierba", "aromática", "cocina mediterránea", "respiratorio"]},
    normalize_text("salvia"): {"original_name": "Salvia", "category_key": "🌿 Hierbas y especias", "color": "verde grisáceo", "pni_benefits": ["ácido rosmarínico", "tuyona (con moderación)", "mejora función cognitiva", "antiinflamatorio", "menopausia (alivio sofocos)"], "tags": ["hierba", "aromática", "memoria", "propiedades medicinales"]},
    normalize_text("cayena"): {"original_name": "Cayena (Pimienta de Cayena)", "category_key": "🌿 Hierbas y especias", "color": "rojo", "pni_benefits": ["capsaicina (antiinflamatorio, analgésico, termogénico)", "vitamina C", "antioxidantes"], "tags": ["especia", "picante", "metabolismo", "dolor"]},
    normalize_text("pimienta negra"): {"original_name": "Pimienta Negra", "category_key": "🌿 Hierbas y especias", "color": "negro", "pni_benefits": ["piperina (mejora absorción nutrientes, ej. curcumina)", "antioxidante", "antiinflamatorio"], "tags": ["especia", "digestiva", "potenciador de absorción"]},
    normalize_text("clavo"): {"original_name": "Clavo (de olor)", "category_key": "🌿 Hierbas y especias", "color": "marrón oscuro", "pni_benefits": ["eugenol (muy alto, potente antioxidante, analgésico, antiséptico)", "antiinflamatorio"], "tags": ["especia", "aromático", "analgésico dental", "antioxidante potente"]},
    normalize_text("nuez moscada"): {"original_name": "Nuez Moscada", "category_key": "🌿 Hierbas y especias", "color": "marrón", "pni_benefits": ["miristicina y elemicina (estimulantes en altas dosis, tóxicas)", "antiinflamatorio", "digestivo (con moderación)"], "tags": ["especia", "aromática", "usar con moderación", "postres/bechamel"]},
    normalize_text("comino"): {"original_name": "Comino", "category_key": "🌿 Hierbas y especias", "color": "marrón claro", "pni_benefits": ["cuminaldehído", "hierro", "digestivo", "carminativo"], "tags": ["especia", "aromático", "cocina india/mexicana/medio oriente", "digestivo"]},
    normalize_text("hinojo (semillas)"): {"original_name": "Hinojo (semillas)", "category_key": "🌿 Hierbas y especias", "color": "verde/marrón claro", "pni_benefits": ["anetol (digestivo, carminativo)", "fibra", "antiespasmódico"], "tags": ["especia", "digestiva", "sabor anisado", "infusiones"]},
    normalize_text("cardamomo"): {"original_name": "Cardamomo", "category_key": "🌿 Hierbas y especias", "color": "verde/negro (vainas)", "pni_benefits": ["cineol (expectorante)", "antioxidantes", "digestivo", "diurético suave"], "tags": ["especia", "aromático", "cocina india/escandinava", "caro"]},
    normalize_text("anis estrellado"): {"original_name": "Anís Estrellado", "category_key": "🌿 Hierbas y especias", "color": "marrón", "pni_benefits": ["anetol", "ácido shikímico (base para Tamiflu)", "antiviral", "digestivo"], "tags": ["especia", "aromático", "forma de estrella", "cocina asiática", "infusiones"]},
    normalize_text("azafran"): {"original_name": "Azafrán", "category_key": "🌿 Hierbas y especias", "color": "rojo (estigmas)", "pni_benefits": ["crocina y crocetina (antioxidantes, antidepresivo leve)", "safranal (aroma, antidepresivo leve)", "antiinflamatorio"], "tags": ["especia", "colorante", "aromático", "caro", "estado de ánimo"]},
    normalize_text("laurel"): {"original_name": "Laurel (hoja)", "category_key": "🌿 Hierbas y especias", "color": "verde", "pni_benefits": ["eugenol", "cineol", "digestivo", "antiinflamatorio"], "tags": ["hierba", "aromática", "cocina mediterránea", "guisos"]},

    # Alimentos de origen animal (ejemplos y algunos más para variedad)
    normalize_text("pollo"): {"original_name": "Pollo (preferiblemente de pasto/ecológico)", "category_key": "🥩 Carnes", "color": "blanco/amarillento", "pni_benefits": ["proteína magra de alta calidad", "vitamina B6", "niacina", "selenio"], "tags": ["ave", "versátil", "fuente de proteína"]},
    normalize_text("salmon"): {"original_name": "Salmón (preferiblemente salvaje)", "category_key": "🐟 Pescados (blancos y azules)", "color": "rosado/rojo", "pni_benefits": ["omega-3 (EPA/DHA)", "vitamina D", "proteína de alta calidad", "astaxantina (antioxidante)"], "tags": ["pescado azul", "antiinflamatorio", "salud cardiovascular", "cerebro"]},
    normalize_text("huevo"): {"original_name": "Huevo (preferiblemente de gallinas camperas/ecológicas)", "category_key": "🥚 Huevos y derivados", "color": "varios (cáscara), amarillo/naranja (yema)", "pni_benefits": ["proteína completa", "colina (salud cerebral)", "vitamina D", "luteína", "zeaxantina"], "tags": ["versátil", "rico en nutrientes", "desayuno"]},
    normalize_text("ternera de pasto"): {"original_name": "Ternera de Pasto", "category_key": "🥩 Carnes", "color": "rojo", "pni_benefits": ["proteína de alta calidad", "hierro hemo", "zinc", "vitamina B12", "mejor perfil omega-3/omega-6 que la convencional"], "tags": ["carne roja", "rica en hierro", "omega-3 (si de pasto)"]},
    normalize_text("cordero"): {"original_name": "Cordero (preferiblemente de pasto)", "category_key": "🥩 Carnes", "color": "rojo claro", "pni_benefits": ["proteína", "hierro hemo", "zinc", "vitamina B12", "ácido linoleico conjugado (CLA)"], "tags": ["carne roja", "sabor distintivo"]},
    normalize_text("sardina"): {"original_name": "Sardina", "category_key": "🐟 Pescados (blancos y azules)", "color": "plateado", "pni_benefits": ["omega-3 (EPA/DHA)", "calcio (si se come con espinas)", "vitamina D", "proteína"], "tags": ["pescado azul", "económico", "rico en calcio", "sostenible"]},
    normalize_text("caballa"): {"original_name": "Caballa (Verdel)", "category_key": "🐟 Pescados (blancos y azules)", "color": "plateado/azulado", "pni_benefits": ["omega-3 (EPA/DHA)", "vitamina D", "proteína", "selenio"], "tags": ["pescado azul", "sabor intenso", "antiinflamatorio"]},
    normalize_text("anchoa"): {"original_name": "Anchoa / Boquerón", "category_key": "🐟 Pescados (blancos y azules)", "color": "plateado", "pni_benefits": ["omega-3 (EPA/DHA)", "proteína", "calcio", "vitamina D"], "tags": ["pescado azul", "sabor intenso", "salud ósea"]},
    normalize_text("bacalao"): {"original_name": "Bacalao", "category_key": "🐟 Pescados (blancos y azules)", "color": "blanco", "pni_benefits": ["proteína magra", "vitamina B12", "selenio", "fósforo"], "tags": ["pescado blanco", "versátil", "bajo en grasa"]},
    normalize_text("merluza"): {"original_name": "Merluza", "category_key": "🐟 Pescados (blancos y azules)", "color": "blanco", "pni_benefits": ["proteína magra", "vitaminas B", "potasio", "fósforo"], "tags": ["pescado blanco", "sabor suave", "popular"]},
    normalize_text("higado de ternera"): {"original_name": "Hígado de Ternera (de pasto)", "category_key": "🧠 Vísceras y casquería", "color": "marrón rojizo", "pni_benefits": ["vitamina A (retinol, muy alta)", "hierro hemo (muy alta)", "vitamina B12", "cobre", "colina"], "tags": ["vísceras", "superalimento nutricional", "consumir con moderación por vitamina A"]},
    normalize_text("corazon de ternera"): {"original_name": "Corazón de Ternera (de pasto)", "category_key": "🧠 Vísceras y casquería", "color": "rojo oscuro", "pni_benefits": ["CoQ10", "proteína", "vitaminas B", "hierro", "selenio"], "tags": ["vísceras", "músculo", "salud cardiovascular", "CoQ10"]},
    normalize_text("mejillon"): {"original_name": "Mejillón", "category_key": "🦐 Mariscos y crustáceos", "color": "negro (concha), naranja/amarillo (carne)", "pni_benefits": ["hierro", "selenio", "vitamina B12", "omega-3", "glucosamina y condroitina (natural)"], "tags": ["marisco", "bivalvo", "rico en hierro", "sostenible"]},
    normalize_text("gamba"): {"original_name": "Gamba / Langostino", "category_key": "🦐 Mariscos y crustáceos", "color": "rosado/gris", "pni_benefits": ["proteína magra", "selenio", "astaxantina", "vitamina B12"], "tags": ["marisco", "crustáceo", "versátil"]}, # Colesterol dietético, pero bajo en grasa saturada.
    normalize_text("pulpo"): {"original_name": "Pulpo", "category_key": "🦐 Mariscos y crustáceos", "color": "marrón/morado (crudo), blanco/rosado (cocido)", "pni_benefits": ["proteína", "hierro", "vitamina B12", "taurina"], "tags": ["marisco", "cefalópodo", "inteligente", "textura firme"]},

    # Probióticos y fermentados (Existentes y Nuevos)
    normalize_text("yogur natural"): {"original_name": "Yogur Natural (sin azúcar, con cultivos vivos)", "category_key": "🦠 PROBIÓTICOS", "color": "blanco", "pni_benefits": ["probióticos (Lactobacillus, Bifidobacterium)", "calcio", "proteína", "vitamina B12"], "tags": ["fermentado", "lácteo", "salud intestinal"], "category_key_alt": "🧀 Lácteos"},
    normalize_text("kefir de leche"): {"original_name": "Kefir de Leche", "category_key": "🦠 PROBIÓTICOS", "color": "blanco", "pni_benefits": ["probióticos (mayor diversidad que yogur, incluye levaduras)", "calcio", "vitaminas B", "kefiran (polisacárido)"], "tags": ["fermentado", "lácteo", "potente probiótico", "salud intestinal"], "category_key_alt": "🧀 Lácteos"},
    normalize_text("chucrut"): {"original_name": "Chucrut (no pasteurizado)", "category_key": "🦠 PROBIÓTICOS", "color": "verde claro/blanco", "pni_benefits": ["probióticos (Lactobacillus spp.)", "vitamina C", "fibra", "glucosinolatos (del repollo)"], "tags": ["fermentado", "repollo", "no pasteurizado", "salud intestinal", "vitamina K2 (por bacterias)"]},
    normalize_text("kimchi"): {"original_name": "Kimchi (no pasteurizado)", "category_key": "🦠 PROBIÓTICOS", "color": "rojo/naranja", "pni_benefits": ["probióticos (Lactobacillus spp.)", "fibra", "capsaicina (del chile)", "ajo y jengibre (beneficios adicionales)"], "tags": ["fermentado", "picante", "coreano", "verduras variadas", "salud intestinal"]},
    normalize_text("miso"): {"original_name": "Miso (no pasteurizado)", "category_key": "🦠 PROBIÓTICOS", "color": "varios (blanco, amarillo, rojo, marrón)", "pni_benefits": ["probióticos (Aspergillus oryzae)", "isoflavonas (de soja)", "enzimas digestivas", "vitamina K"], "tags": ["fermentado", "soja (generalmente)", "japonés", "umami", "salud intestinal"]},
    normalize_text("tempeh"): {"original_name": "Tempeh", "category_key": "🦠 PROBIÓTICOS", "color": "blanco-marrón", "pni_benefits": ["probióticos (Rhizopus oligosporus)", "proteína vegetal completa", "fibra", "isoflavonas (biodisponibles)", "vitaminas B"], "tags": ["fermentado", "soja", "textura firme", "proteína vegetal", "salud intestinal"]},
    normalize_text("kombucha"): {"original_name": "Kombucha (bajo en azúcar)", "category_key": "🦠 PROBIÓTICOS", "color": "varios (según té e ingredientes)", "pni_benefits": ["probióticos (levaduras y bacterias - SCOBY)", "ácidos orgánicos (glucurónico, acético)", "antioxidantes (del té)"], "tags": ["fermentado", "té", "bajo en azúcar (elegir bien)", "bebida efervescente"]},
    normalize_text("kefir de agua"): {"original_name": "Kefir de Agua", "category_key": "🦠 PROBIÓTICOS", "color": "translúcido/varía", "pni_benefits": ["probióticos (diversas bacterias y levaduras)", "hidratante", "bajo en calorías"], "tags": ["fermentado", "sin lácteos", "bebida efervescente", "salud intestinal"]},
    normalize_text("vinagre de manzana sin pasteurizar"): {"original_name": "Vinagre de Manzana (con madre, sin pasteurizar)", "category_key": "🦠 PROBIÓTICOS", "color": "ámbar turbio", "pni_benefits": ["ácido acético", "contiene 'madre' (bacterias y levaduras)", "mejora sensibilidad a la insulina (potencial)", "digestivo"], "tags": ["fermentado", "condimento", "salud metabólica (potencial)", "no pasteurizado"]},
    normalize_text("encurtidos lactofermentados"): {"original_name": "Encurtidos Lactofermentados (no pasteurizados)", "category_key": "🦠 PROBIÓTICOS", "color": "varios (según vegetal)", "pni_benefits": ["probióticos (Lactobacillus spp.)", "fibra", "vitaminas (del vegetal)"], "tags": ["fermentado", "verduras", "salud intestinal", "no pasteurizado", "ej: pepinillos, zanahorias"]},

    # PREBIÓTICOS (algunos ya están, otros específicos para destacar)
    normalize_text("raiz de achicoria"): {"original_name": "Raíz de Achicoria", "category_key": "🌿 PREBIÓTICOS", "color": "marrón", "pni_benefits": ["inulina (alto contenido)", "fibra prebiótica potente", "salud intestinal"], "tags": ["prebiótico concentrado", "sustituto de café (tostada)"]},
    # El ajo, cebolla, puerro, espárrago, plátano (verde), alcachofa, diente de león (raíz), avena, manzana ya están listados y son prebióticos
    normalize_text("cebada"): {"original_name": "Cebada", "category_key": "🌾 Cereales y pseudocereales", "color": "beige", "pni_benefits": ["betaglucanos (fibra soluble, prebiótico)", "selenio", "magnesio"], "tags": ["cereal con gluten", "prebiótico", "salud cardiovascular"]}, # También es prebiótico
    normalize_text("platano macho verde"): {"original_name": "Plátano Macho Verde", "category_key": "🍎 Frutas", "color": "verde", "pni_benefits": ["almidón resistente (prebiótico)", "fibra", "potasio", "vitamina B6"], "tags": ["prebiótico", "cocinar antes de comer", "salud intestinal"]}, # Culinariamente verdura/fécula


    # Lácteos (Ejemplos, si no son probióticos)
    normalize_text("queso curado"): {"original_name": "Queso Curado (de buena calidad, ej. manchego, parmesano)", "category_key": "🧀 Lácteos", "color": "amarillo/blanco", "pni_benefits": ["calcio", "proteína", "vitamina K2 (en algunos)", "grasas (variable)"], "tags": ["lácteo", "fermentado (proceso, no siempre probiótico vivo)", "calcio", "sabor intenso"]},
    normalize_text("queso fresco"): {"original_name": "Queso Fresco (ej. cottage, ricotta, burgos)", "category_key": "🧀 Lácteos", "color": "blanco", "pni_benefits": ["proteína (caseína)", "calcio", "fósforo"], "tags": ["lácteo", "suave", "bajo en grasa (algunos)"]},
    normalize_text("mantequilla ghee"): {"original_name": "Mantequilla Ghee (clarificada)", "category_key": "🧀 Lácteos", "color": "amarillo dorado", "pni_benefits": ["ácido butírico (en pequeñas cantidades)", "vitaminas liposolubles (A, E, K)", "sin lactosa ni caseína (prácticamente)"], "tags": ["grasa láctea", "cocina india", "alto punto de humeo", "apto para algunos intolerantes"]},
    normalize_text("leche de cabra"): {"original_name": "Leche de Cabra", "category_key": "🧀 Lácteos", "color": "blanco", "pni_benefits": ["calcio", "proteína", "más fácil de digerir para algunos que la de vaca", "ácidos grasos de cadena media"], "tags": ["lácteo", "alternativa a leche de vaca"]},
    normalize_text("leche de oveja"): {"original_name": "Leche de Oveja", "category_key": "🧀 Lácteos", "color": "blanco", "pni_benefits": ["calcio (muy alto)", "proteína (muy alta)", "vitaminas B", "ácido fólico"], "tags": ["lácteo", "rica y cremosa", "para quesos (ej. Roquefort, Manchego)"]},

    # Otros / Miscelánea (Ejemplos)
    normalize_text("aceite de oliva virgen extra"): {"original_name": "Aceite de Oliva Virgen Extra", "category_key": "🫒 Aceites y grasas saludables", "color": "verde/dorado", "pni_benefits": ["ácido oleico (grasa monoinsaturada)", "polifenoles (oleocantal, hidroxitirosol - antiinflamatorios)", "vitamina E"], "tags": ["grasa saludable", "antiinflamatorio", "antioxidante", "dieta mediterránea"]},
    normalize_text("aceite de coco virgen"): {"original_name": "Aceite de Coco Virgen", "category_key": "🫒 Aceites y grasas saludables", "color": "blanco (sólido)/transparente (líquido)", "pni_benefits": ["ácidos grasos de cadena media (AGCM/MCTs)", "ácido láurico (antimicrobiano)", "energía rápida"], "tags": ["grasa saludable", "MCT", "controvertido (grasa saturada)", "uso culinario y cosmético"]},
    normalize_text("aceite de lino"): {"original_name": "Aceite de Lino", "category_key": "🫒 Aceites y grasas saludables", "color": "amarillo dorado", "pni_benefits": ["omega-3 (ALA, muy alto)", "antiinflamatorio"], "tags": ["grasa saludable", "omega-3 vegetal", "no calentar", "sensible a la oxidación"]},
    normalize_text("aceituna"): {"original_name": "Aceituna", "category_key": "🫒 Aceites y grasas saludables", "color": "verde/negro/morado", "pni_benefits": ["grasas monoinsaturadas (ácido oleico)", "vitamina E", "polifenoles", "fibra"], "tags": ["fruto del olivo", "aperitivo", "grasa saludable", "fermentadas (algunas)"]},
    normalize_text("cacao puro en polvo"): {"original_name": "Cacao Puro en Polvo (desgrasado, sin azúcar)", "category_key": "🍫 Chocolate y cacao", "color": "marrón oscuro", "pni_benefits": ["flavonoides (epicatequina - antioxidante, salud cardiovascular)", "magnesio", "hierro", "teobromina (estimulante suave)"], "tags": ["superfood", "antioxidante", "estado de ánimo", "amargo"]},
    normalize_text("chocolate negro"): {"original_name": "Chocolate Negro (>70% cacao, bajo en azúcar)", "category_key": "🍫 Chocolate y cacao", "color": "marrón oscuro", "pni_benefits": ["flavonoides del cacao", "magnesio", "antioxidantes", "mejora flujo sanguíneo"], "tags": ["placer saludable", "antioxidante", "moderación", "elegir alto porcentaje cacao"]},
    normalize_text("caldo de huesos"): {"original_name": "Caldo de Huesos", "category_key": "🍲 Sopas y caldos", "color": "variable (dorado a marrón)", "pni_benefits": ["colágeno/gelatina", "aminoácidos (glicina, prolina)", "minerales", "salud intestinal"], "tags": ["nutritivo", "salud articular", "salud intestinal", "cocción lenta"]},
    normalize_text("te verde"): {"original_name": "Té Verde", "category_key": "🍵 Bebidas saludables", "color": "verde/amarillo claro", "pni_benefits": ["EGCG (galato de epigalocatequina - potente antioxidante)", "L-teanina (calmante, concentración)", "catequinas"], "tags": ["antioxidante", "salud cerebral", "metabolismo", "matcha (forma concentrada)"]},
    normalize_text("matcha"): {"original_name": "Matcha", "category_key": "🍵 Bebidas saludables", "color": "verde intenso", "pni_benefits": ["EGCG (muy alto)", "L-teanina (muy alta)", "clorofila", "antioxidantes"], "tags": ["té verde en polvo", "concentrado", "energía calmada", "antioxidante potente"]},
    normalize_text("te blanco"): {"original_name": "Té Blanco", "category_key": "🍵 Bebidas saludables", "color": "amarillo pálido", "pni_benefits": ["antioxidantes (similar al té verde, pero perfil diferente)", "menos procesado", "catequinas"], "tags": ["delicado", "antioxidante", "bajo en cafeína (generalmente)"]},
    normalize_text("rooibos"): {"original_name": "Rooibos (Té rojo sudafricano)", "category_key": "🍵 Bebidas saludables", "color": "rojo/marrón", "pni_benefits": ["aspalatina y notofagina (antioxidantes)", "sin cafeína", "minerales (pequeñas cantidades)"], "tags": ["infusión", "sin cafeína", "antioxidante", "sabor dulce"]},
    normalize_text("infusion de jengibre"): {"original_name": "Infusión de Jengibre", "category_key": "🍵 Bebidas saludables", "color": "amarillo pálido", "pni_benefits": ["gingerol", "antinauseas", "antiinflamatorio", "digestivo"], "tags": ["infusión", "sin cafeína", "medicinal", "calentadora"]},
    normalize_text("infusion de manzanilla"): {"original_name": "Infusión de Manzanilla", "category_key": "🍵 Bebidas saludables", "color": "amarillo claro", "pni_benefits": ["apigenina (calmante, ansiolítico suave)", "antiinflamatorio", "digestivo"], "tags": ["infusión", "sin cafeína", "calmante", "digestiva", "sueño"]},
    normalize_text("agua de coco"): {"original_name": "Agua de Coco (natural, sin azúcar añadido)", "category_key": "🍵 Bebidas saludables", "color": "translúcido", "pni_benefits": ["electrolitos (potasio, magnesio)", "hidratante", "bajo en calorías"], "tags": ["hidratación", "natural", "refrescante", "post-ejercicio"]},
    normalize_text("alga nori"): {"original_name": "Alga Nori", "category_key": "🌊 Algas", "color": "verde oscuro/negro", "pni_benefits": ["yodo", "fibra", "vitaminas (B12 en algunas formas, pero biodisponibilidad discutida)", "proteína"], "tags": ["alga marina", "sushi", "snacks", "rica en yodo"]},
    normalize_text("alga kombu"): {"original_name": "Alga Kombu", "category_key": "🌊 Algas", "color": "verde oscuro/negro", "pni_benefits": ["yodo (muy alta)", "ácido glutámico (umami)", "fucoidano (anticoagulante, antiviral)", "minerales"], "tags": ["alga marina", "caldos (dashi)", "ablandar legumbres", "rica en yodo (usar con precaución)"]},
    normalize_text("alga wakame"): {"original_name": "Alga Wakame", "category_key": "🌊 Algas", "color": "verde oscuro", "pni_benefits": ["yodo", "fucoxantina (quema grasa potencial)", "calcio", "magnesio"], "tags": ["alga marina", "sopa de miso", "ensaladas", "rica en nutrientes"]},
    normalize_text("alga espirulina"): {"original_name": "Alga Espirulina", "category_key": "🌊 Algas", "color": "verde azulado oscuro", "pni_benefits": ["proteína completa (alta)", "hierro", "ficocianina (antioxidante, antiinflamatorio)", "vitaminas B"], "tags": ["microalga", "superfood", "proteína vegetal", "detox (potencial)", "suplemento"]},
    normalize_text("alga chlorella"): {"original_name": "Alga Chlorella", "category_key": "🌊 Algas", "color": "verde oscuro", "pni_benefits": ["clorofila (muy alta)", "proteína", "factor de crecimiento de Chlorella (CGF)", "detox metales pesados (potencial)"], "tags": ["microalga", "superfood", "detox", "pared celular dura (requiere procesado)", "suplemento"]},
    normalize_text("levadura nutricional"): {"original_name": "Levadura Nutricional", "category_key": "🌿 Hierbas y especias", "color": "amarillo (escamas/polvo)", "pni_benefits": ["vitaminas B (a menudo fortificada con B12)", "proteína completa (inactiva)", "betaglucanos"], "tags": ["condimento", "sabor a queso (umami)", "vegana", "rica en B12 (si fortificada)"]},


}

# Ejemplo: Añadir el yogur a la categoría Lácteos también si se desea listarlo allí
# (Ya se hizo arriba con "category_key_alt" para yogur y kefir de leche)

# Nuevas categorías sugeridas por los añadidos
# 🫒 Aceites y grasas saludables
# 🍫 Chocolate y cacao
# 🍲 Sopas y caldos
# 🍵 Bebidas saludables
# 🌊 Algas

# Se puede añadir `category_key_alt` a más alimentos si es necesario.
# Por ejemplo, el ajo también podría estar en "Hierbas y especias"
if normalize_text("ajo") in food_details_db:
    food_details_db[normalize_text("ajo")]["category_key_alt"] = "🌿 Hierbas y especias"
if normalize_text("jengibre") in food_details_db:
    food_details_db[normalize_text("jengibre")]["category_key_alt"] = "🥦 Verduras y hortalizas" # Ya está como verdura, pero es raíz especia
if normalize_text("tomate") in food_details_db: # Botánicamente fruta, culinariamente verdura
    food_details_db[normalize_text("tomate")]["category_key_alt"] = "🍎 Frutas"
if normalize_text("aguacate") in food_details_db: # Botánicamente fruta
    food_details_db[normalize_text("aguacate")]["category_key_alt"] = "🫒 Aceites y grasas saludables" # Por su contenido graso
if normalize_text("aceituna") in food_details_db: # Fruto, pero fuente de grasa
    food_details_db[normalize_text("aceituna")]["category_key_alt"] = "🍎 Frutas"
if normalize_text("guisante") in food_details_db: # Leguminosa verde, culinariamente verdura
    food_details_db[normalize_text("guisante")]["category_key_alt"] = "🫘 Legumbres"
if normalize_text("judia verde") in food_details_db: # Leguminosa verde, culinariamente verdura
    food_details_db[normalize_text("judia verde")]["category_key_alt"] = "🫘 Legumbres"
if normalize_text("habas") in food_details_db: # Leguminosa verde, culinariamente verdura
    food_details_db[normalize_text("habas")]["category_key_alt"] = "🫘 Legumbres"
if normalize_text("edamame") in food_details_db: # Soja, legumbre, pero a veces como verdura
    food_details_db[normalize_text("edamame")]["category_key_alt"] = "🥦 Verduras y hortalizas"


print(f"Total de alimentos en la base de datos: {len(food_details_db)}")
# Para verificar alguna entrada específica:
# print(food_details_db[normalize_text("col rizada")])
# print(food_details_db[normalize_text("salmon")])
# print(food_details_db[normalize_text("aceite de oliva virgen extra")])


# Derivar listas necesarias a partir de food_details_db
all_selectable_food_items_original_case = sorted(list(set([ # Usar set para evitar duplicados si un alimento está en múltiples categorías (poco probable con este setup)
    data["original_name"] for data in food_details_db.values()
])))

plant_food_items_original_case = set() # Nombres originales de alimentos vegetales
normalized_plant_food_items = set()    # Nombres normalizados de alimentos vegetales
normalized_to_original_food_map = {}   # Mapeo general de normalizado a original

for norm_name, data in food_details_db.items():
    normalized_to_original_food_map[norm_name] = data["original_name"]
    if data.get("category_key") in PLANT_CATEGORIES_KEYS:
        plant_food_items_original_case.add(data["original_name"])
        normalized_plant_food_items.add(norm_name)

# Definir también listas para probióticos y prebióticos si se usan para sugerencias específicas
probiotic_foods_original_case = set()
normalized_probiotic_foods = set()
prebiotic_foods_original_case = set() # Podrías también definir alimentos específicamente como prebióticos aquí
normalized_prebiotic_foods = set()

for norm_name, data in food_details_db.items():
    if data.get("category_key") == "🦠 PROBIÓTICOS":
        probiotic_foods_original_case.add(data["original_name"])
        normalized_probiotic_foods.add(norm_name)
    if data.get("category_key") == "🌿 PREBIÓTICOS" or "prebiótico" in " ".join(data.get("pni_benefits", [])).lower() or "prebiótico" in " ".join(data.get("tags", [])).lower():
        # Considerar un alimento como prebiótico si está en la categoría, o tiene "prebiótico" en beneficios o tags
        prebiotic_foods_original_case.add(data["original_name"])
        normalized_prebiotic_foods.add(norm_name)
        # Añadir explícitamente algunos que son excelentes prebióticos desde sus categorías principales:
        if norm_name in [normalize_text("ajo"), normalize_text("cebolla"), normalize_text("puerro"), normalize_text("alcachofa"), normalize_text("espárrago"), normalize_text("plátano"), normalize_text("avena")]:
             normalized_prebiotic_foods.add(norm_name)
             prebiotic_foods_original_case.add(data["original_name"])


food_synonyms_map = {
    normalize_text("jitomate"): normalize_text("tomate"),
    normalize_text("aguacate hass"): normalize_text("aguacate"),
    normalize_text("palta"): normalize_text("aguacate"),
    normalize_text("plátano canario"): normalize_text("plátano"),
    normalize_text("banana"): normalize_text("plátano"),
    normalize_text("brocoli"): normalize_text("brócoli"),
    normalize_text("broccoli"): normalize_text("brócoli"),
    normalize_text("col china"): normalize_text("pak choi"), # Ejemplo si tuvieras pak choi
    normalize_text("esparrago"): normalize_text("espárrago"),
    normalize_text("esparragos"): normalize_text("espárrago"),
    normalize_text("champinon"): normalize_text("champiñón"),
    normalize_text("champinones"): normalize_text("champiñón"),
    normalize_text("semillas de chia"): normalize_text("semilla de chía"),
    normalize_text("semillas de lino"): normalize_text("semilla de lino"),
    normalize_text("linaza"): normalize_text("semilla de lino"),
    normalize_text("pipas de calabaza"): normalize_text("pipa de calabaza"),
    normalize_text("alubia negra"): normalize_text("judía negra"),
    normalize_text("frijol negro"): normalize_text("judía negra"),
    normalize_text("buckwheat"): normalize_text("trigo sarraceno"),
    normalize_text("alforfon"): normalize_text("trigo sarraceno"),
    normalize_text("curcuma"): normalize_text("cúrcuma"),
    normalize_text("turmeric"): normalize_text("cúrcuma"),
    normalize_text("jengibre fresco"): normalize_text("jengibre"),
    normalize_text("ginger"): normalize_text("jengibre"),
    normalize_text("yogurt natural"): normalize_text("yogur natural"),
    normalize_text("sauerkraut"): normalize_text("chucrut"),
}

# NUEVO: Función para obtener el nombre canónico (normalizado) y el original
def get_canonical_food_info(input_name):
    """
    Toma un nombre de alimento, lo normaliza, busca sinónimos y devuelve
    el nombre normalizado canónico y el nombre original canónico.
    Returns: Tuple (canonical_normalized_name, canonical_original_name) or (None, None)
    """
    if not input_name:
        return None, None
    
    normalized_input = normalize_text(input_name)

    # 1. Buscar en sinónimos primero
    canonical_norm_name = food_synonyms_map.get(normalized_input)

    # 2. Si no está en sinónimos, el input normalizado podría ser ya canónico
    if not canonical_norm_name:
        if normalized_input in food_details_db:
            canonical_norm_name = normalized_input
        else: # No se encontró directamente ni como sinónimo
            # Podríamos añadir lógica de búsqueda parcial aquí si quisiéramos ser más permisivos
            # Por ahora, si no es un hit directo o sinónimo, no lo reconocemos.
            return None, None

    # 3. Obtener el nombre original del canónico normalizado
    if canonical_norm_name in food_details_db:
        original_name = food_details_db[canonical_norm_name]["original_name"]
        return canonical_norm_name, original_name
    
    return None, None # No debería llegar aquí si la lógica es correcta y food_details_db está completo

# --- Fin de Base de Datos Detallada de Alimentos ---

# --- Credenciales de Google Cloud (sin cambios) ---
# ... (tu código de credenciales existente) ...

# --- Conectar a Google Sheets ---
@st.cache_resource(ttl=600)
def get_sheet(creds_param): # Modificado para pasar creds
    if not google_services_available or creds_param is None: # Usar creds_param
        st.warning("Los servicios de Google no están disponibles. No se puede acceder a la hoja de cálculo.")
        return None
    try:
        client_gspread = gspread.authorize(creds_param) # Usar creds_param
        # Intenta abrir por nombre. Si falla, puedes pedir al usuario el ID o URL en el futuro.
        # Por ahora, asumimos que "habitos_microbiota" existe y está compartida con la cuenta de servicio.
        return client_gspread.open("habitos_microbiota").sheet1
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Hoja de cálculo 'habitos_microbiota' no encontrada. "
                 f"Asegúrate de que existe y está compartida con el email de la cuenta de servicio: "
                 f"{creds_info_dict.get('client_email', 'EMAIL_NO_ENCONTRADO_EN_CREDENCIALES') if creds_info_dict else 'CREDENCIALES_NO_CARGADAS'}")
        return None
    except Exception as e:
        st.error(f"No se pudo conectar a Google Sheets: {e}")
        return None

EXPECTED_HEADERS = ["usuario", "fecha", "comida_original", "comida_normalizada_canonica", "sueno", "ejercicio", "animo", "diversidad_diaria_plantas", "tipo_registro"]

def check_and_create_headers(sheet):
    if sheet is None: return
    try:
        headers = sheet.row_values(1)
        if not headers: # Hoja completamente vacía
            sheet.append_row(EXPECTED_HEADERS)
            st.info(f"Encabezados creados en la hoja: {', '.join(EXPECTED_HEADERS)}")
        elif headers != EXPECTED_HEADERS:
            st.warning(f"Los encabezados de la hoja de Google Sheets ({headers}) no coinciden con los esperados ({EXPECTED_HEADERS}). "
                       "Esto podría causar errores. Considera ajustar la hoja o empezar con una nueva.")
    except gspread.exceptions.APIError as e:
        if 'exceeds grid limits' in str(e).lower() or 'exceeded a limit' in str(e).lower(): # Hoja vacía o casi
            try:
                if not sheet.get_all_values(): # Doble check si está realmente vacía
                     sheet.append_row(EXPECTED_HEADERS)
                     st.info(f"Encabezados creados en la hoja (tras APIError): {', '.join(EXPECTED_HEADERS)}")
            except Exception as inner_e:
                 st.error(f"Error al intentar añadir encabezados tras APIError: {inner_e}")
        else:
            st.error(f"Error de API con Google Sheets al verificar encabezados: {e}")
    except Exception as e:
        st.error(f"Error al verificar/crear encabezados en Google Sheets: {e}")


# --- Detección de vegetales con Google Vision AI ---
def detectar_alimentos_google_vision(image_file_content): # Renombrado a detectar_alimentos
    if vision_client is None:
        st.warning("El cliente de Google Vision no está inicializado. No se pueden detectar alimentos.")
        return [] # Devuelve lista de nombres originales canónicos

    image = vision.Image(content=image_file_content)
    try:
        response = vision_client.label_detection(image=image)
        labels = response.label_annotations
    except Exception as e:
        st.error(f"Excepción al llamar a Google Vision API: {e}")
        if hasattr(e, 'details'):
            st.error(f"Detalles del error de API: {e.details()}")
        return []

    if response.error.message:
        st.error(f"Error devuelto por Google Vision API: {response.error.message}")
        return []

    if not labels:
        st.info("Google Vision API no devolvió ninguna etiqueta para esta imagen.")
        return []

    # Mapeos específicos de Vision API a tus nombres normalizados canónicos
    # Esto puede crecer con el tiempo basado en lo que Vision devuelve.
    api_label_to_my_food_map = {
        normalize_text("summer squash"): normalize_text("calabacín"),
        normalize_text("zucchini"): normalize_text("calabacín"),
        normalize_text("courgette"): normalize_text("calabacín"),
        normalize_text("cucumber"): normalize_text("pepino"),
        normalize_text("bell pepper"): normalize_text("pimiento rojo"), # Asume rojo si no especifica color
        normalize_text("capsicum"): normalize_text("pimiento rojo"),
        normalize_text("potato"): normalize_text("patata"), # Si tienes "patata" en tu DB
        normalize_text("tomato"): normalize_text("tomate"),
        normalize_text("apple"): normalize_text("manzana"),
        normalize_text("banana"): normalize_text("plátano"),
        normalize_text("orange"): normalize_text("naranja"), # Fruta
        normalize_text("strawberry"): normalize_text("fresa"),
        normalize_text("blueberry"): normalize_text("arándano"),
        normalize_text("broccoli"): normalize_text("brócoli"),
        normalize_text("spinach"): normalize_text("espinaca"),
        normalize_text("carrot"): normalize_text("zanahoria"),
        normalize_text("almond"): normalize_text("almendra"),
        normalize_text("walnut"): normalize_text("nuez"),
        normalize_text("lentil"): normalize_text("lenteja"),
        normalize_text("chickpea"): normalize_text("garbanzo"),
        normalize_text("oat"): normalize_text("avena"), # Para "oatmeal" o "oats"
        normalize_text("quinoa"): normalize_text("quinoa"),
        normalize_text("mushroom"): normalize_text("champiñón"), # Genérico
        # ... más mapeos
    }

    posibles_alimentos_detectados_original_case = set()

    for label in labels:
        nombre_label_norm_api = normalize_text(label.description)

        # Estrategia 1: Mapeo directo de API
        target_norm_name = api_label_to_my_food_map.get(nombre_label_norm_api)
        
        if target_norm_name:
            # Asegurar que este nombre mapeado existe en nuestra DB
            if target_norm_name in food_details_db:
                original_name = food_details_db[target_norm_name]["original_name"]
                posibles_alimentos_detectados_original_case.add(original_name)
                # st.write(f"Debug Vision: Mapeo API directo: '{label.description}' -> '{original_name}'")
                continue # Siguiente label

        # Estrategia 2: Usar get_canonical_food_info con la etiqueta de la API
        # Esto intentará normalizar, buscar sinónimos de la etiqueta y luego mapear.
        # Es útil si la API devuelve "brocoli" y tu sinónimo lo mapea a "brócoli".
        norm_canonical, original_canonical = get_canonical_food_info(label.description)
        if norm_canonical and original_canonical:
            # Solo añadir si es una planta reconocida por nuestra DB
            if norm_canonical in normalized_plant_food_items: # Filtramos para que solo sugiera plantas
                posibles_alimentos_detectados_original_case.add(original_canonical)
                # st.write(f"Debug Vision: Mapeo canonico: '{label.description}' -> '{original_canonical}'")
                continue

        # Estrategia 3: (Menos precisa) Ver si alguna de nuestras plantas está contenida en la etiqueta
        # (ej. etiqueta "red apple", nuestra planta "apple")
        # Es mejor si las etiquetas de la API son más específicas.
        # for my_plant_norm_key in normalized_plant_food_items:
        #     if my_plant_norm_key in nombre_label_norm_api:
        #         original_name = food_details_db[my_plant_norm_key]["original_name"]
        #         posibles_alimentos_detectados_original_case.add(original_name)
        #         # st.write(f"Debug Vision: Mapeo substring: '{my_plant_norm_key}' in '{label.description}' -> '{original_name}'")


    if labels and not posibles_alimentos_detectados_original_case:
        raw_api_labels_for_warning = [l.description for l in labels[:5]]
        st.warning(
            f"La API de Vision devolvió etiquetas (ej: {', '.join(raw_api_labels_for_warning)}), "
            "pero ninguna coincidió con tu lista interna de plantas tras la normalización y el mapeo. "
            "Intenta añadir los alimentos manualmente o refinar los mapeos en `api_label_to_my_food_map`."
        )
    
    # Devolver solo los que son plantas
    plantas_detectadas_final = [
        food_name for food_name in sorted(list(posibles_alimentos_detectados_original_case))
        if normalize_text(food_name) in normalized_plant_food_items
    ]
    return plantas_detectadas_final


# --- Guardar registro diario ---
def guardar_registro(sheet, user_id, fecha, seleccionados_original_case, sueno, ejercicio, animo):
    if sheet is None:
        st.error("No se puede guardar el registro, la hoja de cálculo no está disponible.")
        return

    fecha_str = fecha.strftime('%Y-%m-%d')
    plantas_dia_normalizadas_canonicas = set()
    todos_alimentos_dia_normalizados_canonicos = set() # Para guardar todos los alimentos normalizados
    
    nombres_originales_para_guardar = [] # Para la columna "comida_original"

    for item_original_seleccionado in seleccionados_original_case:
        norm_canonical, original_canonical = get_canonical_food_info(item_original_seleccionado)
        if norm_canonical and original_canonical:
            nombres_originales_para_guardar.append(original_canonical) # Guardar el nombre canónico original
            todos_alimentos_dia_normalizados_canonicos.add(norm_canonical)
            if norm_canonical in normalized_plant_food_items: # Contar para diversidad solo si es planta
                plantas_dia_normalizadas_canonicas.add(norm_canonical)
        else:
            # Si no se puede obtener el canónico, guardar el original tal cual (y quizás loguear)
            nombres_originales_para_guardar.append(item_original_seleccionado)
            st.warning(f"Alimento '{item_original_seleccionado}' no encontrado en la base de datos, se guardará tal cual pero podría no contar para la diversidad si no es reconocido.")

    diversidad_diaria_plantas = len(plantas_dia_normalizadas_canonicas)
    
    comida_original_str = ", ".join(sorted(list(set(nombres_originales_para_guardar)))) # Nombres originales canónicos
    comida_normalizada_str = ", ".join(sorted(list(todos_alimentos_dia_normalizados_canonicos))) # Nombres normalizados canónicos

    try:
        sheet.append_row([
            user_id, fecha_str, comida_original_str, comida_normalizada_str,
            sueno, ejercicio, animo, diversidad_diaria_plantas, "registro_diario" # tipo_registro
        ])
        st.success(f"✅ Registro para {user_id} guardado: {diversidad_diaria_plantas} plantas distintas hoy.")
    except Exception as e:
        st.error(f"Error al guardar el registro en Google Sheets: {e}")


# --- Guardar resumen semanal ---
def calcular_y_guardar_resumen_semanal_usuario(sheet, user_id, fecha_referencia_lunes):
    if sheet is None: return
    
    st.write(f"Calculando resumen semanal para {user_id} para la semana que termina el domingo antes de {fecha_referencia_lunes.strftime('%Y-%m-%d')}")

    all_records_list_of_dict = []
    try:
        # Usar get_all_records si los encabezados son fiables
        # Si da problemas, cambiar a get_all_values y parsear manualmente
        all_records_list_of_dict = sheet.get_all_records(expected_headers=EXPECTED_HEADERS)
    except Exception as e:
        st.error(f"No se pudieron obtener todos los registros para el resumen semanal: {e}")
        st.info("Asegúrate que los encabezados de la hoja coinciden con: " + ", ".join(EXPECTED_HEADERS))
        return

    if not all_records_list_of_dict:
        st.warning("La hoja está vacía, no se puede generar resumen semanal.")
        return

    df = pd.DataFrame(all_records_list_of_dict)

    if "usuario" not in df.columns:
        st.error("La columna 'usuario' no se encuentra en la hoja. No se puede generar resumen.")
        return
        
    df_user = df[df["usuario"] == user_id].copy()

    if df_user.empty:
        st.info(f"No hay registros para el usuario {user_id} para generar resumen semanal.")
        return

    try:
        df_user["fecha"] = pd.to_datetime(df_user["fecha"], errors='coerce').dt.date
        df_user.dropna(subset=["fecha"], inplace=True)
    except Exception as e:
        st.error(f"Error convirtiendo fechas para el resumen: {e}")
        return
            
    fin_semana_a_resumir = fecha_referencia_lunes - timedelta(days=1) 
    inicio_semana_a_resumir = fin_semana_a_resumir - timedelta(days=6)

    # Filtrar registros de la semana a resumir que sean de tipo "registro_diario"
    # y usar la columna 'comida_normalizada_canonica'
    semana_df = df_user[
        (df_user["fecha"] >= inicio_semana_a_resumir) &
        (df_user["fecha"] <= fin_semana_a_resumir) &
        (df_user["tipo_registro"] == "registro_diario") # Usar el nuevo nombre de columna
    ].copy()

    diversidad_semanal_plantas = 0
    if semana_df.empty:
        st.info(f"No hay registros diarios para {user_id} en la semana del {inicio_semana_a_resumir.strftime('%Y-%m-%d')} al {fin_semana_a_resumir.strftime('%Y-%m-%d')}.")
    else:
        plantas_semana_normalizadas_canonicas = set()
        for _, row in semana_df.iterrows():
            # Usar la columna de nombres normalizados canónicos para el cálculo
            comida_registrada_norm = str(row.get("comida_normalizada_canonica", "")).split(",")
            for item_norm_canonico in comida_registrada_norm:
                item_norm_canonico_trimmed = item_norm_canonico.strip()
                if not item_norm_canonico_trimmed: continue
                
                # Solo contamos si el item normalizado canónico es una planta reconocida
                if item_norm_canonico_trimmed in normalized_plant_food_items:
                    plantas_semana_normalizadas_canonicas.add(item_norm_canonico_trimmed)
        diversidad_semanal_plantas = len(plantas_semana_normalizadas_canonicas)

    fecha_resumen_str = fecha_referencia_lunes.strftime('%Y-%m-%d')
    
    resumen_existente = df_user[
        (df_user["fecha"] == fecha_referencia_lunes) &
        (df_user["tipo_registro"] == "resumen_semanal") # Nuevo tipo de registro
    ]

    if resumen_existente.empty:
        try:
            sheet.append_row([
                user_id, fecha_resumen_str, 
                f"Resumen de la semana {inicio_semana_a_resumir.strftime('%Y-%m-%d')} - {fin_semana_a_resumir.strftime('%Y-%m-%d')}", # comida_original
                "", # comida_normalizada_canonica (vacío para resumen)
                "", "", "", # sueño, ejercicio, animo (vacíos para resumen)
                diversidad_semanal_plantas, # diversidad_diaria_plantas (aquí es la semanal)
                "resumen_semanal" # tipo_registro
            ])
            st.success(f"📝 Resumen semanal para {user_id} guardado: {diversidad_semanal_plantas} plantas.")
        except Exception as e:
            st.error(f"Error al guardar el resumen semanal en Google Sheets: {e}")
    else:
        st.info(f"Ya existe un resumen para {user_id} en la fecha {fecha_resumen_str}.")


# --- NUEVO: Sugerencias Inteligentes (Punto 2) ---
def get_smart_suggestions(plantas_consumidas_norm_canonicas_set, num_sugerencias=5):
    """
    Genera sugerencias de plantas no consumidas, intentando variar.
    - plantas_consumidas_norm_canonicas_set: set de nombres normalizados canónicos de plantas ya consumidas.
    - num_sugerencias: cuántas sugerencias devolver.
    """
    if not food_details_db or not normalized_plant_food_items:
        return ["Error: Base de datos de alimentos no cargada."]

    plantas_disponibles_norm = normalized_plant_food_items - plantas_consumidas_norm_canonicas_set
    
    if not plantas_disponibles_norm:
        return [] # No hay nada que sugerir

    sugerencias = []
    # Convertir a lista para poder barajar y seleccionar
    plantas_disponibles_lista_norm = list(plantas_disponibles_norm)
    random.shuffle(plantas_disponibles_lista_norm)

    # Lógica simple: tomar las primeras N de la lista barajada.
    # Lógica avanzada (futuro):
    # 1. Intentar obtener de categorías no consumidas recientemente.
    # 2. Intentar obtener de colores no consumidos recientemente.
    # 3. Priorizar alimentos con ciertos PNI benefits.
    
    for norm_name in plantas_disponibles_lista_norm:
        if len(sugerencias) < num_sugerencias:
            original_name = food_details_db[norm_name]["original_name"]
            sugerencias.append(original_name)
        else:
            break
            
    return sugerencias

# --- Visualización y análisis (MODIFICADO para usar nuevas estructuras y sugerencias) ---
def mostrar_registros_y_analisis(df_user, current_user_id):
    if df_user.empty:
        st.info(f"Aún no hay registros para el usuario {current_user_id}.")
        return

    df_display = df_user[df_user['tipo_registro'] == 'registro_diario'].copy() # Filtrar por tipo_registro
    if df_display.empty:
        st.info(f"Aún no hay registros de tipo 'registro_diario' para el usuario {current_user_id} para mostrar detalles.")
        return
        
    df_display["fecha"] = pd.to_datetime(df_display["fecha"]).dt.date
    # diversidad_diaria_plantas ya debería ser numérico, pero coercemos por si acaso
    df_display["diversidad_diaria_plantas"] = pd.to_numeric(df_display["diversidad_diaria_plantas"], errors='coerce').fillna(0)
    df_display["sueno"] = pd.to_numeric(df_display["sueno"], errors='coerce')
    df_display["animo"] = pd.to_numeric(df_display["animo"], errors='coerce')

    st.markdown("---")
    st.subheader(f"📅 Tus vegetales únicos por día ({current_user_id})")
    
    # Usar 'comida_original' para mostrar, 'comida_normalizada_canonica' para lógica si es necesario
    for fecha_registro, grupo in df_display.sort_values("fecha", ascending=False).groupby("fecha"):
        plantas_originales_dia = set()
        # La columna 'comida_normalizada_canonica' contiene los nombres normalizados de *todos* los alimentos.
        # Filtramos solo los que son plantas.
        for idx, row_comida_norm_str in grupo["comida_normalizada_canonica"].dropna().items():
            items_norm_canonicos = [i.strip() for i in row_comida_norm_str.split(",") if i.strip()]
            for item_norm_c in items_norm_canonicos:
                if item_norm_c in normalized_plant_food_items: # Es una planta
                    # Recuperar su nombre original para mostrarlo
                    original_name = food_details_db.get(item_norm_c, {}).get("original_name", item_norm_c)
                    plantas_originales_dia.add(original_name)
        
        if plantas_originales_dia:
            st.markdown(f"📆 **{fecha_registro.strftime('%Y-%m-%d')}**: {len(plantas_originales_dia)} planta(s): {', '.join(sorted(list(plantas_originales_dia)))}")
        else:
            st.markdown(f"📆 **{fecha_registro.strftime('%Y-%m-%d')}**: 0 plantas.")

    st.markdown("---")
    st.subheader(f"🌿 Tu diversidad vegetal esta semana ({current_user_id})")
    
    hoy = datetime.now().date()
    inicio_semana_actual = hoy - timedelta(days=hoy.weekday()) 
    
    df_semana_actual = df_display[df_display["fecha"] >= inicio_semana_actual]
    
    plantas_consumidas_semana_actual_norm_canonicas = set()
    for comida_norm_str in df_semana_actual["comida_normalizada_canonica"].dropna():
        items_norm_canonicos = [i.strip() for i in comida_norm_str.split(",") if i.strip()]
        for item_norm_c in items_norm_canonicos:
            if item_norm_c in normalized_plant_food_items:
                plantas_consumidas_semana_actual_norm_canonicas.add(item_norm_c)
    
    progreso = len(plantas_consumidas_semana_actual_norm_canonicas)
    st.markdown(f"Esta semana has comido **{progreso} / 30** plantas diferentes.")
    st.progress(min(progreso / 30.0, 1.0))

    st.subheader("💡 Sugerencias inteligentes para hoy")
    if progreso < 30:
        sugerencias_inteligentes = get_smart_suggestions(plantas_consumidas_semana_actual_norm_canonicas)
        if sugerencias_inteligentes:
            st.markdown("🌟 Prueba algo nuevo: " + ", ".join(sugerencias_inteligentes))
        else:
            st.info("¡Parece que no quedan más plantas por sugerir o ya las has probado todas las de la lista para esta semana!")
    elif progreso >= 30:
        st.success("🎉 ¡Felicidades! Ya has alcanzado o superado las 30 plantas distintas esta semana.")

    # --- Visualizaciones Plotly (usando diversidad_diaria_plantas) ---
    if not df_display.empty:
        st.subheader("📊 Gráfico: Ánimo vs. Sueño")
        fig = px.scatter(df_display.dropna(subset=['sueno', 'animo']), x="sueno", y="animo", 
                         hover_data=["fecha", "comida_original"], title="Relación Ánimo y Sueño")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📈 Diversidad de plantas por día")
        # Asegurar que la fecha esté ordenada para el gráfico de línea
        df_plot_line = df_display.sort_values(by="fecha")
        fig2 = px.line(df_plot_line, x="fecha", y="diversidad_diaria_plantas", title="Evolución de la Diversidad Diaria de Plantas")
        st.plotly_chart(fig2, use_container_width=True)

        # --- ML: Regresión para predecir ánimo ---
        st.subheader("🤖 Predicción de Ánimo (ML)")
        df_ml = df_display[['sueno', 'animo', 'diversidad_diaria_plantas']].copy()
        df_ml.dropna(inplace=True)

        if len(df_ml) > 3 and 'sueno' in df_ml.columns and 'animo' in df_ml.columns:
            X = df_ml[["sueno", "diversidad_diaria_plantas"]]
            y = df_ml["animo"]
            try:
                model = LinearRegression().fit(X, y)
                st.markdown(f"Modelo de predicción de ánimo (beta): Coeficiente sueño: {model.coef_[0]:.2f}, Coeficiente diversidad: {model.coef_[1]:.2f} — Intercepto: {model.intercept_:.2f}")
                st.caption("Esto es una simplificación. El ánimo depende de muchos factores.")
            except Exception as e:
                st.warning(f"No se pudo entrenar el modelo de regresión: {e}")
        else:
            st.info("No hay suficientes datos (se necesitan >3 registros con sueño y ánimo) para entrenar el modelo de predicción de ánimo.")

        # --- ML: Clustering perfiles ---
        st.subheader("👥 Clusters de Días")
        features_cluster = df_display[["diversidad_diaria_plantas", "sueno", "animo"]].copy()
        features_cluster.dropna(inplace=True)

        if len(features_cluster) >= 3:
            n_clusters_kmeans = min(3, len(features_cluster)) 
            if n_clusters_kmeans < 2: n_clusters_kmeans = 2

            if len(features_cluster) >= n_clusters_kmeans :
                try:
                    kmeans = KMeans(n_clusters=n_clusters_kmeans, random_state=42, n_init='auto').fit(features_cluster)
                    df_display_clustered = df_display.loc[features_cluster.index].copy() # Alinea con los datos que se usaron para el cluster
                    df_display_clustered['cluster'] = kmeans.labels_

                    fig3 = px.scatter(df_display_clustered.dropna(subset=['cluster']), x="diversidad_diaria_plantas", y="sueno", color="cluster",
                                      hover_data=["fecha", "animo"], title=f"Clusters de Días ({n_clusters_kmeans} grupos)")
                    st.plotly_chart(fig3, use_container_width=True)
                    st.caption("Los clusters agrupan días con características similares de diversidad, sueño y ánimo.")
                except Exception as e:
                    st.warning(f"No se pudo realizar el clustering: {e}")
            else:
                st.info("No hay suficientes datos para el clustering con el número de clusters deseado.")
        else:
            st.info("No hay suficientes datos (se necesitan >=3 registros con diversidad, sueño y ánimo) para el clustering.")

    # --- Export CSV ---
    st.subheader("📤 Exportar tus datos")
    if not df_user.empty: # Exportar todos los datos del usuario, no solo df_display
        csv_buffer = io.StringIO()
        # Seleccionar y renombrar columnas para exportación si es necesario
        df_export = df_user.copy()
        # df_export.rename(columns={'diversidad_diaria_plantas': 'plant_diversity_daily', ...}, inplace=True)
        df_export.to_csv(csv_buffer, index=False, encoding='utf-8')
        st.download_button(
            label="⬇️ Descargar tus datos como CSV",
            data=csv_buffer.getvalue(),
            file_name=f"registro_nutribio_{current_user_id}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("No hay datos para exportar.")


# --- Mensajes sobre Prebióticos y Probióticos ---
def mostrar_mensajes_pre_probioticos(df_user_registros_diarios, current_user_id):
    st.markdown("---")
    st.subheader("💡 Sabías que...")

    mensajes_generales = [
        "Los **probióticos** son microorganismos vivos beneficiosos. ¡Busca yogur natural, kéfir, chucrut o kimchi no pasteurizados!",
        "Los **prebióticos** son el alimento de tus bacterias intestinales. Encuéntralos en ajos, cebollas, puerros, espárragos, plátanos verdes y avena.",
        "Una microbiota diversa es clave para una buena digestión e inmunidad. ¡Varía tus fuentes de prebióticos y probióticos!",
        "El consumo regular de prebióticos puede mejorar la absorción de minerales como el calcio.",
        "Los probióticos pueden ayudar a equilibrar tu microbiota, especialmente útil después de un tratamiento con antibióticos.",
        "Incluir alimentos fermentados en tu dieta es una excelente forma de obtener probióticos naturales."
    ]
    st.info(random.choice(mensajes_generales))

    if not df_user_registros_diarios.empty:
        consumo_reciente_pro = False
        consumo_reciente_pre = False
        hoy = datetime.now().date()
        # Considerar registros de los últimos 3 días (registros_diarios)
        registros_recientes = df_user_registros_diarios[
            (pd.to_datetime(df_user_registros_diarios["fecha"]).dt.date >= (hoy - timedelta(days=3))) &
            (df_user_registros_diarios["tipo_registro"] == "registro_diario")
        ]

        alimentos_consumidos_recientemente_norm = set()
        for _, row in registros_recientes.iterrows():
            comida_norm_str = str(row.get("comida_normalizada_canonica", "")).split(",")
            for item_norm in comida_norm_str:
                alimentos_consumidos_recientemente_norm.add(item_norm.strip())
        
        if normalized_probiotic_foods.intersection(alimentos_consumidos_recientemente_norm):
            consumo_reciente_pro = True
        if normalized_prebiotic_foods.intersection(alimentos_consumidos_recientemente_norm):
            consumo_reciente_pre = True
            
        if not consumo_reciente_pro:
            sugerencia_pro = random.sample(list(probiotic_foods_original_case), min(3, len(probiotic_foods_original_case))) if probiotic_foods_original_case else []
            st.warning(f"💡 {current_user_id}, parece que no has registrado probióticos recientemente. Considera añadir: {', '.join(sugerencia_pro)}.")
        if not consumo_reciente_pre:
            sugerencia_pre = random.sample(list(prebiotic_foods_original_case), min(3, len(prebiotic_foods_original_case))) if prebiotic_foods_original_case else []
            st.warning(f"💡 {current_user_id}, ¿qué tal unos prebióticos? {', '.join(sugerencia_pre)} son buenas opciones para alimentar tu microbiota.")


# --- NUEVO: Contenido Educativo (Punto 3) ---
contenido_educativo = {
    "pni_alimentacion": {
        "titulo_modulo": "🤝 PNI y Alimentación: Conectando Mente y Plato",
        "lecciones": [
            {
                "id": "pni_intro",
                "titulo": "¿Qué es la Psiconeuroinmunología (PNI)?",
                "texto": """La Psiconeuroinmunología (PNI) es la ciencia que estudia la compleja interacción entre nuestros procesos psicológicos (mente y emociones), el sistema nervioso (cerebro y nervios), el sistema inmune (defensas) y el sistema endocrino (hormonas).
                \n\nEn esencia, la PNI nos enseña cómo nuestros pensamientos, estrés y estilo de vida, especialmente la alimentación, pueden influir directamente en nuestra salud física y mental a través de estos sistemas interconectados. Una alimentación antiinflamatoria y nutritiva es un pilar fundamental para mantener este delicado equilibrio.""",
                "imagen_url": None,
                "quiz": {
                    "pregunta": "La PNI se enfoca únicamente en cómo la nutrición afecta el sistema inmune.",
                    "opciones": ["Verdadero", "Falso"],
                    "respuesta_correcta": "Falso",
                    "explicacion": "La PNI es más amplia, estudiando las interacciones entre los sistemas psicológico, nervioso, inmune y endocrino, y cómo la alimentación y otros factores del estilo de vida influyen en todos ellos."
                }
            },
            {
                "id": "pni_30_plantas",
                "titulo": "🎯 Las 30 Plantas Semanales y la PNI",
                "texto": """Desde la perspectiva de la PNI, consumir una amplia variedad de plantas (¡como el objetivo de 30 distintas por semana!) es crucial por varias razones:
                \n- **Nutrición para la Microbiota:** Cada planta aporta diferentes tipos de fibra y polifenoles que alimentan a distintas cepas de bacterias beneficiosas en tu intestino. Una microbiota diversa es clave para una buena digestión, un sistema inmune fuerte y hasta para la producción de neurotransmisores que afectan tu ánimo.
                \n- **Reducción de la Inflamación:** Muchos fitoquímicos presentes en las plantas (antioxidantes, polifenoles) tienen propiedades antiinflamatorias, ayudando a contrarrestar la inflamación crónica de bajo grado, un factor subyacente en muchas enfermedades modernas.
                \n- **Aporte de Micronutrientes:** Vitaminas, minerales y oligoelementos esenciales se encuentran en abundancia y variedad en el mundo vegetal, siendo cofactores indispensables para miles de reacciones bioquímicas en el cuerpo, incluyendo las de los sistemas nervioso e inmune.
                \n\nAl diversificar tus plantas, aseguras una gama más amplia de estos compuestos beneficiosos, fortaleciendo la resiliencia de tu organismo.""",
                 "quiz": {
                    "pregunta": "Según la PNI, la diversidad de plantas en la dieta solo beneficia la digestión.",
                    "opciones": ["Verdadero", "Falso"],
                    "respuesta_correcta": "Falso",
                    "explicacion": "Beneficia la microbiota, reduce la inflamación y aporta micronutrientes esenciales para múltiples sistemas, incluyendo el nervioso e inmune."
                }
            },
        ]
    },
    "microbiota_poder": {
        "titulo_modulo": "🔬 El Poder de tu Microbiota",
        "lecciones": [
            {
                "id": "micro_intro",
                "titulo": "🦠 Tu Universo Interior: La Microbiota",
                "texto": "Tu intestino alberga billones de microorganismos (bacterias, virus, hongos) conocidos como microbiota intestinal. Este ecosistema juega un papel vital en tu salud: digiere alimentos, produce vitaminas, entrena tu sistema inmune y se comunica con tu cerebro. ¡Cuidarla es cuidarte!",
            },
            {
                "id": "micro_prebioticos",
                "titulo": "🌾 Prebióticos: El Festín de tus Bacterias Buenas",
                "texto": "Los prebióticos son tipos de fibra que nosotros no podemos digerir, pero que sirven de alimento selectivo para las bacterias beneficiosas de nuestra microbiota. Al consumirlos, fomentamos el crecimiento de estas bacterias. Encuéntralos en alimentos como el ajo, la cebolla, el puerro, los espárragos, la alcachofa, el plátano (especialmente si no está muy maduro) y la avena.",
                "quiz": {
                    "pregunta": "¿Los prebióticos son bacterias vivas que añadimos a nuestra dieta?",
                    "opciones": ["Verdadero", "Falso"],
                    "respuesta_correcta": "Falso",
                    "explicacion": "Los prebióticos son el 'alimento' para nuestras bacterias beneficiosas. Los probióticos son las bacterias vivas."
                }
            },
             {
                "id": "micro_probioticos",
                "titulo": "🍦 Probióticos: Refuerzos Vivos para tu Ejército Interno",
                "texto": "Los probióticos son microorganismos vivos que, cuando se administran en cantidades adecuadas, confieren un beneficio para la salud. Pueden ayudar a equilibrar la microbiota, especialmente después de antibióticos, o mejorar ciertas funciones digestivas. Los encuentras en alimentos fermentados como el yogur natural, kéfir, chucrut (no pasteurizado), kimchi, miso y kombucha.",
            }
        ]
    },
    "crononutricion": {
        "titulo_modulo": "⏰ Crononutrición: Comer en Sintonía con tu Reloj Biológico",
        "lecciones": [
            {
                "id": "crono_intro",
                "titulo": "🕰️ ¿Qué es la Crononutrición?",
                "texto": """La crononutrición estudia cómo el momento de la ingesta de alimentos interactúa con nuestros ritmos circadianos (nuestro reloj biológico interno de aproximadamente 24 horas) y cómo esto afecta nuestro metabolismo y salud.
                \n\nNo solo importa *qué* comes, sino también *cuándo* lo comes. Nuestro cuerpo está programado para realizar ciertas funciones de manera más eficiente en diferentes momentos del día. Por ejemplo, la sensibilidad a la insulina suele ser mayor por la mañana.""",
            },
            {
                "id": "crono_tips",
                "titulo": "💡 Principios Básicos de Crononutrición",
                "texto": """
                - **Desayuno Nutritivo:** Prioriza un desayuno completo y rico en proteínas y fibra. Es el momento en que el cuerpo suele estar más preparado para metabolizar nutrientes.
                - **Comidas Principales Durante el Día:** Intenta concentrar la mayor parte de tu ingesta calórica durante las horas de luz.
                - **Cena Ligera y Temprana:** Evita comidas copiosas y tardías. Cenar al menos 2-3 horas antes de acostarte puede mejorar la digestión, el sueño y la reparación celular nocturna.
                - **Ayuno Nocturno:** Permitir un periodo de ayuno de unas 12-14 horas entre la cena y el desayuno del día siguiente puede tener beneficios metabólicos.
                \n\nEscucha a tu cuerpo y adapta estos principios a tu estilo de vida y necesidades individuales. No se trata de reglas estrictas, sino de tomar conciencia de nuestros ritmos naturales.""",
                 "quiz": {
                    "pregunta": "Según la crononutrición, el mejor momento para una comida muy abundante es justo antes de dormir.",
                    "opciones": ["Verdadero", "Falso"],
                    "respuesta_correcta": "Falso",
                    "explicacion": "La crononutrición sugiere cenas más ligeras y tempranas para respetar los ritmos circadianos y favorecer el descanso y la reparación."
                }
            }
        ]
    }
}

def display_contenido_educativo():
    st.title("📚 NutriWiki: Aprende y Crece")
    
    # Crear columnas para los módulos principales para un layout más agradable si hay muchos
    # Por ahora, una sola columna
    
    for id_modulo, modulo_data in contenido_educativo.items():
        with st.expander(f"**{modulo_data['titulo_modulo']}**", expanded=False):
            for leccion in modulo_data["lecciones"]:
                st.subheader(leccion["titulo"])
                st.markdown(leccion["texto"]) # Usar markdown para permitir formato en el texto
                if leccion.get("imagen_url"):
                    try:
                        st.image(leccion["imagen_url"]) # Asegúrate de que la ruta sea correcta si son locales
                    except Exception as e:
                        st.warning(f"No se pudo cargar la imagen: {leccion['imagen_url']}. Error: {e}")

                if leccion.get("quiz"):
                    quiz_data = leccion["quiz"]
                    st.markdown("**Mini Quiz:**")
                    # Usar un form para el quiz para que el botón no reinicie toda la app
                    with st.form(key=f"quiz_form_{id_modulo}_{leccion['id']}"):
                        respuesta_usuario = st.radio(quiz_data["pregunta"], quiz_data["opciones"], key=f"quiz_radio_{id_modulo}_{leccion['id']}", index=None)
                        submitted_quiz = st.form_submit_button("Comprobar respuesta")

                        if submitted_quiz:
                            if respuesta_usuario is None:
                                st.warning("Por favor, selecciona una respuesta.")
                            elif respuesta_usuario == quiz_data["respuesta_correcta"]:
                                st.success("¡Correcto! 🎉")
                            else:
                                st.error(f"No del todo. La respuesta correcta es: {quiz_data['respuesta_correcta']}")
                            
                            if quiz_data.get("explicacion") and respuesta_usuario is not None:
                                st.info(f"Explicación: {quiz_data['explicacion']}")
                st.markdown("---")

# --- Main App ---
def main():
     sheet = None 
    if google_services_available and creds_gspread: # Comprobar que creds_gspread esté inicializado
        sheet = get_sheet() # <--- SIN ARGUMENTOS AQUÍ
        if sheet:
            check_and_create_headers(sheet
    st.sidebar.header("👤 Usuario")
    if 'current_user' not in st.session_state:
        st.session_state.current_user = ""

    user_input = st.sidebar.text_input("Ingresa tu nombre de usuario:", value=st.session_state.current_user, key="user_login_input")
    
    if st.sidebar.button("Acceder / Cambiar Usuario"):
        if user_input:
            st.session_state.current_user = normalize_text(user_input.strip())
            st.sidebar.success(f"Usuario actual: {st.session_state.current_user}")
            # Borrar datos cacheados de usuario anterior si es necesario (no aplica mucho aquí aún)
        else:
            st.sidebar.error("El nombre de usuario no puede estar vacío.")

    current_user_id = st.session_state.current_user

    # Navegación principal
    st.sidebar.title("Navegación")
    pagina_seleccionada = st.sidebar.radio("Ir a:", 
                                           ["🎯 Registro y Progreso", "📚 Aprende"], 
                                           key="nav_main")

    if not current_user_id and pagina_seleccionada != "📚 Aprende": # Se puede acceder a Aprende sin user
        st.info("Por favor, ingresa un nombre de usuario en la barra lateral para registrar datos y ver tu progreso.")
        st.stop()

    sheet = None # Inicializar sheet
    if google_services_available and creds_gspread: # creds_gspread ahora es global
        sheet = get_sheet(creds_gspread) # Pasar creds_gspread
        if sheet:
            check_and_create_headers(sheet)
    elif not google_services_available and pagina_seleccionada != "📚 Aprende":
        st.error("Los servicios de Google no están disponibles. El registro y la visualización de datos no funcionarán.")
        # No detener si quiere ir a "Aprende"


    if pagina_seleccionada == "🎯 Registro y Progreso":
        if not current_user_id: # Doble check si se fuerza esta página sin user
            st.info("Por favor, ingresa un nombre de usuario en la barra lateral para continuar.")
            st.stop()
            
        st.header(f"🎯 Registro y Progreso de {current_user_id}")
        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f"📋 Registro diario")
            with st.form("registro_diario_form"):
                seleccionados_form = st.multiselect(
                    "¿Qué comiste hoy? (Puedes escribir para buscar)",
                    options=all_selectable_food_items_original_case, # Usa la lista derivada de food_details_db
                    help="Escribe parte del nombre, ej: 'manza' para 'Manzana'."
                )
                
                fecha_registro_form = st.date_input("Fecha del registro", datetime.now().date())
                sueno_form = st.number_input("¿Horas de sueño?", min_value=0.0, max_value=24.0, step=0.5, value=7.5) # Cambiado a 7.5
                ejercicio_form = st.text_input("¿Ejercicio realizado? (ej: Caminar 30 min, Yoga, Pesas)")
                animo_form = st.slider("¿Cómo te sientes hoy? (1=Mal, 5=Excelente)", 1, 5, 3)
                
                submitted_registro_manual = st.form_submit_button("Guardar Registro Manual")

                if submitted_registro_manual:
                    if not seleccionados_form:
                        st.warning("Por favor, selecciona al menos un alimento.")
                    else:
                        # Los seleccionados_form ya son nombres originales canónicos porque vienen de all_selectable_food_items_original_case
                        guardar_registro(sheet, current_user_id, fecha_registro_form, seleccionados_form, sueno_form, ejercicio_form, animo_form)
                        st.rerun() # Para refrescar los datos mostrados

        with col2:
            st.subheader("📸 Detección desde foto (Plantas)")
            if vision_client is None:
                st.warning("La detección por imagen no está disponible (cliente de Vision no inicializado).")
            else:
                img_file = st.file_uploader("Sube una foto de tu comida (opcional)", type=["jpg", "jpeg", "png"])

                if img_file:
                    st.image(img_file, caption="Tu imagen", use_container_width=True)
                    img_bytes = img_file.getvalue()
                    
                    if 'detected_plants_img' not in st.session_state:
                        st.session_state.detected_plants_img = []
                    
                    if st.button("🔍 Detectar Plantas en Imagen"):
                        with st.spinner("Detectando plantas en la imagen..."):
                            # Solo se obtendrán plantas gracias al filtro en detectar_alimentos_google_vision
                            st.session_state.detected_plants_img = detectar_alimentos_google_vision(img_bytes)
                        if not st.session_state.detected_plants_img:
                             st.warning("🤔 No se detectaron plantas conocidas en la imagen. Puedes añadirlas manualmente.")


                    if st.session_state.detected_plants_img:
                        st.info(f"Posibles plantas detectadas: {', '.join(st.session_state.detected_plants_img)}")
                        with st.form("confirmar_vegetales_img_form"):
                            st.write("Por favor, confirma las plantas y añade otras si es necesario.")
                            confirmados_api = st.multiselect(
                                "Confirma las plantas detectadas en tu comida:",
                                options=st.session_state.detected_plants_img, # Ya son nombres originales canónicos
                                default=st.session_state.detected_plants_img
                            )
                            # Opciones para añadir: todas las plantas menos las ya detectadas por la API
                            opciones_adicionales = [
                                p for p in plant_food_items_original_case # Usar la lista de solo plantas
                                if p not in st.session_state.detected_plants_img
                            ]
                            adicionales_manual_img = st.multiselect(
                                "Añade otras plantas de tu comida (si no fueron detectadas):",
                                options=opciones_adicionales
                            )
                            
                            todos_seleccionados_img = sorted(list(set(confirmados_api + adicionales_manual_img)))
                            
                            st.write("**Completa los datos para este registro (imagen):**")
                            fecha_registro_img = st.date_input("Fecha del registro (imagen)", datetime.now().date(), key="fecha_img_reg") # Cambiada la key
                            # Usar valores del form manual como default si existen, sino los genéricos
                            sueno_img_val = st.session_state.get('sueno_form_val', 7.5)
                            ejercicio_img_val = st.session_state.get('ejercicio_form_val', "")
                            animo_img_val = st.session_state.get('animo_form_val', 3)

                            sueno_img = st.number_input("¿Horas de sueño ese día?", min_value=0.0, max_value=24.0, step=0.5, value=sueno_img_val, key="sueno_img_reg")
                            ejercicio_img = st.text_input("¿Ejercicio realizado ese día?", value=ejercicio_img_val, key="ejercicio_img_reg")
                            animo_img = st.slider("¿Cómo te sentiste ese día? (1=Mal, 5=Excelente)", 1, 5, value=animo_img_val, key="animo_img_reg")

                            submitted_confirmar_img = st.form_submit_button("✅ Confirmar y Guardar Plantas de Imagen")

                            if submitted_confirmar_img:
                                if not todos_seleccionados_img:
                                    st.warning("No has seleccionado ninguna planta para guardar.")
                                else:
                                    # Guardar todos_seleccionados_img (ya son nombres originales canónicos de plantas)
                                    guardar_registro(sheet, current_user_id, fecha_registro_img, todos_seleccionados_img, sueno_img, ejercicio_img, animo_img)
                                    st.session_state.detected_plants_img = [] # Limpiar después de guardar
                                    st.rerun()


        # --- Visualización de registros y análisis (fuera de las columnas) ---
        if sheet:
            st.markdown("---")
            st.header(f"📊 Tu Progreso y Análisis") # No es necesario el user ID aquí de nuevo
            
            if st.button(f"🗓️ Calcular/Actualizar Resumen Semanal (para la semana pasada)"):
                hoy_calc = datetime.now().date()
                lunes_esta_semana_calc = hoy_calc - timedelta(days=hoy_calc.weekday())
                calcular_y_guardar_resumen_semanal_usuario(sheet, current_user_id, lunes_esta_semana_calc)
                st.rerun()

            try:
                # Leer todos los registros y luego filtrar por usuario.
                # Esto es menos eficiente que filtrar en la query si la API de gspread lo permitiera fácilmente,
                # pero para hojas de tamaño moderado es aceptable.
                data_with_headers = sheet.get_all_records(expected_headers=EXPECTED_HEADERS)
                df_full = pd.DataFrame(data_with_headers)
                
                if not df_full.empty and "usuario" in df_full.columns:
                    df_user_specific = df_full[df_full["usuario"] == current_user_id].copy()
                    
                    if not df_user_specific.empty:
                        # Convertir 'fecha' a datetime.date aquí para df_user_specific una vez
                        df_user_specific["fecha"] = pd.to_datetime(df_user_specific["fecha"], errors='coerce').dt.date
                        df_user_specific.dropna(subset=["fecha"], inplace=True)
                        
                        mostrar_registros_y_analisis(df_user_specific, current_user_id)
                        
                        df_user_registros_tipo_registro = df_user_specific[df_user_specific['tipo_registro'] == 'registro_diario'].copy()
                        mostrar_mensajes_pre_probioticos(df_user_registros_tipo_registro, current_user_id)
                    else:
                        st.info(f"No hay datos registrados para el usuario '{current_user_id}'. ¡Empieza a añadir tus comidas!")
                elif df_full.empty:
                    st.info("La hoja de cálculo parece estar vacía. ¡Comienza a registrar tus comidas!")
                else: # df_full no está vacía pero no tiene la columna 'usuario' o algo falló
                     st.warning("No se pudieron cargar los datos correctamente o la hoja no tiene la columna 'usuario'.")


            except gspread.exceptions.GSpreadException as e:
                st.error(f"Error de gspread al obtener registros: {e}. Asegúrate que los encabezados en la hoja ('{sheet.title if sheet else 'DESCONOCIDO'}') son: {', '.join(EXPECTED_HEADERS)}")
            except Exception as e:
                st.warning(f"No se pudieron cargar o procesar todos los datos de Google Sheets: {type(e).__name__} - {e}")
                st.info("Si acabas de empezar, puede que aún no haya datos que mostrar.")
        elif not google_services_available:
             st.error("No se puede mostrar el progreso porque los servicios de Google (Sheets) no están disponibles.")


    elif pagina_seleccionada == "📚 Aprende":
        display_contenido_educativo()

if __name__ == "__main__":
    main()

