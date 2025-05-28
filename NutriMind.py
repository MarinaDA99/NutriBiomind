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
# import base64 # No se usa actualmente, se puede descomentar si se necesita en el futuro
from unidecode import unidecode # NUEVO: Para quitar acentos
import random # NUEVO: Para mensajes aleatorios

st.set_page_config(page_title="NutriBioMind", layout="centered")
st.title("🌱 La regla de oro: ¡30 plantas distintas por semana!")

# --- Configuración de Clientes de Google Cloud ---
creds_gspread = None
vision_client = None
google_services_available = False
gcp_secret_content_type_for_error = "unknown"
creds_info_dict = None # Definido aquí para un alcance más amplio

try:
    gcp_secret_content = st.secrets["gcp_service_account"]
    gcp_secret_content_type_for_error = str(type(gcp_secret_content))
    # creds_info_dict = None # Ya está definido arriba

    if isinstance(gcp_secret_content, str):
        creds_info_dict = json.loads(gcp_secret_content)
    elif hasattr(gcp_secret_content, 'to_dict') and callable(gcp_secret_content.to_dict):
        creds_info_dict = gcp_secret_content.to_dict()
    elif isinstance(gcp_secret_content, dict):
        creds_info_dict = gcp_secret_content
    else:
        try:
            creds_info_dict = dict(gcp_secret_content)
        except (TypeError, ValueError) as convert_err:
            st.error(f"El contenido del secreto 'gcp_service_account' no es un string JSON ni un diccionario/AttrDict convertible. Error de conversión: {convert_err}")
            raise ValueError(f"Formato de secreto no compatible: {gcp_secret_content_type_for_error}")

    if creds_info_dict is None or not isinstance(creds_info_dict, dict):
        st.error(f"No se pudo interpretar el contenido del secreto 'gcp_service_account' como un diccionario. Tipo obtenido: {gcp_secret_content_type_for_error}")
        raise ValueError("Fallo al interpretar el secreto como diccionario.")

    # 1. Inicializar credenciales para gspread
    scope_gspread = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_gspread = ServiceAccountCredentials.from_json_keyfile_dict(creds_info_dict, scope_gspread)

    # 2. Inicializar cliente de Vision con las credenciales cargadas explícitamente
    from google.oauth2 import service_account as google_service_account # Importación movida aquí
    vision_credentials = google_service_account.Credentials.from_service_account_info(creds_info_dict)
    vision_client = vision.ImageAnnotatorClient(credentials=vision_credentials)

    google_services_available = True
    # st.sidebar.success("Servicios de Google conectados.") # Optional

except KeyError:
    st.error("Error Crítico: La clave 'gcp_service_account' no se encontró en los secretos de Streamlit (secrets.toml). Asegúrate de haberla configurado correctamente.")
except json.JSONDecodeError:
    st.error("Error Crítico: El valor de 'gcp_service_account' (si se interpretó como string) no es un JSON válido. Verifica la estructura del JSON.")
except ValueError as ve:
    st.error(f"Error de configuración o interpretación de secretos: {ve}")
except Exception as e:
    st.error(f"Error inesperado al inicializar los servicios de Google: {e}. Tipo de contenido del secreto procesado: {gcp_secret_content_type_for_error}. Algunas funciones podrían no estar disponibles.")

# --- Base de Datos Detallada de Alimentos ---
def normalize_text(text):
    if text is None:
        return ""
    return unidecode(str(text)).lower().strip()

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
    normalize_text("espárrago"): {"original_name": "Espárrago", "category_key": "🥦 Verduras y hortalizas", "color": "verde/blanco/morado", "pni_benefits": ["asparagina", "prebiótico (inulina)", "folato", "glutation"], "tags": ["diurético", "detox", "primavera"]},
    normalize_text("remolacha"): {"original_name": "Remolacha", "category_key": "🥦 Verduras y hortalizas", "color": "rojo/morado", "pni_benefits": ["nitratos (vasodilatador)", "betanina", "folato", "fibra"], "tags": ["raiz", "colorante natural", "rendimiento deportivo", "detox"]},
    normalize_text("col rizada"): {"original_name": "Col Rizada (Kale)", "category_key": "🥦 Verduras y hortalizas", "color": "verde oscuro", "pni_benefits": ["vitamina K", "vitamina C", "glucosinolatos", "luteína", "zeaxantina"], "tags": ["hoja verde", "cruciferas", "superalimento", "rica en nutrientes"]},
    normalize_text("kale"): {"original_name": "Kale (Col Rizada)", "category_key": "🥦 Verduras y hortalizas", "color": "verde oscuro", "pni_benefits": ["vitamina K", "vitamina C", "glucosinolatos", "luteína", "zeaxantina"], "tags": ["hoja verde", "cruciferas", "superalimento", "rica en nutrientes"]},
    normalize_text("nabo"): {"original_name": "Nabo", "category_key": "🥦 Verduras y hortalizas", "color": "blanco/morado", "pni_benefits": ["fibra", "vitamina C", "glucosinolatos"], "tags": ["raiz", "cruciferas", "sabor terroso"]},
    normalize_text("chirivía"): {"original_name": "Chirivía", "category_key": "🥦 Verduras y hortalizas", "color": "blanco crema", "pni_benefits": ["fibra", "potasio", "vitamina C", "folato"], "tags": ["raiz", "dulce", "invierno"]},
    normalize_text("guisante"): {"original_name": "Guisante", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["fibra", "proteína vegetal", "vitamina K", "manganeso"], "tags": ["leguminosa verde", "dulce", "primavera"]},
    normalize_text("judía verde"): {"original_name": "Judía Verde", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["fibra", "vitamina K", "vitamina C", "silicio"], "tags": ["leguminosa verde", "crujiente", "baja en calorías"]},
    normalize_text("habas"): {"original_name": "Habas", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["fibra", "proteína vegetal", "folato", "levodopa (precursor dopamina)"], "tags": ["leguminosa verde", "primavera"]},
    normalize_text("pimiento verde"): {"original_name": "Pimiento Verde", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["vitamina C", "fibra", "clorofila"], "tags": ["solanacea", "sabor más amargo que otros pimientos"]},
    normalize_text("pimiento amarillo"): {"original_name": "Pimiento Amarillo", "category_key": "🥦 Verduras y hortalizas", "color": "amarillo", "pni_benefits": ["vitamina C (alta)", "betacaroteno", "luteína", "zeaxantina"], "tags": ["solanacea", "dulce", "antioxidante"]},
    normalize_text("cebolla morada"): {"original_name": "Cebolla Morada", "category_key": "🥦 Verduras y hortalizas", "color": "morado", "pni_benefits": ["quercetina", "antocianinas", "prebiótico"], "tags": ["aliacea", "color vibrante", "cruda en ensaladas"]},
    normalize_text("cebolleta"): {"original_name": "Cebolleta", "category_key": "🥦 Verduras y hortalizas", "color": "blanco/verde", "pni_benefits": ["flavonoides", "vitamina K", "fibra"], "tags": ["aliacea", "suave", "fresca"]},
    normalize_text("chalota"): {"original_name": "Chalota", "category_key": "🥦 Verduras y hortalizas", "color": "marrón/morado claro", "pni_benefits": ["compuestos azufrados", "antioxidantes", "vitaminas B"], "tags": ["aliacea", "sabor delicado", "gourmet"]},
    normalize_text("rábano"): {"original_name": "Rábano", "category_key": "🥦 Verduras y hortalizas", "color": "rojo/blanco/negro", "pni_benefits": ["glucosinolatos", "vitamina C", "fibra", "efecto detoxificante"], "tags": ["raiz", "cruciferas", "picante", "digestivo"]},
    normalize_text("endivia"): {"original_name": "Endivia", "category_key": "🥦 Verduras y hortalizas", "color": "blanco/amarillo claro", "pni_benefits": ["inulina (prebiótico)", "folato", "vitamina K"], "tags": ["hoja amarga", "digestiva", "achicoria"]},
    normalize_text("escarola"): {"original_name": "Escarola", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["fibra", "folato", "vitamina A", "intibina (amargor)"], "tags": ["hoja amarga", "invierno", "digestiva"]},
    normalize_text("lechuga iceberg"): {"original_name": "Lechuga Iceberg", "category_key": "🥦 Verduras y hortalizas", "color": "verde claro", "pni_benefits": ["agua (hidratante)", "baja en calorías", "fibra (menor que otras hojas)"], "tags": ["hoja crujiente", "ensaladas"]},
    normalize_text("lechuga romana"): {"original_name": "Lechuga Romana", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["vitamina K", "vitamina A", "folato", "fibra"], "tags": ["hoja verde", "ensaladas", "crujiente"]},
    normalize_text("canónigos"): {"original_name": "Canónigos", "category_key": "🥦 Verduras y hortalizas", "color": "verde oscuro", "pni_benefits": ["vitamina C", "betacaroteno", "hierro", "ácido fólico"], "tags": ["hoja verde", "sabor suave", "delicada"]},
    normalize_text("rúcula"): {"original_name": "Rúcula", "category_key": "🥦 Verduras y hortalizas", "color": "verde oscuro", "pni_benefits": ["glucosinolatos", "vitamina K", "nitratos", "antioxidantes"], "tags": ["hoja verde", "sabor picante", "cruciferas"]},
    normalize_text("boniato"): {"original_name": "Boniato (Batata)", "category_key": "🥦 Verduras y hortalizas", "color": "naranja/morado/blanco", "pni_benefits": ["betacaroteno (naranja)", "antocianinas (morado)", "fibra", "vitamina C", "manganeso"], "tags": ["tuberculo", "dulce", "antiinflamatorio", "versátil"]},
    normalize_text("batata"): {"original_name": "Batata (Boniato)", "category_key": "🥦 Verduras y hortalizas", "color": "naranja/morado/blanco", "pni_benefits": ["betacaroteno (naranja)", "antocianinas (morado)", "fibra", "vitamina C", "manganeso"], "tags": ["tuberculo", "dulce", "antiinflamatorio", "versátil"]}, # Alias
    normalize_text("patata"): {"original_name": "Patata", "category_key": "🥦 Verduras y hortalizas", "color": "varios", "pni_benefits": ["potasio", "vitamina C", "almidón resistente (enfriada)", "vitamina B6"], "tags": ["tuberculo", "versátil", "fuente de energía", "solanacea"]},
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
    normalize_text("wasabi"): {"original_name": "Wasabi (raíz)", "category_key": "🥦 Verduras y hortalizas", "color": "verde claro", "pni_benefits": ["isotiocianatos (antibacterianos, antiinflamatorios)", "propiedades antimicrobianas"], "tags": ["raiz", "muy picante", "condimento japonés", "cruciferas"]},
    normalize_text("col lombarda"): {"original_name": "Col Lombarda", "category_key": "🥦 Verduras y hortalizas", "color": "morado", "pni_benefits": ["antocianinas", "vitamina C", "fibra", "glucosinolatos"], "tags": ["cruciferas", "color vibrante", "antioxidante"]},
    normalize_text("berros"): {"original_name": "Berros", "category_key": "🥦 Verduras y hortalizas", "color": "verde oscuro", "pni_benefits": ["feniletil isotiocianato (PEITC)", "vitamina K", "vitamina C", "antioxidantes"], "tags": ["hoja verde", "cruciferas", "sabor picante", "depurativo"]},
    normalize_text("diente de león (hojas)"): {"original_name": "Diente de León (hojas)", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["vitaminas A, C, K", "hierro", "calcio", "prebiótico (inulina en raíz)", "efecto diurético"], "tags": ["hoja amarga", "silvestre comestible", "depurativo", "nutritivo"]},
    normalize_text("topinambur"): {"original_name": "Topinambur (Alcachofa de Jerusalén)", "category_key": "🥦 Verduras y hortalizas", "color": "marrón claro/amarillo", "pni_benefits": ["inulina (alto contenido, prebiótico)", "hierro", "potasio"], "tags": ["tuberculo", "prebiótico potente", "sabor dulce anuezado", "produce gases en algunos"]},

    # Frutas
    normalize_text("manzana"): {"original_name": "Manzana", "category_key": "🍎 Frutas", "color": "varios (rojo, verde, amarillo)", "pni_benefits": ["pectina (fibra soluble, prebiótico)", "quercetina", "vitamina C", "antioxidantes"], "tags": ["con piel", "salud intestinal", "versátil"]},
    normalize_text("plátano"): {"original_name": "Plátano", "category_key": "🍎 Frutas", "color": "amarillo", "pni_benefits": ["potasio", "vitamina B6", "prebiótico (si no muy maduro - almidón resistente)", "triptófano"], "tags": ["energético", "salud muscular", "estado de ánimo"]},
    normalize_text("naranja"): {"original_name": "Naranja", "category_key": "🍎 Frutas", "color": "naranja", "pni_benefits": ["vitamina C", "hesperidina", "fibra (si se come entera)", "folato"], "tags": ["cítrico", "inmunidad", "antioxidante"]},
    normalize_text("fresa"): {"original_name": "Fresa", "category_key": "🍎 Frutas", "color": "rojo", "pni_benefits": ["antocianinas", "vitamina C", "manganeso", "fisetin"], "tags": ["baya", "antioxidante", "antiinflamatoria", "delicada"]},
    normalize_text("arándano"): {"original_name": "Arándano", "category_key": "🍎 Frutas", "color": "azul/morado", "pni_benefits": ["antocianinas (muy alta)", "pterostilbeno", "antioxidantes potentes", "salud cerebral"], "tags": ["baya", "superfood", "antiinflamatorio", "salud urinaria (arándano rojo)"]},
    normalize_text("kiwi"): {"original_name": "Kiwi", "category_key": "🍎 Frutas", "color": "verde (pulpa)/marrón (piel)", "pni_benefits": ["vitamina C (muy alta)", "actinidina (enzima digestiva)", "fibra", "serotonina"], "tags": ["digestivo", "inmunidad", "rico en vitamina C"]},
    normalize_text("mango"): {"original_name": "Mango", "category_key": "🍎 Frutas", "color": "naranja/amarillo/rojo", "pni_benefits": ["vitamina A (betacaroteno)", "vitamina C", "mangiferina (antioxidante)", "fibra"], "tags": ["tropical", "antioxidante", "dulce"]},
    normalize_text("aguacate"): {"original_name": "Aguacate", "category_key": "🍎 Frutas", "color": "verde (pulpa)/negro-verde (piel)", "pni_benefits": ["grasas saludables (ácido oleico)", "fibra", "potasio", "vitamina E", "folato"], "tags": ["grasa monoinsaturada", "salud cardiovascular", "antiinflamatorio", "fruta botanicamente"]},
    normalize_text("limón"): {"original_name": "Limón", "category_key": "🍎 Frutas", "color": "amarillo", "pni_benefits": ["vitamina C", "limonoides", "flavonoides", "efecto alcalinizante (en el cuerpo)"], "tags": ["cítrico", "detox", "antioxidante", "ácido"]},
    normalize_text("lima"): {"original_name": "Lima", "category_key": "🍎 Frutas", "color": "verde", "pni_benefits": ["vitamina C", "flavonoides", "antioxidantes"], "tags": ["cítrico", "refrescante", "cócteles", "ácida"]},
    normalize_text("pomelo"): {"original_name": "Pomelo", "category_key": "🍎 Frutas", "color": "rosa/rojo/blanco", "pni_benefits": ["vitamina C", "licopeno (rosa/rojo)", "naringenina", "fibra"], "tags": ["cítrico", "amargo", "interacción con medicamentos", "quema grasa (popular)"]},
    normalize_text("mandarina"): {"original_name": "Mandarina", "category_key": "🍎 Frutas", "color": "naranja", "pni_benefits": ["vitamina C", "nobiletina", "fibra", "criptoxantina"], "tags": ["cítrico", "fácil de pelar", "dulce"]},
    normalize_text("uva"): {"original_name": "Uva", "category_key": "🍎 Frutas", "color": "varios (verde, roja, negra)", "pni_benefits": ["resveratrol (piel uvas oscuras)", "antocianinas (uvas oscuras)", "quercetina", "antioxidantes"], "tags": ["baya", "antioxidante", "salud cardiovascular"]},
    normalize_text("melón"): {"original_name": "Melón", "category_key": "🍎 Frutas", "color": "varios (verde, naranja, amarillo)", "pni_benefits": ["hidratante (alto contenido de agua)", "vitamina C", "potasio", "betacaroteno (cantalupo)"], "tags": ["cucurbitacea", "verano", "refrescante", "diurético"]},
    normalize_text("sandía"): {"original_name": "Sandía", "category_key": "🍎 Frutas", "color": "rojo/rosa (pulpa), verde (corteza)", "pni_benefits": ["licopeno", "citrulina (vasodilatador)", "hidratante (muy alta en agua)", "vitamina C"], "tags": ["cucurbitacea", "verano", "refrescante", "hidratación"]},
    normalize_text("piña"): {"original_name": "Piña", "category_key": "🍎 Frutas", "color": "amarillo (pulpa)", "pni_benefits": ["bromelina (enzima digestiva, antiinflamatoria)", "vitamina C", "manganeso"], "tags": ["tropical", "digestiva", "antiinflamatoria"]},
    normalize_text("papaya"): {"original_name": "Papaya", "category_key": "🍎 Frutas", "color": "naranja (pulpa)", "pni_benefits": ["papaína (enzima digestiva)", "vitamina C", "betacaroteno", "licopeno"], "tags": ["tropical", "digestiva", "antioxidante"]},
    normalize_text("granada"): {"original_name": "Granada", "category_key": "🍎 Frutas", "color": "rojo (arilos y cáscara)", "pni_benefits": ["punicalaginas (potente antioxidante)", "ácido púnicico", "antiinflamatoria", "vitamina C"], "tags": ["superfruta", "antioxidante potente", "otoño"]},
    normalize_text("higo"): {"original_name": "Higo", "category_key": "🍎 Frutas", "color": "morado/verde/negro", "pni_benefits": ["fibra (laxante suave)", "calcio", "potasio", "polifenoles"], "tags": ["dulce", "fibra", "otoño"]},
    normalize_text("cereza"): {"original_name": "Cereza", "category_key": "🍎 Frutas", "color": "rojo/negro", "pni_benefits": ["antocianinas", "melatonina (ayuda al sueño)", "antiinflamatoria", "vitamina C"], "tags": ["baya (drupa)", "antiinflamatoria", "ácido úrico", "verano"]},
    normalize_text("ciruela"): {"original_name": "Ciruela", "category_key": "🍎 Frutas", "color": "varios (rojo, morado, amarillo)", "pni_benefits": ["fibra (sorbitol - laxante)", "antioxidantes", "vitamina K", "potasio"], "tags": ["laxante natural", "fibra", "verano"]},
    normalize_text("melocotón"): {"original_name": "Melocotón", "category_key": "🍎 Frutas", "color": "amarillo/naranja/rojo", "pni_benefits": ["vitamina C", "betacaroteno", "fibra", "antioxidantes"], "tags": ["verano", "dulce", "piel aterciopelada"]},
    normalize_text("albaricoque"): {"original_name": "Albaricoque", "category_key": "🍎 Frutas", "color": "naranja", "pni_benefits": ["betacaroteno", "vitamina C", "fibra", "catequinas"], "tags": ["verano", "dulce", "salud ocular"]},
    normalize_text("frambuesa"): {"original_name": "Frambuesa", "category_key": "🍎 Frutas", "color": "rojo/rosa", "pni_benefits": ["cetonas de frambuesa (discutido)", "ácido elágico", "antocianinas", "fibra", "vitamina C"], "tags": ["baya", "antioxidante", "baja en azúcar"]},
    normalize_text("mora"): {"original_name": "Mora", "category_key": "🍎 Frutas", "color": "negro/morado oscuro", "pni_benefits": ["antocianinas (muy alta)", "vitamina C", "vitamina K", "fibra"], "tags": ["baya", "antioxidante potente", "verano"]},
    normalize_text("kaki"): {"original_name": "Kaki (Persimón)", "category_key": "🍎 Frutas", "color": "naranja", "pni_benefits": ["vitamina A", "vitamina C", "fibra", "taninos (astringente si no maduro)", "antioxidantes"], "tags": ["otoño", "dulce", "fibra"]},
    normalize_text("chirimoya"): {"original_name": "Chirimoya", "category_key": "🍎 Frutas", "color": "verde (piel), blanco (pulpa)", "pni_benefits": ["vitamina C", "vitamina B6", "fibra", "annonacina"], "tags": ["tropical", "dulce", "textura cremosa"]},
    normalize_text("maracuyá"): {"original_name": "Maracuyá (Fruta de la pasión)", "category_key": "🍎 Frutas", "color": "morado/amarillo (piel), amarillo/naranja (pulpa)", "pni_benefits": ["vitamina C", "vitamina A", "fibra", "flavonoides"], "tags": ["tropical", "ácido/dulce", "aromático"]},
    normalize_text("lichi"): {"original_name": "Lichi", "category_key": "🍎 Frutas", "color": "rojo (piel), blanco translúcido (pulpa)", "pni_benefits": ["vitamina C", "oligopeptidos", "flavonoides"], "tags": ["tropical", "dulce", "aromático"]},
    normalize_text("plátano macho verde"): {"original_name": "Plátano Macho Verde", "category_key": "🍎 Frutas", "color": "verde", "pni_benefits": ["almidón resistente (prebiótico)", "fibra", "potasio", "vitamina B6"], "tags": ["prebiótico", "cocinar antes de comer", "salud intestinal"]},

    # Frutos secos y semillas
    normalize_text("almendra"): {"original_name": "Almendra", "category_key": "🌰 Frutos secos y semillas", "color": "marrón (piel), blanco (interior)", "pni_benefits": ["vitamina E", "grasas saludables (monoinsaturadas)", "fibra", "magnesio", "proteína"], "tags": ["fruto seco", "salud cardiovascular", "piel sana"]},
    normalize_text("nuez"): {"original_name": "Nuez", "category_key": "🌰 Frutos secos y semillas", "color": "marrón claro", "pni_benefits": ["omega-3 (ALA)", "antioxidantes (polifenoles)", "melatonina", "salud cerebral"], "tags": ["fruto seco", "cerebro", "antiinflamatorio"]},
    normalize_text("semilla de chía"): {"original_name": "Semilla de Chía", "category_key": "🌰 Frutos secos y semillas", "color": "gris/negro/blanco", "pni_benefits": ["omega-3 (ALA)", "fibra soluble (mucílago)", "calcio", "proteína"], "tags": ["semilla", "superfood", "gelificante", "salud intestinal"]},
    normalize_text("semilla de lino"): {"original_name": "Semilla de Lino", "category_key": "🌰 Frutos secos y semillas", "color": "marrón/dorado", "pni_benefits": ["omega-3 (ALA)", "lignanos (fitoestrógenos)", "fibra soluble e insoluble"], "tags": ["semilla", "moler para absorber", "salud hormonal", "salud intestinal"]},
    normalize_text("pipa de calabaza"): {"original_name": "Pipa de Calabaza", "category_key": "🌰 Frutos secos y semillas", "color": "verde oscuro", "pni_benefits": ["magnesio", "zinc", "grasas saludables", "cucurbitina (antiparasitario leve)"], "tags": ["semilla", "salud prostática", "magnesio"]},
    normalize_text("anacardo"): {"original_name": "Anacardo", "category_key": "🌰 Frutos secos y semillas", "color": "blanco crema", "pni_benefits": ["magnesio", "cobre", "grasas monoinsaturadas", "triptófano"], "tags": ["fruto seco", "textura cremosa", "versátil"]},
    normalize_text("nuez de brasil"): {"original_name": "Nuez de Brasil", "category_key": "🌰 Frutos secos y semillas", "color": "marrón oscuro (piel), blanco (interior)", "pni_benefits": ["selenio (muy alta - 1-2 al día suficiente)", "grasas saludables", "vitamina E"], "tags": ["fruto seco", "selenio", "tiroides", "moderación"]},
    normalize_text("pistacho"): {"original_name": "Pistacho", "category_key": "🌰 Frutos secos y semillas", "color": "verde/morado (nuez), beige (cáscara)", "pni_benefits": ["vitamina B6", "luteína", "zeaxantina", "grasas saludables", "fibra"], "tags": ["fruto seco", "salud ocular", "colorido"]},
    normalize_text("avellana"): {"original_name": "Avellana", "category_key": "🌰 Frutos secos y semillas", "color": "marrón", "pni_benefits": ["vitamina E", "grasas monoinsaturadas", "manganeso", "folato"], "tags": ["fruto seco", "salud cardiovascular", "sabor dulce"]},
    normalize_text("semilla de girasol"): {"original_name": "Semilla de Girasol (Pipa)", "category_key": "🌰 Frutos secos y semillas", "color": "gris/negro (cáscara), blanco (semilla)", "pni_benefits": ["vitamina E", "selenio", "magnesio", "grasas saludables"], "tags": ["semilla", "vitamina E", "antiinflamatorio"]},
    normalize_text("semilla de sésamo"): {"original_name": "Semilla de Sésamo (Ajonjolí)", "category_key": "🌰 Frutos secos y semillas", "color": "blanco/negro/marrón", "pni_benefits": ["calcio", "hierro", "magnesio", "lignanos (sesamina, sesamolina)"], "tags": ["semilla", "calcio", "tahini", "antioxidante"]},
    normalize_text("semilla de cáñamo"): {"original_name": "Semilla de Cáñamo", "category_key": "🌰 Frutos secos y semillas", "color": "verde/marrón claro", "pni_benefits": ["proteína completa", "omega-3 y omega-6 (ratio ideal)", "fibra", "vitamina E"], "tags": ["semilla", "proteína vegetal", "superfood", "sin CBD/THC psicoactivo"]},
    normalize_text("nuez pecana"): {"original_name": "Nuez Pecana", "category_key": "🌰 Frutos secos y semillas", "color": "marrón", "pni_benefits": ["antioxidantes", "grasas monoinsaturadas", "zinc", "vitamina E"], "tags": ["fruto seco", "dulce", "salud cardiovascular"]},
    normalize_text("nuez de macadamia"): {"original_name": "Nuez de Macadamia", "category_key": "🌰 Frutos secos y semillas", "color": "blanco crema", "pni_benefits": ["grasas monoinsaturadas (ácido palmitoleico)", "fibra", "manganeso"], "tags": ["fruto seco", "rica en grasa saludable", "textura mantecosa", "cara"]},

    # Legumbres
    normalize_text("lenteja"): {"original_name": "Lenteja", "category_key": "🫘 Legumbres", "color": "varios (marrón, verde, roja, negra)", "pni_benefits": ["fibra (soluble e insoluble)", "proteína vegetal", "hierro", "folato", "prebiótico"], "tags": ["versátil", "económica", "rica en nutrientes"]},
    normalize_text("garbanzo"): {"original_name": "Garbanzo", "category_key": "🫘 Legumbres", "color": "beige", "pni_benefits": ["fibra", "proteína vegetal", "manganeso", "folato", "almidón resistente (enfriado)"], "tags": ["versátil", "hummus", "salud intestinal"]},
    normalize_text("judía negra"): {"original_name": "Judía Negra", "category_key": "🫘 Legumbres", "color": "negro", "pni_benefits": ["fibra", "antocianinas", "proteína vegetal", "molibdeno"], "tags": ["antioxidante", "rica en fibra", "cocina latina"]},
    normalize_text("judía pinta"): {"original_name": "Judía Pinta", "category_key": "🫘 Legumbres", "color": "marrón rojizo con motas", "pni_benefits": ["fibra", "proteína vegetal", "folato", "hierro"], "tags": ["tradicional", "rica en fibra"]},
    normalize_text("judía blanca"): {"original_name": "Judía Blanca (Alubia)", "category_key": "🫘 Legumbres", "color": "blanco", "pni_benefits": ["fibra", "proteína vegetal", "fósforo", "molibdeno"], "tags": ["versátil", "textura cremosa"]},
    normalize_text("soja"): {"original_name": "Soja (Haba)", "category_key": "🫘 Legumbres", "color": "amarillo/verde (edamame)", "pni_benefits": ["proteína completa", "isoflavonas (fitoestrógenos)", "fibra", "ácidos grasos omega-3 y omega-6"], "tags": ["proteína vegetal", "versátil (tofu, tempeh, miso, edamame)", "salud hormonal (discutido)"]},
    normalize_text("edamame"): {"original_name": "Edamame (Haba de Soja Verde)", "category_key": "🫘 Legumbres", "color": "verde", "pni_benefits": ["proteína completa", "fibra", "folato", "vitamina K", "isoflavonas"], "tags": ["snack saludable", "japonés", "proteína vegetal"]},
    normalize_text("azuki"): {"original_name": "Azuki (Judía Roja Japonesa)", "category_key": "🫘 Legumbres", "color": "rojo oscuro", "pni_benefits": ["fibra", "proteína vegetal", "molibdeno", "antioxidantes"], "tags": ["dulce natural", "cocina asiática", "postres saludables"]},
    normalize_text("lupino"): {"original_name": "Lupino (Altramuz)", "category_key": "🫘 Legumbres", "color": "amarillo", "pni_benefits": ["proteína muy alta", "fibra", "prebiótico", "aminoácidos esenciales"], "tags": ["aperitivo", "salmuera", "alto en proteína", "legumbre"]},

    # Cereales y pseudocereales
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
    normalize_text("cebada"): {"original_name": "Cebada", "category_key": "🌾 Cereales y pseudocereales", "color": "beige", "pni_benefits": ["betaglucanos (fibra soluble, prebiótico)", "selenio", "magnesio"], "tags": ["cereal con gluten", "prebiótico", "salud cardiovascular"]},

    # Setas y hongos
    normalize_text("champiñón"): {"original_name": "Champiñón (Portobello, Cremini)", "category_key": "🍄 Setas y hongos", "color": "blanco/marrón", "pni_benefits": ["selenio", "vitaminas B (B2, B3, B5)", "betaglucanos", "ergotioneína (antioxidante)"], "tags": ["versátil", "común", "bajo en calorías"]},
    normalize_text("shiitake"): {"original_name": "Shiitake", "category_key": "🍄 Setas y hongos", "color": "marrón", "pni_benefits": ["lentinano (betaglucano inmunomodulador)", "eritadenina (colesterol)", "vitamina D (si expuesto al sol)", "cobre"], "tags": ["medicinal", "sabor umami", "inmunidad"]},
    normalize_text("seta de ostra"): {"original_name": "Seta de Ostra", "category_key": "🍄 Setas y hongos", "color": "varios (gris, rosa, amarillo)", "pni_benefits": ["betaglucanos", "lovastatina natural (colesterol)", "niacina", "antioxidantes"], "tags": ["sabor suave", "textura delicada", "fácil de cultivar"]},
    normalize_text("maitake"): {"original_name": "Maitake (Grifola frondosa)", "category_key": "🍄 Setas y hongos", "color": "marrón/gris", "pni_benefits": ["grifolano (betaglucano)", "factor D-fracción (inmunidad, antitumoral potencial)", "regulación glucosa"], "tags": ["medicinal", "adaptógeno", "inmunidad"]},
    normalize_text("reishi"): {"original_name": "Reishi (Ganoderma lucidum)", "category_key": "🍄 Setas y hongos", "color": "rojo/marrón brillante", "pni_benefits": ["triterpenos (antiinflamatorio, antihistamínico)", "polisacáridos (inmunomodulador)", "adaptógeno", "calmante"], "tags": ["medicinal", "no culinario (amargo)", "extracto/polvo", "longevidad"]},
    normalize_text("enoki"): {"original_name": "Enoki", "category_key": "🍄 Setas y hongos", "color": "blanco", "pni_benefits": ["fibra", "vitaminas B", "antioxidantes", "proflamina (potencial antitumoral)"], "tags": ["largas y finas", "crujientes", "cocina asiática", "sopas"]},
    normalize_text("melena de león"): {"original_name": "Melena de León (Hericium erinaceus)", "category_key": "🍄 Setas y hongos", "color": "blanco", "pni_benefits": ["hericenonas y erinacinas (neuroprotector, estimula NGF)", "salud digestiva", "inmunomodulador"], "tags": ["medicinal", "nootrópico", "salud cerebral", "sabor similar al marisco"]},
    normalize_text("cordyceps"): {"original_name": "Cordyceps", "category_key": "🍄 Setas y hongos", "color": "naranja/marrón", "pni_benefits": ["cordicepina (energía, antiinflamatorio)", "adenosina", "polisacáridos", "rendimiento físico"], "tags": ["medicinal", "adaptógeno", "energizante", "resistencia"]},
    normalize_text("trufa"): {"original_name": "Trufa (negra, blanca)", "category_key": "🍄 Setas y hongos", "color": "negro/blanco/marrón", "pni_benefits": ["antioxidantes", "compuestos fenólicos", "fibra", "minerales (pequeñas cantidades)"], "tags": ["gourmet", "aroma intenso", "condimento caro", "afrodisíaco (popular)"]},

    # Hierbas y especias
    normalize_text("cúrcuma"): {"original_name": "Cúrcuma", "category_key": "🌿 Hierbas y especias", "color": "naranja", "pni_benefits": ["curcumina (potente antiinflamatorio)", "antioxidante", "mejora función endotelial"], "tags": ["especia", "con pimienta negra (para absorción)", "antiinflamatorio", "dorada"]},
    normalize_text("jengibre"): {"original_name": "Jengibre", "category_key": "🌿 Hierbas y especias", "color": "amarillo claro (interior)", "pni_benefits": ["gingerol (antiinflamatorio, antioxidante)", "antinauseas", "mejora digestión", "termogénico"], "tags": ["raiz", "especia", "picante", "digestivo"]},
    normalize_text("perejil"): {"original_name": "Perejil", "category_key": "🌿 Hierbas y especias", "color": "verde", "pni_benefits": ["vitamina K", "vitamina C", "apiol", "miristicina", "apigenina (flavonoide)"], "tags": ["hierba fresca", "decoración", "diurético suave"]},
    normalize_text("cilantro"): {"original_name": "Cilantro (hojas y semillas)", "category_key": "🌿 Hierbas y especias", "color": "verde (hojas), marrón (semillas)", "pni_benefits": ["antioxidantes (hojas)", "quelante suave de metales pesados (hojas)", "digestivo (semillas)", "linalol"], "tags": ["hierba fresca", "especia (semilla)", "sabor distintivo (amor/odio)"]},
    normalize_text("canela"): {"original_name": "Canela (Cassia y Ceylan)", "category_key": "🌿 Hierbas y especias", "color": "marrón", "pni_benefits": ["cinamaldehído (antioxidante, antimicrobiano)", "regulación glucosa", "antiinflamatorio"], "tags": ["especia", "ceylan mejor (menos cumarina)", "dulce", "postres"]},
    normalize_text("orégano"): {"original_name": "Orégano", "category_key": "🌿 Hierbas y especias", "color": "verde", "pni_benefits": ["carvacrol y timol (potentes antimicrobianos)", "antioxidantes", "antiinflamatorio"], "tags": ["hierba", "especia", "cocina mediterránea", "antimicrobiano"]},
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
    normalize_text("anís estrellado"): {"original_name": "Anís Estrellado", "category_key": "🌿 Hierbas y especias", "color": "marrón", "pni_benefits": ["anetol", "ácido shikímico (base para Tamiflu)", "antiviral", "digestivo"], "tags": ["especia", "aromático", "forma de estrella", "cocina asiática", "infusiones"]},
    normalize_text("azafrán"): {"original_name": "Azafrán", "category_key": "🌿 Hierbas y especias", "color": "rojo (estigmas)", "pni_benefits": ["crocina y crocetina (antioxidantes, antidepresivo leve)", "safranal (aroma, antidepresivo leve)", "antiinflamatorio"], "tags": ["especia", "colorante", "aromático", "caro", "estado de ánimo"]},
    normalize_text("laurel"): {"original_name": "Laurel (hoja)", "category_key": "🌿 Hierbas y especias", "color": "verde", "pni_benefits": ["eugenol", "cineol", "digestivo", "antiinflamatorio"], "tags": ["hierba", "aromática", "cocina mediterránea", "guisos"]},
    normalize_text("levadura nutricional"): {"original_name": "Levadura Nutricional", "category_key": "🌿 Hierbas y especias", "color": "amarillo (escamas/polvo)", "pni_benefits": ["vitaminas B (a menudo fortificada con B12)", "proteína completa (inactiva)", "betaglucanos"], "tags": ["condimento", "sabor a queso (umami)", "vegana", "rica en B12 (si fortificada)"]},

    # Alimentos de origen animal
    normalize_text("pollo"): {"original_name": "Pollo (de pasto/ecológico)", "category_key": "🥩 Carnes", "color": "blanco/amarillento", "pni_benefits": ["proteína magra de alta calidad", "vitamina B6", "niacina", "selenio"], "tags": ["ave", "versátil", "fuente de proteína"]},
    normalize_text("salmón"): {"original_name": "Salmón (salvaje)", "category_key": "🐟 Pescados (blancos y azules)", "color": "rosado/rojo", "pni_benefits": ["omega-3 (EPA/DHA)", "vitamina D", "proteína de alta calidad", "astaxantina (antioxidante)"], "tags": ["pescado azul", "antiinflamatorio", "salud cardiovascular", "cerebro"]},
    normalize_text("huevo"): {"original_name": "Huevo (campero/ecológico)", "category_key": "🥚 Huevos y derivados", "color": "varios (cáscara), amarillo/naranja (yema)", "pni_benefits": ["proteína completa", "colina (salud cerebral)", "vitamina D", "luteína", "zeaxantina"], "tags": ["versátil", "rico en nutrientes", "desayuno"]},
    normalize_text("ternera de pasto"): {"original_name": "Ternera de Pasto", "category_key": "🥩 Carnes", "color": "rojo", "pni_benefits": ["proteína de alta calidad", "hierro hemo", "zinc", "vitamina B12", "mejor perfil omega-3/omega-6"], "tags": ["carne roja", "rica en hierro", "omega-3 (si de pasto)"]},
    normalize_text("cordero"): {"original_name": "Cordero (de pasto)", "category_key": "🥩 Carnes", "color": "rojo claro", "pni_benefits": ["proteína", "hierro hemo", "zinc", "vitamina B12", "ácido linoleico conjugado (CLA)"], "tags": ["carne roja", "sabor distintivo"]},
    normalize_text("sardina"): {"original_name": "Sardina", "category_key": "🐟 Pescados (blancos y azules)", "color": "plateado", "pni_benefits": ["omega-3 (EPA/DHA)", "calcio (con espinas)", "vitamina D", "proteína"], "tags": ["pescado azul", "económico", "rico en calcio", "sostenible"]},
    normalize_text("caballa"): {"original_name": "Caballa (Verdel)", "category_key": "🐟 Pescados (blancos y azules)", "color": "plateado/azulado", "pni_benefits": ["omega-3 (EPA/DHA)", "vitamina D", "proteína", "selenio"], "tags": ["pescado azul", "sabor intenso", "antiinflamatorio"]},
    normalize_text("anchoa"): {"original_name": "Anchoa / Boquerón", "category_key": "🐟 Pescados (blancos y azules)", "color": "plateado", "pni_benefits": ["omega-3 (EPA/DHA)", "proteína", "calcio", "vitamina D"], "tags": ["pescado azul", "sabor intenso", "salud ósea"]},
    normalize_text("bacalao"): {"original_name": "Bacalao", "category_key": "🐟 Pescados (blancos y azules)", "color": "blanco", "pni_benefits": ["proteína magra", "vitamina B12", "selenio", "fósforo"], "tags": ["pescado blanco", "versátil", "bajo en grasa"]},
    normalize_text("merluza"): {"original_name": "Merluza", "category_key": "🐟 Pescados (blancos y azules)", "color": "blanco", "pni_benefits": ["proteína magra", "vitaminas B", "potasio", "fósforo"], "tags": ["pescado blanco", "sabor suave", "popular"]},
    normalize_text("hígado de ternera"): {"original_name": "Hígado de Ternera (de pasto)", "category_key": "🧠 Vísceras y casquería", "color": "marrón rojizo", "pni_benefits": ["vitamina A (retinol, muy alta)", "hierro hemo (muy alta)", "vitamina B12", "cobre", "colina"], "tags": ["vísceras", "superalimento nutricional", "consumir con moderación"]},
    normalize_text("corazón de ternera"): {"original_name": "Corazón de Ternera (de pasto)", "category_key": "🧠 Vísceras y casquería", "color": "rojo oscuro", "pni_benefits": ["CoQ10", "proteína", "vitaminas B", "hierro", "selenio"], "tags": ["vísceras", "músculo", "salud cardiovascular", "CoQ10"]},
    normalize_text("mejillón"): {"original_name": "Mejillón", "category_key": "🦐 Mariscos y crustáceos", "color": "negro (concha), naranja/amarillo (carne)", "pni_benefits": ["hierro", "selenio", "vitamina B12", "omega-3", "glucosamina"], "tags": ["marisco", "bivalvo", "rico en hierro", "sostenible"]},
    normalize_text("gamba"): {"original_name": "Gamba / Langostino", "category_key": "🦐 Mariscos y crustáceos", "color": "rosado/gris", "pni_benefits": ["proteína magra", "selenio", "astaxantina", "vitamina B12"], "tags": ["marisco", "crustáceo", "versátil"]},
    normalize_text("pulpo"): {"original_name": "Pulpo", "category_key": "🦐 Mariscos y crustáceos", "color": "marrón/morado (crudo), blanco/rosado (cocido)", "pni_benefits": ["proteína", "hierro", "vitamina B12", "taurina"], "tags": ["marisco", "cefalópodo", "inteligente", "textura firme"]},

    # Probióticos y fermentados
    normalize_text("yogur natural"): {"original_name": "Yogur Natural (sin azúcar, cultivos vivos)", "category_key": "🦠 PROBIÓTICOS", "category_key_alt": "🧀 Lácteos", "color": "blanco", "pni_benefits": ["probióticos (Lactobacillus, Bifidobacterium)", "calcio", "proteína", "vitamina B12"], "tags": ["fermentado", "lácteo", "salud intestinal"]},
    normalize_text("kefir de leche"): {"original_name": "Kefir de Leche", "category_key": "🦠 PROBIÓTICOS", "category_key_alt": "🧀 Lácteos", "color": "blanco", "pni_benefits": ["probióticos (mayor diversidad, levaduras)", "calcio", "vitaminas B", "kefiran"], "tags": ["fermentado", "lácteo", "potente probiótico"]},
    normalize_text("chucrut"): {"original_name": "Chucrut (no pasteurizado)", "category_key": "🦠 PROBIÓTICOS", "color": "verde claro/blanco", "pni_benefits": ["probióticos (Lactobacillus spp.)", "vitamina C", "fibra", "glucosinolatos"], "tags": ["fermentado", "repollo", "salud intestinal", "vitamina K2"]},
    normalize_text("kimchi"): {"original_name": "Kimchi (no pasteurizado)", "category_key": "🦠 PROBIÓTICOS", "color": "rojo/naranja", "pni_benefits": ["probióticos (Lactobacillus spp.)", "fibra", "capsaicina", "ajo", "jengibre"], "tags": ["fermentado", "picante", "coreano", "verduras"]},
    normalize_text("miso"): {"original_name": "Miso (no pasteurizado)", "category_key": "🦠 PROBIÓTICOS", "color": "varios", "pni_benefits": ["probióticos (Aspergillus oryzae)", "isoflavonas", "enzimas digestivas", "vitamina K"], "tags": ["fermentado", "soja", "japonés", "umami"]},
    normalize_text("tempeh"): {"original_name": "Tempeh", "category_key": "🦠 PROBIÓTICOS", "color": "blanco-marrón", "pni_benefits": ["probióticos (Rhizopus oligosporus)", "proteína vegetal completa", "fibra", "isoflavonas"], "tags": ["fermentado", "soja", "textura firme"]},
    normalize_text("kombucha"): {"original_name": "Kombucha (bajo en azúcar)", "category_key": "🦠 PROBIÓTICOS", "color": "varios", "pni_benefits": ["probióticos (SCOBY)", "ácidos orgánicos", "antioxidantes (del té)"], "tags": ["fermentado", "té", "bebida efervescente"]},
    normalize_text("kefir de agua"): {"original_name": "Kefir de Agua", "category_key": "🦠 PROBIÓTICOS", "color": "translúcido/varía", "pni_benefits": ["probióticos (bacterias y levaduras)", "hidratante"], "tags": ["fermentado", "sin lácteos", "bebida efervescente"]},
    normalize_text("vinagre de manzana sin pasteurizar"): {"original_name": "Vinagre de Manzana (con madre)", "category_key": "🦠 PROBIÓTICOS", "color": "ámbar turbio", "pni_benefits": ["ácido acético", "'madre' (bacterias)", "sensibilidad a la insulina (potencial)"], "tags": ["fermentado", "condimento", "no pasteurizado"]},
    normalize_text("encurtidos lactofermentados"): {"original_name": "Encurtidos Lactofermentados (no pasteurizados)", "category_key": "🦠 PROBIÓTICOS", "color": "varios", "pni_benefits": ["probióticos (Lactobacillus spp.)", "fibra"], "tags": ["fermentado", "verduras", "no pasteurizado"]},

    # PREBIÓTICOS (categoría específica y otros ya listados que son buenos prebióticos)
    normalize_text("raíz de achicoria"): {"original_name": "Raíz de Achicoria", "category_key": "🌿 PREBIÓTICOS", "color": "marrón", "pni_benefits": ["inulina (alto contenido)", "fibra prebiótica potente"], "tags": ["prebiótico concentrado", "sustituto de café"]},
    # Ajo, cebolla, puerro, espárrago, plátano (verde), alcachofa, diente de león (raíz), avena, manzana, cebada ya están listados y son prebióticos clave.

    # Lácteos (no principalmente probióticos)
    normalize_text("queso curado"): {"original_name": "Queso Curado (ej. manchego, parmesano)", "category_key": "🧀 Lácteos", "color": "amarillo/blanco", "pni_benefits": ["calcio", "proteína", "vitamina K2 (algunos)"], "tags": ["lácteo", "fermentado (proceso)", "sabor intenso"]},
    normalize_text("queso fresco"): {"original_name": "Queso Fresco (ej. cottage, ricotta)", "category_key": "🧀 Lácteos", "color": "blanco", "pni_benefits": ["proteína (caseína)", "calcio"], "tags": ["lácteo", "suave"]},
    normalize_text("mantequilla ghee"): {"original_name": "Mantequilla Ghee (clarificada)", "category_key": "🧀 Lácteos", "color": "amarillo dorado", "pni_benefits": ["ácido butírico", "vitaminas liposolubles", "sin lactosa/caseína"], "tags": ["grasa láctea", "cocina india", "alto punto de humeo"]},
    normalize_text("leche de cabra"): {"original_name": "Leche de Cabra", "category_key": "🧀 Lácteos", "color": "blanco", "pni_benefits": ["calcio", "proteína", "fácil digestión para algunos"], "tags": ["lácteo", "alternativa leche de vaca"]},
    normalize_text("leche de oveja"): {"original_name": "Leche de Oveja", "category_key": "🧀 Lácteos", "color": "blanco", "pni_benefits": ["calcio (alto)", "proteína (alta)"], "tags": ["lácteo", "rica y cremosa"]},

    # Aceites y Grasas Saludables
    normalize_text("aceite de oliva virgen extra"): {"original_name": "Aceite de Oliva Virgen Extra", "category_key": "🫒 Aceites y grasas saludables", "color": "verde/dorado", "pni_benefits": ["ácido oleico", "polifenoles (oleocantal)", "vitamina E"], "tags": ["grasa saludable", "antiinflamatorio", "dieta mediterránea"]},
    normalize_text("aceite de coco virgen"): {"original_name": "Aceite de Coco Virgen", "category_key": "🫒 Aceites y grasas saludables", "color": "blanco/transparente", "pni_benefits": ["AGCM/MCTs", "ácido láurico"], "tags": ["grasa saludable", "MCT", "energía rápida"]},
    normalize_text("aceite de lino"): {"original_name": "Aceite de Lino", "category_key": "🫒 Aceites y grasas saludables", "color": "amarillo dorado", "pni_benefits": ["omega-3 (ALA, muy alto)", "antiinflamatorio"], "tags": ["grasa saludable", "omega-3 vegetal", "no calentar"]},
    normalize_text("aceituna"): {"original_name": "Aceituna", "category_key": "🫒 Aceites y grasas saludables", "category_key_alt": "🍎 Frutas", "color": "verde/negro/morado", "pni_benefits": ["grasas monoinsaturadas", "vitamina E", "polifenoles"], "tags": ["fruto del olivo", "aperitivo", "grasa saludable"]},

    # Chocolate y Cacao
    normalize_text("cacao puro en polvo"): {"original_name": "Cacao Puro en Polvo (sin azúcar)", "category_key": "🍫 Chocolate y cacao", "color": "marrón oscuro", "pni_benefits": ["flavonoides (epicatequina)", "magnesio", "hierro", "teobromina"], "tags": ["superfood", "antioxidante", "estado de ánimo"]},
    normalize_text("chocolate negro"): {"original_name": "Chocolate Negro (>70% cacao)", "category_key": "🍫 Chocolate y cacao", "color": "marrón oscuro", "pni_benefits": ["flavonoides del cacao", "magnesio", "antioxidantes"], "tags": ["placer saludable", "antioxidante", "moderación"]},

    # Sopas y Caldos
    normalize_text("caldo de huesos"): {"original_name": "Caldo de Huesos", "category_key": "🍲 Sopas y caldos", "color": "variable", "pni_benefits": ["colágeno/gelatina", "aminoácidos (glicina, prolina)", "minerales"], "tags": ["nutritivo", "salud articular", "salud intestinal"]},

    # Bebidas Saludables
    normalize_text("té verde"): {"original_name": "Té Verde", "category_key": "🍵 Bebidas saludables", "color": "verde/amarillo", "pni_benefits": ["EGCG (antioxidante)", "L-teanina (calma, concentración)"], "tags": ["antioxidante", "salud cerebral", "metabolismo"]},
    normalize_text("matcha"): {"original_name": "Matcha", "category_key": "🍵 Bebidas saludables", "color": "verde intenso", "pni_benefits": ["EGCG (muy alto)", "L-teanina (muy alta)", "clorofila"], "tags": ["té verde en polvo", "concentrado", "energía calmada"]},
    normalize_text("té blanco"): {"original_name": "Té Blanco", "category_key": "🍵 Bebidas saludables", "color": "amarillo pálido", "pni_benefits": ["antioxidantes", "menos procesado"], "tags": ["delicado", "antioxidante", "bajo en cafeína"]},
    normalize_text("rooibos"): {"original_name": "Rooibos (Té rojo sudafricano)", "category_key": "🍵 Bebidas saludables", "color": "rojo/marrón", "pni_benefits": ["aspalatina (antioxidante)", "sin cafeína"], "tags": ["infusión", "sin cafeína", "sabor dulce"]},
    normalize_text("infusión de jengibre"): {"original_name": "Infusión de Jengibre", "category_key": "🍵 Bebidas saludables", "color": "amarillo pálido", "pni_benefits": ["gingerol", "antinauseas", "antiinflamatorio"], "tags": ["infusión", "sin cafeína", "medicinal"]},
    normalize_text("infusión de manzanilla"): {"original_name": "Infusión de Manzanilla", "category_key": "🍵 Bebidas saludables", "color": "amarillo claro", "pni_benefits": ["apigenina (calmante)", "antiinflamatorio"], "tags": ["infusión", "sin cafeína", "calmante", "digestiva"]},
    normalize_text("agua de coco"): {"original_name": "Agua de Coco (natural)", "category_key": "🍵 Bebidas saludables", "color": "translúcido", "pni_benefits": ["electrolitos (potasio)", "hidratante"], "tags": ["hidratación", "natural", "refrescante"]},

    # Algas
    normalize_text("alga nori"): {"original_name": "Alga Nori", "category_key": "🌊 Algas", "color": "verde oscuro/negro", "pni_benefits": ["yodo", "fibra", "vitaminas"], "tags": ["alga marina", "sushi", "snacks"]},
    normalize_text("alga kombu"): {"original_name": "Alga Kombu", "category_key": "🌊 Algas", "color": "verde oscuro/negro", "pni_benefits": ["yodo (muy alta)", "ácido glutámico (umami)", "fucoidano"], "tags": ["alga marina", "caldos (dashi)", "ablandar legumbres"]},
    normalize_text("alga wakame"): {"original_name": "Alga Wakame", "category_key": "🌊 Algas", "color": "verde oscuro", "pni_benefits": ["yodo", "fucoxantina", "calcio"], "tags": ["alga marina", "sopa de miso", "ensaladas"]},
    normalize_text("alga espirulina"): {"original_name": "Alga Espirulina", "category_key": "🌊 Algas", "color": "verde azulado", "pni_benefits": ["proteína completa", "hierro", "ficocianina"], "tags": ["microalga", "superfood", "proteína vegetal", "detox"]},
    normalize_text("alga chlorella"): {"original_name": "Alga Chlorella", "category_key": "🌊 Algas", "color": "verde oscuro", "pni_benefits": ["clorofila (muy alta)", "proteína", "CGF (factor crecimiento)"], "tags": ["microalga", "superfood", "detox", "pared celular dura"]},
}

# Asignar category_key_alt para alimentos con múltiples naturalezas
if normalize_text("ajo") in food_details_db: food_details_db[normalize_text("ajo")]["category_key_alt"] = "🌿 Hierbas y especias"
if normalize_text("tomate") in food_details_db: food_details_db[normalize_text("tomate")]["category_key_alt"] = "🍎 Frutas"
if normalize_text("aguacate") in food_details_db: food_details_db[normalize_text("aguacate")]["category_key_alt"] = "🫒 Aceites y grasas saludables"
if normalize_text("guisante") in food_details_db: food_details_db[normalize_text("guisante")]["category_key_alt"] = "🫘 Legumbres"
if normalize_text("judía verde") in food_details_db: food_details_db[normalize_text("judía verde")]["category_key_alt"] = "🫘 Legumbres"
if normalize_text("habas") in food_details_db: food_details_db[normalize_text("habas")]["category_key_alt"] = "🫘 Legumbres"
if normalize_text("edamame") in food_details_db: food_details_db[normalize_text("edamame")]["category_key_alt"] = "🥦 Verduras y hortalizas"

all_selectable_food_items_original_case = sorted(list(set([data["original_name"] for data in food_details_db.values()])))
plant_food_items_original_case = set()
normalized_plant_food_items = set()
normalized_to_original_food_map = {}
probiotic_foods_original_case = set()
normalized_probiotic_foods = set()
prebiotic_foods_original_case = set()
normalized_prebiotic_foods = set()

for norm_name, data in food_details_db.items():
    normalized_to_original_food_map[norm_name] = data["original_name"]
    if data.get("category_key") in PLANT_CATEGORIES_KEYS:
        plant_food_items_original_case.add(data["original_name"])
        normalized_plant_food_items.add(norm_name)
    if data.get("category_key") == "🦠 PROBIÓTICOS":
        probiotic_foods_original_case.add(data["original_name"])
        normalized_probiotic_foods.add(norm_name)
    # Definición de prebióticos
    is_prebiotic_category = data.get("category_key") == "🌿 PREBIÓTICOS"
    has_prebiotic_benefit = "prebiótico" in " ".join(data.get("pni_benefits", [])).lower()
    has_prebiotic_tag = "prebiótico" in " ".join(data.get("tags", [])).lower()
    is_explicit_prebiotic = norm_name in [normalize_text("ajo"), normalize_text("cebolla"), normalize_text("puerro"), normalize_text("alcachofa"), normalize_text("espárrago"), normalize_text("plátano"), normalize_text("avena"), normalize_text("raíz de achicoria"), normalize_text("cebada"), normalize_text("diente de león (hojas)"), normalize_text("topinambur")]

    if is_prebiotic_category or has_prebiotic_benefit or has_prebiotic_tag or is_explicit_prebiotic:
        prebiotic_foods_original_case.add(data["original_name"])
        normalized_prebiotic_foods.add(norm_name)

food_synonyms_map = {
    normalize_text("jitomate"): normalize_text("tomate"), normalize_text("aguacate hass"): normalize_text("aguacate"),
    normalize_text("palta"): normalize_text("aguacate"), normalize_text("plátano canario"): normalize_text("plátano"),
    normalize_text("banana"): normalize_text("plátano"), normalize_text("brocoli"): normalize_text("brócoli"),
    normalize_text("broccoli"): normalize_text("brócoli"), normalize_text("col china"): normalize_text("pak choi"),
    normalize_text("esparragos"): normalize_text("espárrago"), normalize_text("champinon"): normalize_text("champiñón"),
    normalize_text("champinones"): normalize_text("champiñón"), normalize_text("semillas de chia"): normalize_text("semilla de chía"),
    normalize_text("semillas de lino"): normalize_text("semilla de lino"), normalize_text("linaza"): normalize_text("semilla de lino"),
    normalize_text("pipas de calabaza"): normalize_text("pipa de calabaza"), normalize_text("alubia negra"): normalize_text("judía negra"),
    normalize_text("frijol negro"): normalize_text("judía negra"), normalize_text("buckwheat"): normalize_text("trigo sarraceno"),
    normalize_text("alforfon"): normalize_text("trigo sarraceno"), normalize_text("turmeric"): normalize_text("cúrcuma"),
    normalize_text("jengibre fresco"): normalize_text("jengibre"), normalize_text("ginger"): normalize_text("jengibre"),
    normalize_text("yogurt natural"): normalize_text("yogur natural"), normalize_text("sauerkraut"): normalize_text("chucrut"),
    normalize_text("bokchoy"): normalize_text("pak choi"), normalize_text("kale verde"): normalize_text("col rizada"),
    normalize_text("batata"): normalize_text("boniato"), normalize_text("camote"): normalize_text("boniato"),
}

def get_canonical_food_info(input_name):
    if not input_name: return None, None
    normalized_input = normalize_text(input_name)
    canonical_norm_name = food_synonyms_map.get(normalized_input)
    if not canonical_norm_name:
        if normalized_input in food_details_db:
            canonical_norm_name = normalized_input
        else: return None, None
    if canonical_norm_name in food_details_db:
        original_name = food_details_db[canonical_norm_name]["original_name"]
        return canonical_norm_name, original_name
    return None, None

# --- Conectar a Google Sheets ---
@st.cache_resource(ttl=600)
def get_sheet_cached(credentials): # Renombrada para reflejar que está cacheada y evitar confusión con cualquier otra get_sheet
    if not google_services_available or credentials is None:
        st.warning("Los servicios de Google (gspread) no están disponibles. No se puede acceder a la hoja de cálculo.")
        return None
    try:
        client_gspread = gspread.authorize(credentials)
        return client_gspread.open("habitos_microbiota").sheet1
    except gspread.exceptions.SpreadsheetNotFound:
        email_cuenta_servicio = "EMAIL_NO_ENCONTRADO"
        if creds_info_dict and 'client_email' in creds_info_dict: # creds_info_dict debe estar disponible
            email_cuenta_servicio = creds_info_dict['client_email']
        st.error(f"Hoja de cálculo 'habitos_microbiota' no encontrada. Asegúrate de que existe y está compartida con: {email_cuenta_servicio}")
        return None
    except Exception as e:
        st.error(f"No se pudo conectar a Google Sheets: {type(e).__name__} - {e}")
        return None

EXPECTED_HEADERS = ["usuario", "fecha", "comida_original", "comida_normalizada_canonica", "sueno", "ejercicio", "animo", "diversidad_diaria_plantas", "tipo_registro"]

def check_and_create_headers(sheet_obj):
    if sheet_obj is None: return
    try:
        headers = sheet_obj.row_values(1)
        if not headers:
            sheet_obj.append_row(EXPECTED_HEADERS)
            st.info(f"Encabezados creados en la hoja: {', '.join(EXPECTED_HEADERS)}")
        elif headers != EXPECTED_HEADERS:
            st.warning(f"Encabezados existentes ({headers}) no coinciden con los esperados ({EXPECTED_HEADERS}). Podrían ocurrir errores.")
    except gspread.exceptions.APIError as e:
        if 'exceeds grid limits' in str(e).lower() or 'exceeded a limit' in str(e).lower():
            try:
                if not sheet_obj.get_all_values():
                    sheet_obj.append_row(EXPECTED_HEADERS)
                    st.info(f"Encabezados creados en hoja vacía (tras APIError): {', '.join(EXPECTED_HEADERS)}")
            except Exception as inner_e:
                st.error(f"Error al intentar añadir encabezados tras APIError: {inner_e}")
        else:
            st.error(f"Error de API con Google Sheets al verificar encabezados: {e}")
    except Exception as e:
        st.error(f"Error al verificar/crear encabezados en Google Sheets: {e}")

# --- Detección de alimentos con Google Vision AI ---
def detectar_plantas_google_vision(image_file_content): # Renombrado para claridad (solo devuelve plantas)
    if vision_client is None:
        st.warning("El cliente de Google Vision no está inicializado.")
        return []

    image = vision.Image(content=image_file_content)
    try:
        response = vision_client.label_detection(image=image)
        labels = response.label_annotations
    except Exception as e:
        st.error(f"Excepción al llamar a Google Vision API: {e}")
        if hasattr(e, 'details'): st.error(f"Detalles del error de API: {e.details()}")
        return []

    if response.error.message:
        st.error(f"Error devuelto por Google Vision API: {response.error.message}")
        return []
    if not labels:
        st.info("Google Vision API no devolvió ninguna etiqueta para esta imagen.")
        return []

    api_label_to_my_food_map = {
        normalize_text("summer squash"): normalize_text("calabacín"), normalize_text("zucchini"): normalize_text("calabacín"),
        normalize_text("courgette"): normalize_text("calabacín"), normalize_text("cucumber"): normalize_text("pepino"),
        normalize_text("bell pepper"): normalize_text("pimiento rojo"), normalize_text("capsicum"): normalize_text("pimiento rojo"),
        normalize_text("potato"): normalize_text("patata"), normalize_text("tomato"): normalize_text("tomate"),
        normalize_text("apple"): normalize_text("manzana"), normalize_text("banana"): normalize_text("plátano"),
        normalize_text("orange"): normalize_text("naranja"), normalize_text("strawberry"): normalize_text("fresa"),
        normalize_text("blueberry"): normalize_text("arándano"), normalize_text("broccoli"): normalize_text("brócoli"),
        normalize_text("spinach"): normalize_text("espinaca"), normalize_text("carrot"): normalize_text("zanahoria"),
        normalize_text("almond"): normalize_text("almendra"), normalize_text("walnut"): normalize_text("nuez"),
        normalize_text("lentil"): normalize_text("lenteja"), normalize_text("chickpea"): normalize_text("garbanzo"),
        normalize_text("oat"): normalize_text("avena"), normalize_text("quinoa"): normalize_text("quinoa"),
        normalize_text("mushroom"): normalize_text("champiñón"),
    }
    posibles_alimentos_detectados_original_case = set()
    for label in labels:
        nombre_label_norm_api = normalize_text(label.description)
        target_norm_name = api_label_to_my_food_map.get(nombre_label_norm_api)
        if target_norm_name and target_norm_name in food_details_db:
            original_name = food_details_db[target_norm_name]["original_name"]
            posibles_alimentos_detectados_original_case.add(original_name)
            continue
        norm_canonical, original_canonical = get_canonical_food_info(label.description)
        if norm_canonical and original_canonical:
            posibles_alimentos_detectados_original_case.add(original_canonical)

    plantas_detectadas_final = sorted([
        food_name for food_name in list(posibles_alimentos_detectados_original_case)
        if normalize_text(food_name) in normalized_plant_food_items # Filtro para devolver solo plantas
    ])

    if labels and not plantas_detectadas_final:
        raw_api_labels_for_warning = [l.description for l in labels[:5]]
        st.warning(f"Vision API devolvió etiquetas (ej: {', '.join(raw_api_labels_for_warning)}), pero ninguna coincidió con plantas de tu lista.")
    return plantas_detectadas_final

# --- Guardar registro diario ---
def guardar_registro(sheet_obj, user_id, fecha, seleccionados_original_case, sueno, ejercicio, animo):
    if sheet_obj is None:
        st.error("No se puede guardar el registro, la hoja de cálculo no está disponible.")
        return
    fecha_str = fecha.strftime('%Y-%m-%d')
    plantas_dia_normalizadas_canonicas = set()
    todos_alimentos_dia_normalizados_canonicos = set()
    nombres_originales_para_guardar = []

    for item_original_seleccionado in seleccionados_original_case:
        norm_canonical, original_canonical = get_canonical_food_info(item_original_seleccionado)
        if norm_canonical and original_canonical:
            nombres_originales_para_guardar.append(original_canonical)
            todos_alimentos_dia_normalizados_canonicos.add(norm_canonical)
            if norm_canonical in normalized_plant_food_items:
                plantas_dia_normalizadas_canonicas.add(norm_canonical)
        else:
            nombres_originales_para_guardar.append(item_original_seleccionado) # Guardar tal cual si no reconocido
            st.warning(f"Alimento '{item_original_seleccionado}' no reconocido, se guardará pero no contará para diversidad de plantas.")

    diversidad_diaria_plantas = len(plantas_dia_normalizadas_canonicas)
    comida_original_str = ", ".join(sorted(list(set(nombres_originales_para_guardar))))
    comida_normalizada_str = ", ".join(sorted(list(todos_alimentos_dia_normalizados_canonicos)))

    try:
        sheet_obj.append_row([
            user_id, fecha_str, comida_original_str, comida_normalizada_str,
            sueno, ejercicio, animo, diversidad_diaria_plantas, "registro_diario"
        ])
        st.success(f"✅ Registro para {user_id} guardado: {diversidad_diaria_plantas} plantas distintas hoy.")
    except Exception as e:
        st.error(f"Error al guardar el registro en Google Sheets: {e}")

# --- Guardar resumen semanal ---
def calcular_y_guardar_resumen_semanal_usuario(sheet_obj, user_id, fecha_referencia_lunes):
    if sheet_obj is None: return
    st.write(f"Calculando resumen semanal para {user_id} para la semana anterior al {fecha_referencia_lunes.strftime('%Y-%m-%d')}")
    try:
        all_records_list_of_dict = sheet_obj.get_all_records(expected_headers=EXPECTED_HEADERS)
    except Exception as e:
        st.error(f"No se pudieron obtener todos los registros para el resumen semanal: {e}")
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
        st.info(f"No hay registros para {user_id} para generar resumen semanal.")
        return

    try:
        df_user["fecha"] = pd.to_datetime(df_user["fecha"], errors='coerce').dt.date
        df_user.dropna(subset=["fecha"], inplace=True)
    except Exception as e:
        st.error(f"Error convirtiendo fechas para el resumen: {e}")
        return
            
    fin_semana_a_resumir = fecha_referencia_lunes - timedelta(days=1)
    inicio_semana_a_resumir = fin_semana_a_resumir - timedelta(days=6)

    semana_df = df_user[
        (df_user["fecha"] >= inicio_semana_a_resumir) &
        (df_user["fecha"] <= fin_semana_a_resumir) &
        (df_user["tipo_registro"] == "registro_diario")
    ].copy()

    diversidad_semanal_plantas = 0
    if semana_df.empty:
        st.info(f"No hay registros diarios para {user_id} en la semana de {inicio_semana_a_resumir.strftime('%Y-%m-%d')} a {fin_semana_a_resumir.strftime('%Y-%m-%d')}.")
    else:
        plantas_semana_normalizadas_canonicas = set()
        for _, row in semana_df.iterrows():
            comida_registrada_norm = str(row.get("comida_normalizada_canonica", "")).split(",")
            for item_norm_canonico in comida_registrada_norm:
                item_norm_canonico_trimmed = item_norm_canonico.strip()
                if item_norm_canonico_trimmed and item_norm_canonico_trimmed in normalized_plant_food_items:
                    plantas_semana_normalizadas_canonicas.add(item_norm_canonico_trimmed)
        diversidad_semanal_plantas = len(plantas_semana_normalizadas_canonicas)

    fecha_resumen_str = fecha_referencia_lunes.strftime('%Y-%m-%d')
    resumen_existente = df_user[
        (df_user["fecha"] == fecha_referencia_lunes) &
        (df_user["tipo_registro"] == "resumen_semanal")
    ]

    if resumen_existente.empty:
        try:
            sheet_obj.append_row([
                user_id, fecha_resumen_str, 
                f"Resumen semana {inicio_semana_a_resumir.strftime('%Y-%m-%d')} - {fin_semana_a_resumir.strftime('%Y-%m-%d')}", 
                "", "", "", "", diversidad_semanal_plantas, "resumen_semanal"
            ])
            st.success(f"📝 Resumen semanal para {user_id} guardado: {diversidad_semanal_plantas} plantas.")
        except Exception as e:
            st.error(f"Error al guardar el resumen semanal en Google Sheets: {e}")
    else:
        st.info(f"Ya existe un resumen para {user_id} en la fecha {fecha_resumen_str}.")

# --- Sugerencias Inteligentes ---
def get_smart_suggestions(plantas_consumidas_norm_canonicas_set, num_sugerencias=5):
    if not food_details_db or not normalized_plant_food_items:
        return ["Error: Base de datos de alimentos no cargada."]
    plantas_disponibles_norm = normalized_plant_food_items - plantas_consumidas_norm_canonicas_set
    if not plantas_disponibles_norm: return []
    
    plantas_disponibles_lista_norm = list(plantas_disponibles_norm)
    random.shuffle(plantas_disponibles_lista_norm)
    sugerencias = []
    for norm_name in plantas_disponibles_lista_norm:
        if len(sugerencias) < num_sugerencias:
            original_name = food_details_db[norm_name]["original_name"]
            sugerencias.append(original_name)
        else: break
    return sugerencias

# --- Visualización y análisis ---
def mostrar_registros_y_analisis(df_user, current_user_id):
    if df_user.empty:
        st.info(f"Aún no hay registros para el usuario {current_user_id}.")
        return

    df_display = df_user[df_user['tipo_registro'] == 'registro_diario'].copy()
    if df_display.empty:
        st.info(f"Aún no hay registros de tipo 'registro_diario' para {current_user_id} para mostrar detalles.")
        return
            
    df_display["fecha"] = pd.to_datetime(df_display["fecha"]).dt.date
    df_display["diversidad_diaria_plantas"] = pd.to_numeric(df_display["diversidad_diaria_plantas"], errors='coerce').fillna(0)
    df_display["sueno"] = pd.to_numeric(df_display["sueno"], errors='coerce')
    df_display["animo"] = pd.to_numeric(df_display["animo"], errors='coerce')

    st.markdown("---"); st.subheader(f"📅 Tus vegetales únicos por día ({current_user_id})")
    for fecha_registro, grupo in df_display.sort_values("fecha", ascending=False).groupby("fecha"):
        plantas_originales_dia = set()
        for comida_norm_str in grupo["comida_normalizada_canonica"].dropna():
            items_norm_canonicos = [i.strip() for i in comida_norm_str.split(",") if i.strip()]
            for item_norm_c in items_norm_canonicos:
                if item_norm_c in normalized_plant_food_items:
                    original_name = food_details_db.get(item_norm_c, {}).get("original_name", item_norm_c)
                    plantas_originales_dia.add(original_name)
        if plantas_originales_dia:
            st.markdown(f"📆 **{fecha_registro.strftime('%Y-%m-%d')}**: {len(plantas_originales_dia)} planta(s): {', '.join(sorted(list(plantas_originales_dia)))}")
        else:
            st.markdown(f"📆 **{fecha_registro.strftime('%Y-%m-%d')}**: 0 plantas.")

    st.markdown("---"); st.subheader(f"🌿 Tu diversidad vegetal esta semana ({current_user_id})")
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
            st.info("¡Parece que no quedan más plantas por sugerir o ya las has probado todas!")
    elif progreso >= 30:
        st.success("🎉 ¡Felicidades! Ya has alcanzado o superado las 30 plantas distintas esta semana.")

    if not df_display.empty:
        st.subheader("📊 Gráfico: Ánimo vs. Sueño")
        fig = px.scatter(df_display.dropna(subset=['sueno', 'animo']), x="sueno", y="animo", 
                           hover_data=["fecha", "comida_original"], title="Relación Ánimo y Sueño")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📈 Diversidad de plantas por día")
        df_plot_line = df_display.sort_values(by="fecha")
        fig2 = px.line(df_plot_line, x="fecha", y="diversidad_diaria_plantas", title="Evolución de la Diversidad Diaria de Plantas")
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("🤖 Predicción de Ánimo (ML)")
        df_ml = df_display[['sueno', 'animo', 'diversidad_diaria_plantas']].dropna().copy()
        if len(df_ml) > 3:
            X = df_ml[["sueno", "diversidad_diaria_plantas"]]
            y = df_ml["animo"]
            try:
                model = LinearRegression().fit(X, y)
                st.markdown(f"Modelo (beta): Sueño: {model.coef_[0]:.2f}, Diversidad: {model.coef_[1]:.2f}, Intercepto: {model.intercept_:.2f}")
                st.caption("Simplificación. El ánimo depende de muchos factores.")
            except Exception as e: st.warning(f"No se pudo entrenar el modelo de regresión: {e}")
        else: st.info("No hay suficientes datos (>3 registros con sueño, ánimo y diversidad) para el modelo de ánimo.")

        st.subheader("👥 Clusters de Días")
        features_cluster = df_display[["diversidad_diaria_plantas", "sueno", "animo"]].dropna().copy()
        if len(features_cluster) >= 3:
            n_clusters_kmeans = min(3, len(features_cluster))
            if n_clusters_kmeans < 2: n_clusters_kmeans = 2
            if len(features_cluster) >= n_clusters_kmeans :
                try:
                    kmeans = KMeans(n_clusters=n_clusters_kmeans, random_state=42, n_init='auto').fit(features_cluster)
                    df_display_clustered = df_display.loc[features_cluster.index].copy()
                    df_display_clustered['cluster'] = kmeans.labels_.astype(str) # Color como string
                    fig3 = px.scatter(df_display_clustered.dropna(subset=['cluster']), x="diversidad_diaria_plant
