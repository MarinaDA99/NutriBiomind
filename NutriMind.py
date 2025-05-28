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
from unidecode import unidecode # NUEVO: Para quitar acentos
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
    # Verduras y Hortalizas
    normalize_text("acelga"): {"original_name": "Acelga", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["vitamina K", "magnesio"], "tags": ["hoja verde"]},
    normalize_text("apio"): {"original_name": "Apio", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["fibra", "antioxidantes"], "tags": ["crujiente"]},
    normalize_text("berenjena"): {"original_name": "Berenjena", "category_key": "🥦 Verduras y hortalizas", "color": "morado", "pni_benefits": ["nasunina", "fibra"], "tags": ["solanacea"]},
    normalize_text("brócoli"): {"original_name": "Brócoli", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["sulforafano", "fibra", "vitamina C"], "tags": ["cruciferas"]},
    normalize_text("calabacín"): {"original_name": "Calabacín", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["bajo en calorías", "vitamina A"], "tags": ["cucurbitacea"]},
    normalize_text("calabaza"): {"original_name": "Calabaza", "category_key": "🥦 Verduras y hortalizas", "color": "naranja", "pni_benefits": ["betacaroteno", "fibra"], "tags": ["cucurbitacea", "otoño"]},
    normalize_text("cebolla"): {"original_name": "Cebolla", "category_key": "🥦 Verduras y hortalizas", "color": "blanco", "pni_benefits": ["quercetina", "prebiótico (inulina)"], "tags": ["aliacea"]},
    normalize_text("coliflor"): {"original_name": "Coliflor", "category_key": "🥦 Verduras y hortalizas", "color": "blanco", "pni_benefits": ["glucosinolatos", "fibra"], "tags": ["cruciferas"]},
    normalize_text("espinaca"): {"original_name": "Espinaca", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["hierro", "folato", "vitamina K"], "tags": ["hoja verde"]},
    normalize_text("pimiento rojo"): {"original_name": "Pimiento Rojo", "category_key": "🥦 Verduras y hortalizas", "color": "rojo", "pni_benefits": ["vitamina C", "capsantina"], "tags": ["solanacea", "dulce"]},
    normalize_text("puerro"): {"original_name": "Puerro", "category_key": "🥦 Verduras y hortalizas", "color": "verde claro", "pni_benefits": ["prebiótico (inulina)", "kaempferol"], "tags": ["aliacea"]},
    normalize_text("tomate"): {"original_name": "Tomate", "category_key": "🥦 Verduras y hortalizas", "color": "rojo", "pni_benefits": ["licopeno", "vitamina C"], "tags": ["solanacea", "fruta botanicamente"]}, # Botánicamente fruta, culinariamente verdura
    normalize_text("zanahoria"): {"original_name": "Zanahoria", "category_key": "🥦 Verduras y hortalizas", "color": "naranja", "pni_benefits": ["betacaroteno", "fibra"], "tags": ["raiz"]},
    normalize_text("ajo"): {"original_name": "Ajo", "category_key": "🥦 Verduras y hortalizas", "color": "blanco", "pni_benefits": ["alicina", "prebiótico"], "tags": ["aliacea", "especias"]}, # Podría estar en especias también
    normalize_text("alcachofa"): {"original_name": "Alcachofa", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["cinarina", "fibra prebiótica"], "tags": ["flor comestible"]},
    normalize_text("espárrago"): {"original_name": "Espárrago", "category_key": "🥦 Verduras y hortalizas", "color": "verde", "pni_benefits": ["asparagina", "prebiótico (inulina)", "folato"], "tags": []},


    # Frutas
    normalize_text("manzana"): {"original_name": "Manzana", "category_key": "🍎 Frutas", "color": "varios", "pni_benefits": ["pectina", "quercetina", "antioxidantes"], "tags": ["con piel"]},
    normalize_text("plátano"): {"original_name": "Plátano", "category_key": "🍎 Frutas", "color": "amarillo", "pni_benefits": ["potasio", "vitamina B6", "prebiótico (si no muy maduro)"], "tags": []},
    normalize_text("naranja"): {"original_name": "Naranja", "category_key": "🍎 Frutas", "color": "naranja", "pni_benefits": ["vitamina C", "hesperidina"], "tags": ["cítrico"]},
    normalize_text("fresa"): {"original_name": "Fresa", "category_key": "🍎 Frutas", "color": "rojo", "pni_benefits": ["antocianinas", "vitamina C"], "tags": ["baya"]},
    normalize_text("arándano"): {"original_name": "Arándano", "category_key": "🍎 Frutas", "color": "azul", "pni_benefits": ["antocianinas", "antioxidantes potentes"], "tags": ["baya", "superfood"]},
    normalize_text("kiwi"): {"original_name": "Kiwi", "category_key": "🍎 Frutas", "color": "verde", "pni_benefits": ["vitamina C", "actinidina", "fibra"], "tags": []},
    normalize_text("mango"): {"original_name": "Mango", "category_key": "🍎 Frutas", "color": "naranja", "pni_benefits": ["vitamina A", "vitamina C", "mangiferina"], "tags": ["tropical"]},
    normalize_text("aguacate"): {"original_name": "Aguacate", "category_key": "🍎 Frutas", "color": "verde", "pni_benefits": ["grasas saludables", "fibra", "potasio"], "tags": ["grasa monoinsaturada"]}, # Botánicamente fruta

    # Frutos secos y semillas
    normalize_text("almendra"): {"original_name": "Almendra", "category_key": "🌰 Frutos secos y semillas", "color": "marrón", "pni_benefits": ["vitamina E", "grasas saludables", "fibra"], "tags": ["fruto seco"]},
    normalize_text("nuez"): {"original_name": "Nuez", "category_key": "🌰 Frutos secos y semillas", "color": "marrón", "pni_benefits": ["omega-3 (ALA)", "antioxidantes"], "tags": ["fruto seco", "cerebro"]},
    normalize_text("semilla de chía"): {"original_name": "Semilla de Chía", "category_key": "🌰 Frutos secos y semillas", "color": "gris", "pni_benefits": ["omega-3", "fibra soluble", "calcio"], "tags": ["semilla", "superfood"]},
    normalize_text("semilla de lino"): {"original_name": "Semilla de Lino", "category_key": "🌰 Frutos secos y semillas", "color": "marrón", "pni_benefits": ["omega-3", "lignanos", "fibra"], "tags": ["semilla", "moler para absorber"]},
    normalize_text("pipa de calabaza"): {"original_name": "Pipa de Calabaza", "category_key": "🌰 Frutos secos y semillas", "color": "verde oscuro", "pni_benefits": ["magnesio", "zinc", "grasas saludables"], "tags": ["semilla"]},

    # Legumbres
    normalize_text("lenteja"): {"original_name": "Lenteja", "category_key": "🫘 Legumbres", "color": "varios", "pni_benefits": ["fibra", "proteína vegetal", "hierro"], "tags": []},
    normalize_text("garbanzo"): {"original_name": "Garbanzo", "category_key": "🫘 Legumbres", "color": "beige", "pni_benefits": ["fibra", "proteína vegetal", "manganeso"], "tags": []},
    normalize_text("judía negra"): {"original_name": "Judía Negra", "category_key": "🫘 Legumbres", "color": "negro", "pni_benefits": ["fibra", "antocianinas", "proteína vegetal"], "tags": []},

    # Cereales y pseudocereales
    normalize_text("avena"): {"original_name": "Avena", "category_key": "🌾 Cereales y pseudocereales", "color": "beige", "pni_benefits": ["betaglucanos (fibra soluble)", "prebiótico"], "tags": ["integral", "desayuno"]},
    normalize_text("quinoa"): {"original_name": "Quinoa", "category_key": "🌾 Cereales y pseudocereales", "color": "varios", "pni_benefits": ["proteína completa", "fibra", "hierro"], "tags": ["pseudocereal", "sin gluten"]},
    normalize_text("arroz integral"): {"original_name": "Arroz Integral", "category_key": "🌾 Cereales y pseudocereales", "color": "marrón", "pni_benefits": ["fibra", "magnesio", "selenio"], "tags": ["integral"]},
    normalize_text("trigo sarraceno"): {"original_name": "Trigo Sarraceno", "category_key": "🌾 Cereales y pseudocereales", "color": "marrón", "pni_benefits": ["rutina", "magnesio", "fibra"], "tags": ["pseudocereal", "sin gluten", "alforfón"]},


    # Setas y hongos
    normalize_text("champiñón"): {"original_name": "Champiñón", "category_key": "🍄 Setas y hongos", "color": "blanco", "pni_benefits": ["selenio", "vitaminas B", "betaglucanos"], "tags": []},
    normalize_text("shiitake"): {"original_name": "Shiitake", "category_key": "🍄 Setas y hongos", "color": "marrón", "pni_benefits": ["lentinano", "eritadenina", "inmunomodulador"], "tags": ["medicinal"]},

    # Hierbas y especias
    normalize_text("cúrcuma"): {"original_name": "Cúrcuma", "category_key": "🌿 Hierbas y especias", "color": "naranja", "pni_benefits": ["curcumina", "antiinflamatorio"], "tags": ["especia", "con pimienta negra"]},
    normalize_text("jengibre"): {"original_name": "Jengibre", "category_key": "🌿 Hierbas y especias", "color": "amarillo claro", "pni_benefits": ["gingerol", "antiinflamatorio", "antinauseas"], "tags": ["raiz", "especia"]},
    normalize_text("perejil"): {"original_name": "Perejil", "category_key": "🌿 Hierbas y especias", "color": "verde", "pni_benefits": ["vitamina K", "apiol"], "tags": ["hierba fresca"]},
    normalize_text("cilantro"): {"original_name": "Cilantro", "category_key": "🌿 Hierbas y especias", "color": "verde", "pni_benefits": ["antioxidantes", "quelante suave"], "tags": ["hierba fresca"]},
    normalize_text("canela"): {"original_name": "Canela", "category_key": "🌿 Hierbas y especias", "color": "marrón", "pni_benefits": ["regulación glucosa", "antioxidante"], "tags": ["especia", "ceylan mejor"]},
    normalize_text("orégano"): {"original_name": "Orégano", "category_key": "🌿 Hierbas y especias", "color": "verde", "pni_benefits": ["carvacrol", "timol", "antimicrobiano"], "tags": ["hierba", "especia"]},


    # Alimentos de origen animal (ejemplos)
    normalize_text("pollo"): {"original_name": "Pollo", "category_key": "🥩 Carnes", "color": "blanco", "pni_benefits": ["proteína magra", "vitamina B6"], "tags": ["ave"]},
    normalize_text("salmón"): {"original_name": "Salmón", "category_key": "🐟 Pescados (blancos y azules)", "color": "rosado", "pni_benefits": ["omega-3 (EPA/DHA)", "vitamina D", "proteína"], "tags": ["pescado azul", "antiinflamatorio"]},
    normalize_text("huevo"): {"original_name": "Huevo", "category_key": "🥚 Huevos y derivados", "color": "varios", "pni_benefits": ["proteína completa", "colina", "vitamina D"], "tags": ["versátil"]},
    normalize_text("yogur natural"): {"original_name": "Yogur Natural", "category_key": "🦠 PROBIÓTICOS", "color": "blanco", "pni_benefits": ["probióticos", "calcio", "proteína"], "tags": ["fermentado", "lacteo"]}, # También en "🧀 Lácteos"
    normalize_text("kefir de leche"): {"original_name": "Kefir de Leche", "category_key": "🦠 PROBIÓTICOS", "color": "blanco", "pni_benefits": ["probióticos (mayor diversidad)", "calcio"], "tags": ["fermentado", "lacteo"]}, # También en "🧀 Lácteos"
    normalize_text("chucrut"): {"original_name": "Chucrut", "category_key": "🦠 PROBIÓTICOS", "color": "verde claro", "pni_benefits": ["probióticos", "vitamina C", "fibra"], "tags": ["fermentado", "repollo", "no pasteurizado"]},
    normalize_text("kimchi"): {"original_name": "Kimchi", "category_key": "🦠 PROBIÓTICOS", "color": "rojo", "pni_benefits": ["probióticos", "fibra", "capsaicina"], "tags": ["fermentado", "picante", "coreano"]},
    normalize_text("miso"): {"original_name": "Miso", "category_key": "🦠 PROBIÓTICOS", "color": "varios", "pni_benefits": ["probióticos", "isoflavonas", "enzimas"], "tags": ["fermentado", "soja", "japonés"]},
    normalize_text("tempeh"): {"original_name": "Tempeh", "category_key": "🦠 PROBIÓTICOS", "color": "blanco-marron", "pni_benefits": ["probióticos", "proteína vegetal completa", "fibra"], "tags": ["fermentado", "soja"]},
    normalize_text("kombucha"): {"original_name": "Kombucha", "category_key": "🦠 PROBIÓTICOS", "color": "varios", "pni_benefits": ["probióticos (levaduras y bacterias)", "ácidos orgánicos"], "tags": ["fermentado", "té", "bajo en azúcar"]},

    # Categorías que existían antes, rellenar según necesidad (no cuentan para las 30 plantas)
    # "🥩 Carnes", "🐟 Pescados (blancos y azules)", "🦐 Mariscos y crustáceos",
    # "🥚 Huevos y derivados", "🧀 Lácteos", "🧠 Vísceras y casquería",
    # "🧴 Productos fermentados animales", "🐖 Embutidos y curados",
    # "🪳 Insectos comestibles", "🍖 Otros productos animales"
    # "🌿 PREBIÓTICOS" (muchos ya están en verduras/frutas, pero se pueden duplicar aquí si se quiere destacar su función prebiótica)
    # Ejemplo para PREBIÓTICOS si quieres que aparezcan como categoría seleccionable aparte:
    normalize_text("raíz de achicoria"): {"original_name": "Raíz de Achicoria", "category_key": "🌿 PREBIÓTICOS", "color": "marrón", "pni_benefits": ["inulina (alto contenido)", "fibra prebiótica"], "tags": ["prebiótico concentrado"]},
}
# Ejemplo: Añadir el yogur a la categoría Lácteos también si se desea listarlo allí
if normalize_text("yogur natural") in food_details_db:
     food_details_db[normalize_text("yogur natural")]["category_key_alt"] = "🧀 Lácteos"


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

