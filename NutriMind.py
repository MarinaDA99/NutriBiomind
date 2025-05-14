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

# El resto de tu código que depende de creds_gspread y vision_client
# debe verificar si son None o si google_services_available es False antes de usarlos.
# --- Definiciones de Categorías y Alimentos ---
categorias = {
    "🥦 Verduras y hortalizas": ["acelga", "apio", "berenjena", "brócoli", "calabacín", "calabaza", "cardo", "cebolla", "cebolleta", "col blanca", "col de Bruselas", "col lombarda", "col rizada (kale)", "coliflor", "endibia", "escarola", "espárrago", "espinaca", "hinojo", "judía verde", "lechuga romana", "lechuga iceberg", "nabo", "pepino", "pimiento rojo", "pimiento verde", "puerro", "rábano", "remolacha", "tomate", "zanahoria", "alcachofa", "chirivía", "boniato (batata)", "patata", "ñame", "taro", "malanga", "yuca", "okra", "pak choi", "berza", "acedera", "mostaza verde", "diente de león (hojas)", "berro", "canónigos", "mizuna", "tatsoi", "escarola rizada"],
    "🍎 Frutas": ["manzana", "pera", "plátano", "naranja", "mandarina", "kiwi", "uva", "granada", "fresa", "frambuesa", "mora", "arándano", "cereza", "melocotón", "albaricoque", "ciruela", "mango", "papaya", "piña", "melón", "sandía", "higo", "caqui", "lichi", "maracuyá", "guayaba", "chirimoya", "carambola", "níspero", "pomelo", "lima", "limón", "coco", "aguacate", "tomate cherry", "grosella", "zarzamora", "mandarino", "plátano macho", "dátil"],
    "🌰 Frutos secos y semillas": ["almendra", "avellana", "nuez", "nuez de Brasil", "nuez de macadamia", "pistacho", "anacardo", "cacahuete", "pipa de girasol", "pipa de calabaza", "semilla de sésamo", "semilla de chía", "semilla de lino", "semilla de amapola", "semilla de cáñamo", "semilla de alcaravea", "semilla de hinojo", "semilla de mostaza", "semilla de albahaca", "semilla de comino", "semilla de coriandro", "semilla de anís", "semilla de cardamomo", "semilla de nigella", "semilla de fenogreco", "semilla de ajonjolí negro", "semilla de calabaza tostada", "semilla de girasol tostada", "semilla de lino dorado", "semilla de chía blanca"],
    "🫘 Legumbres": ["lenteja", "garbanzo", "judía blanca", "judía roja", "judía negra", "habas", "guisantes", "soja", "azuki", "mungo", "lupino", "alubia pinta", "alubia canela", "alubia carilla", "alubia de Lima", "alubia de riñón", "alubia moteada", "alubia escarlata", "alubia borlotti", "alubia navy"],
    "🌾 Cereales y pseudocereales": ["trigo integral", "avena", "cebada", "centeno", "arroz integral", "maíz", "quinoa", "amaranto", "mijo", "teff", "alforfón (trigo sarraceno)", "espelta", "kamut", "sorgo", "farro", "freekeh", "trigo bulgur", "trigo candeal", "trigo sarraceno tostado (kasha)", "arroz salvaje"],
    "🍄 Setas y hongos": ["champiñón", "shiitake", "maitake", "gírgola (ostra)", "enoki", "portobello", "rebozuelo", "trompeta de la muerte", "seta de cardo", "seta de chopo", "seta de pie azul", "seta de pino", "seta de haya", "seta de álamo", "seta de abedul", "seta de roble", "seta de caoba", "seta de castaño", "seta de aliso", "seta de fresno"],
    "🌿 Hierbas y especias": ["albahaca", "perejil", "cilantro", "menta", "hierbabuena", "romero", "tomillo", "orégano", "salvia", "estragón", "eneldo", "cebollino", "laurel", "mejorana", "ajedrea", "hinojo (hojas)", "lemongrass", "curry (hojas)", "hoja de lima kaffir", "hoja de laurel indio"],
    "🥩 Carnes": ["ternera", "vaca", "buey", "cordero", "cabrito", "cerdo", "jabalí", "conejo", "liebre", "caballo", "asno", "canguro", "bisonte", "yak", "reno", "camello", "ñu", "antílope", "oveja", "chivo"],
    "🐟 Pescados (blancos y azules)": ["merluza", "bacalao", "lubina", "dorada", "rape", "lenguado", "rodaballo", "abadejo", "cabracho", "besugo", "sardina", "anchoa", "atún", "bonito", "caballa", "jurel", "salmón", "arenque", "trucha", "pez espada", "marrajo", "palometa", "sábalo", "mujol", "chicharro"],
    "🦐 Mariscos y crustáceos": ["camarón", "gamba", "langostino", "langosta", "cigala", "cangrejo", "nécora", "buey de mar", "percebe", "mejillón", "almeja", "berberecho", "navaja", "vieira", "ostras", "coquina", "caracol de mar", "zamburiña", "sepia", "pulpo", "calamar", "chipirón"],
    "🥚 Huevos y derivados": ["huevo de gallina", "huevo de codorniz", "huevo de pato", "huevo de oca", "huevo de avestruz", "clara de huevo", "yema de huevo", "huevo deshidratado", "huevo líquido pasteurizado", "huevo cocido", "huevo escalfado", "huevo revuelto", "tortilla francesa", "huevos rellenos", "mayonesa casera"],
    "🧀 Lácteos": ["leche de vaca", "leche de cabra", "leche de oveja", "leche evaporada", "leche condensada", "leche en polvo", "nata", "mantequilla", "manteca", "queso fresco", "queso curado", "queso semicurado", "queso azul", "queso de cabra", "queso de oveja", "requesón", "ricotta", "mascarpone", "burrata", "parmesano", "grana padano", "mozzarella", "cheddar", "gouda", "emmental", "camembert", "brie", "yogur natural", "yogur griego", "yogur bebible", "kefir de leche"],
    "🧠 Vísceras y casquería": ["hígado de ternera", "hígado de pollo", "riñón", "sesos", "mollejas", "corazón", "lengua", "callos", "ubre", "morros", "manitas de cerdo", "sangre coagulada", "panza", "tuétano", "pata de cordero", "estómago (mondongo)", "tripa natural", "criadillas", "caracoles (terrestres)"],
    "🧴 Productos fermentados animales": ["yogur", "kefir", "queso azul", "roquefort", "queso camembert", "miso con caldo dashi", "salsa de pescado", "garum", "natto con huevo", "lassi", "suero de leche fermentado", "amasake"],
    "🐖 Embutidos y curados": ["jamón serrano", "jamón ibérico", "lomo embuchado", "chorizo", "salchichón", "fuet", "morcilla", "butifarra", "sobrasada", "cecina", "lacón", "panceta curada", "tocino", "mortadela", "salami", "longaniza", "coppa", "bresaola", "pastrami", "speck", "kielbasa", "andouille", "chistorra"],
    "🪳 Insectos comestibles": ["chapulines", "gusanos de maguey", "hormigas culonas", "escarabajos", "grillos", "langostas (insectos)", "larvas de escarabajo", "saltamontes", "gusanos de seda", "termitas", "avispas (crisálidas)"],
    "🍖 Otros productos animales": ["caldo de huesos", "gelatina (de origen animal)", "grasa de pato", "grasa de cerdo (manteca)", "sebo de vaca", "caviar", "huevas de pescado", "leche materna (humana)", "cuajo animal"],
    "🦠 PROBIÓTICOS": ["yogur natural", "yogur griego", "yogur de cabra", "kefir de leche", "kefir de agua", "miso", "tempeh", "natto", "chucrut (fermentado en crudo)", "kimchi", "kombucha", "vinagre de manzana sin filtrar (con madre)"], # Resumido para brevedad
    "🌿 PREBIÓTICOS": ["ajo crudo", "cebolla cruda", "puerro", "alcachofa", "espárrago", "plátano verde", "avena", "manzana con piel", "semillas de lino molidas", "cacao puro", "raíz de achicoria"] # Resumido para brevedad
}

# NUEVO: Función para normalizar texto (quitar acentos y a minúsculas)
def normalize_text(text):
    if text is None:
        return ""
    return unidecode(str(text)).lower()

# NUEVO: Definición de qué categorías cuentan como "plantas" para la diversidad
PLANT_CATEGORIES_KEYS = [
    "🥦 Verduras y hortalizas", "🍎 Frutas", "🌰 Frutos secos y semillas",
    "🫘 Legumbres", "🌾 Cereales y pseudocereales", "🍄 Setas y hongos", "🌿 Hierbas y especias"
]

# NUEVO: Alimentos que cuentan para la diversidad de plantas (nombres originales)
plant_food_items_original_case = set()
for key in PLANT_CATEGORIES_KEYS:
    if key in categorias:
        plant_food_items_original_case.update([item for item in categorias[key]])

# NUEVO: Todos los alimentos seleccionables en formularios (nombres originales)
# Incluye plantas, animales, y también los listados en probióticos/prebióticos si se quieren seleccionar individualmente
all_selectable_food_items_original_case = set()
for cat_key, cat_items in categorias.items():
    all_selectable_food_items_original_case.update(cat_items)
all_selectable_food_items_original_case = sorted(list(all_selectable_food_items_original_case))


# NUEVO: Set de alimentos vegetales normalizados para validación y búsqueda
normalized_plant_food_items = {normalize_text(item) for item in plant_food_items_original_case}

# NUEVO: Mapeo de nombres normalizados a originales para consistencia de datos
# Esto asegura que si el usuario escribe "brocoli", se guarde como "brócoli" (si "brócoli" es la forma canónica en `categorias`)
normalized_to_original_food_map = {normalize_text(item): item for item in all_selectable_food_items_original_case}


# NUEVO: Listas de prebióticos y probióticos (nombres originales)
probiotic_foods_original_case = set(categorias.get("🦠 PROBIÓTICOS", []))
prebiotic_foods_original_case = set(categorias.get("🌿 PREBIÓTICOS", []))
normalized_probiotic_foods = {normalize_text(food) for food in probiotic_foods_original_case}
normalized_prebiotic_foods = {normalize_text(food) for food in prebiotic_foods_original_case}


# --- Conectar a Google Sheets ---
# CAMBIO: Añadir manejo de errores si las credenciales no están disponibles
@st.cache_resource(ttl=600) # Cache para evitar reconexiones constantes
def get_sheet():
    if not google_services_available or creds is None:
        st.warning("Los servicios de Google no están disponibles. No se puede acceder a la hoja de cálculo.")
        return None
    try:
        client_gspread = gspread.authorize(creds)
        return client_gspread.open("habitos_microbiota").sheet1
    except Exception as e:
        st.error(f"No se pudo conectar a Google Sheets: {e}")
        return None

# NUEVO: Encabezados esperados en Google Sheets
EXPECTED_HEADERS = ["usuario", "fecha", "comida", "sueno", "ejercicio", "animo", "diversidad_diaria", "tipo"]

def check_and_create_headers(sheet):
    if sheet is None: return
    try:
        headers = sheet.row_values(1)
        if not headers or headers != EXPECTED_HEADERS:
            # Si la hoja está completamente vacía (sin siquiera la primera fila)
            if not sheet.get_all_values():
                 sheet.append_row(EXPECTED_HEADERS)
            # Si hay algo pero los encabezados no son los correctos (esto es más complejo de manejar automáticamente sin riesgo)
            # Podríamos intentar borrar y reescribir, o simplemente advertir. Por simplicidad, solo añadimos si está vacía.
            # Para un sistema robusto, se necesitaría una migración o una lógica más compleja aquí.
            elif headers != EXPECTED_HEADERS:
                 st.warning("Los encabezados de la hoja de Google Sheets no coinciden con los esperados. Por favor, verifica la hoja o vacíala para que se creen automáticamente.")
    except gspread.exceptions.APIError as e:
        if 'exceeds grid limits' in str(e): # Hoja vacía
            sheet.append_row(EXPECTED_HEADERS)
        else:
            st.error(f"Error de API con Google Sheets al verificar encabezados: {e}")
    except Exception as e:
        st.error(f"Error al verificar/crear encabezados en Google Sheets: {e}")


# --- Detección de vegetales con Google Vision AI ---
# CAMBIO: Usar el cliente global de vision y normalización de texto
# --- Detección de vegetales con Google Vision AI ---
# CAMBIO: Usar el cliente global de vision y normalización de texto
def detectar_vegetales_google_vision(image_file_content):
    if vision_client is None:
        st.warning("El cliente de Google Vision no está inicializado. No se pueden detectar vegetales.")
        return []

    image = vision.Image(content=image_file_content)
    try:
        response = vision_client.label_detection(image=image)
        labels = response.label_annotations
    except Exception as e: # Catch potential errors during the API call itself
        st.error(f"Excepción al llamar a Google Vision API: {e}")
        if hasattr(e, 'details'): # Some gRPC errors have details
             st.error(f"Detalles del error de API: {e.details()}")
        return []

    # --- START OF ADDED DEBUGGING CODE ---
    st.subheader("ℹ️ Información de Depuración de Vision API") # Added a subheader for clarity
    if response.error.message:
        st.error(f"Error devuelto por Google Vision API: {response.error.message}")
        st.json({"vision_api_error_details": response.error}) # Show full error structure
    
    debug_labels_output = []
    if labels: # Only process if labels exist
        st.write("Etiquetas detectadas por Google Vision (antes del filtrado):")
        for label in labels:
            debug_labels_output.append({
                "description_original": label.description,
                "description_normalized": normalize_text(label.description),
                "score": f"{label.score:.2f}" # Format score as string with 2 decimal places
            })
        st.json({"vision_api_raw_labels": debug_labels_output})
    else:
        st.info("Google Vision API no devolvió ninguna etiqueta para esta imagen.")
    # --- END OF ADDED DEBUGGING CODE ---

    posibles_vegetales_detectados_original_case = set()
    if not response.error.message and labels: # Only proceed if no error and labels exist
        for label in labels:
            nombre_label_norm = normalize_text(label.description)
            
            # Lógica de coincidencia (puedes refinar esto más adelante)
            # Intenta que coincida si el nombre normalizado de tu vegetal está en la etiqueta de la API
            for vegetal_norm in normalized_plant_food_items:
                if vegetal_norm in nombre_label_norm:
                    posibles_vegetales_detectados_original_case.add(
                        normalized_to_original_food_map.get(vegetal_norm, vegetal_norm)
                    )
            
            # Opcional: Intenta que coincida si la etiqueta de la API (o una palabra de ella) está en tu lista de vegetales
            # Esto podría ser útil pero también podría dar falsos positivos si no se ajusta bien.
            # label_words = set(nombre_label_norm.split())
            # for vegetal_norm in normalized_plant_food_items:
            #     if vegetal_norm in label_words:
            #         posibles_vegetales_detectados_original_case.add(
            #             normalized_to_original_food_map.get(vegetal_norm, vegetal_norm)
            #         )
    
    # Mensaje si se detectaron etiquetas pero no coincidieron con la lista (movido aquí para más contexto)
    if labels and not posibles_vegetales_detectados_original_case and not response.error.message:
        st.warning(
            "La API de Vision devolvió etiquetas (mostradas arriba en depuración), "
            "pero ninguna coincidió con tu lista interna de plantas tras la normalización y el filtrado."
        )

    return sorted(list(posibles_vegetales_detectados_original_case))


# --- Guardar registro diario ---
# CAMBIO: Añadir `user_id` y usar normalización para calcular diversidad
def guardar_registro(sheet, user_id, fecha, seleccionados_original_case, sueno, ejercicio, animo):
    if sheet is None:
        st.error("No se puede guardar el registro, la hoja de cálculo no está disponible.")
        return

    fecha_str = fecha.strftime('%Y-%m-%d')

    # Calcular diversidad diaria basada en alimentos vegetales normalizados
    # `seleccionados_original_case` son los nombres tal como están en `categorias`
    vegetales_dia_normalizados = set()
    for item_original in seleccionados_original_case:
        item_norm = normalize_text(item_original)
        if item_norm in normalized_plant_food_items:
            vegetales_dia_normalizados.add(item_norm)
    
    diversidad_diaria = len(vegetales_dia_normalizados)

    # Guardar los nombres originales en la hoja
    comida_str = ", ".join(seleccionados_original_case)

    try:
        sheet.append_row([
            user_id, fecha_str, comida_str, sueno, ejercicio, animo, diversidad_diaria, "registro"
        ])
        st.success(f"✅ Registro para {user_id} guardado: {diversidad_diaria} plantas hoy.")
    except Exception as e:
        st.error(f"Error al guardar el registro en Google Sheets: {e}")

    # El resumen semanal se calculará de forma diferente o se llamará explícitamente por el usuario
    # if fecha.weekday() == 0:
    #     guardar_resumen_semanal_usuario(sheet, user_id, fecha)


# --- Guardar resumen semanal (AHORA POR USUARIO Y CON LÓGICA REVISADA) ---
def calcular_y_guardar_resumen_semanal_usuario(sheet, user_id, fecha_referencia_lunes):
    if sheet is None: return
    
    st.write(f"Calculando resumen semanal para {user_id} para la semana que termina el {fecha_referencia_lunes.strftime('%Y-%m-%d')}")

    all_records = []
    try:
        all_records = sheet.get_all_records() # Esto asume que los encabezados son correctos y únicos
    except Exception as e:
        st.error(f"No se pudieron obtener todos los registros para el resumen semanal: {e}")
        # Podríamos intentar con get_all_values y parsear manualmente si get_all_records falla consistentemente
        return

    if not all_records:
        st.warning("La hoja está vacía, no se puede generar resumen semanal.")
        return

    df = pd.DataFrame(all_records)

    # Filtrar por usuario
    df_user = df[df["usuario"] == user_id].copy() # Usar .copy() para evitar SettingWithCopyWarning

    if df_user.empty:
        st.info(f"No hay registros para el usuario {user_id} para generar resumen semanal.")
        return

    # Convertir 'fecha' a datetime.date, manejando errores
    try:
        df_user["fecha"] = pd.to_datetime(df_user["fecha"], errors='coerce').dt.date
        df_user.dropna(subset=["fecha"], inplace=True) # Eliminar filas donde la fecha no se pudo convertir
    except Exception as e:
        st.error(f"Error convirtiendo fechas para el resumen: {e}")
        return
        
    # El `fecha_referencia_lunes` es el lunes de la semana para la que se hace el resumen (o el día que gatilla el resumen)
    # Queremos los 7 días ANTERIORES a este lunes (es decir, la semana completa que acaba de terminar)
    # Por ejemplo, si hoy es lunes 13, queremos del lunes 6 al domingo 12.
    # `fecha_referencia_lunes` es el día del resumen.
    # `inicio_semana_a_resumir` es el lunes de la semana que se va a resumir.
    # `fin_semana_a_resumir` es el domingo de esa semana.

    # Si `fecha_referencia_lunes` es el lunes actual, el resumen es de la semana pasada.
    fin_semana_a_resumir = fecha_referencia_lunes - timedelta(days=1) # Domingo pasado
    inicio_semana_a_resumir = fin_semana_a_resumir - timedelta(days=6) # Lunes pasado

    # Filtrar registros de la semana a resumir que sean de tipo "registro"
    semana_df = df_user[
        (df_user["fecha"] >= inicio_semana_a_resumir) &
        (df_user["fecha"] <= fin_semana_a_resumir) &
        (df_user["tipo"] == "registro")
    ].copy()

    if semana_df.empty:
        st.info(f"No hay registros de 'registro' para {user_id} en la semana del {inicio_semana_a_resumir.strftime('%Y-%m-%d')} al {fin_semana_a_resumir.strftime('%Y-%m-%d')}.")
        diversidad_semanal = 0
    else:
        vegetales_semana_normalizados = set()
        for _, row in semana_df.iterrows():
            comida_registrada = str(row.get("comida", "")).split(",")
            for item_original in comida_registrada:
                item_original_trimmed = item_original.strip()
                if not item_original_trimmed: continue # Saltar si está vacío
                
                item_norm = normalize_text(item_original_trimmed)
                if item_norm in normalized_plant_food_items: # Solo contamos plantas válidas
                    vegetales_semana_normalizados.add(item_norm)
        diversidad_semanal = len(vegetales_semana_normalizados)

    # Verificar si ya existe un resumen para este usuario y esta fecha de resumen
    # La fecha del resumen es el lunes en que se genera.
    fecha_resumen_str = fecha_referencia_lunes.strftime('%Y-%m-%d')
    
    resumen_existente = df_user[
        (df_user["fecha"] == fecha_referencia_lunes) & # Convertir a date si no lo es ya
        (df_user["tipo"] == "resumen")
    ]

    if resumen_existente.empty:
        try:
            sheet.append_row([
                user_id, fecha_resumen_str, f"Resumen de la semana {inicio_semana_a_resumir.strftime('%Y-%m-%d')} - {fin_semana_a_resumir.strftime('%Y-%m-%d')}",
                "", "", "", diversidad_semanal, "resumen"
            ])
            st.success(f"📝 Resumen semanal para {user_id} guardado: {diversidad_semanal} plantas.")
        except Exception as e:
            st.error(f"Error al guardar el resumen semanal en Google Sheets: {e}")
    else:
        st.info(f"Ya existe un resumen para {user_id} en la fecha {fecha_resumen_str}.")


# --- Visualización y análisis ---
# CAMBIO: Adaptar para DataFrame filtrado por usuario y usar normalización
def mostrar_registros_y_analisis(df_user, current_user_id):
    if df_user.empty:
        st.info(f"Aún no hay registros para el usuario {current_user_id}.")
        return

    df_display = df_user[df_user['tipo'] == 'registro'].copy()
    if df_display.empty:
        st.info(f"Aún no hay registros de tipo 'registro' para el usuario {current_user_id} para mostrar detalles.")
        return
        
    # Convertir tipos de datos para asegurar que Plotly y ML funcionen bien
    df_display["fecha"] = pd.to_datetime(df_display["fecha"]).dt.date
    df_display["diversidad_diaria"] = pd.to_numeric(df_display["diversidad_diaria"], errors='coerce').fillna(0)
    df_display["sueno"] = pd.to_numeric(df_display["sueno"], errors='coerce') # No rellenar NaNs aún para plots
    df_display["animo"] = pd.to_numeric(df_display["animo"], errors='coerce')

    st.markdown("---")
    st.subheader(f"📅 Tus vegetales únicos por día ({current_user_id})")
    
    # Agrupar por fecha y mostrar vegetales únicos
    for fecha_registro, grupo in df_display.groupby("fecha"):
        plantas_diarias_original_case = set()
        for entrada_comida in grupo["comida"].dropna():
            items_comida = [i.strip() for i in entrada_comida.split(",") if i.strip()]
            for item_original in items_comida:
                if normalize_text(item_original) in normalized_plant_food_items:
                    plantas_diarias_original_case.add(item_original) # Mostrar el nombre original
        
        if plantas_diarias_original_case:
             st.markdown(f"📆 **{fecha_registro.strftime('%Y-%m-%d')}**: {len(plantas_diarias_original_case)} plantas: {', '.join(sorted(list(plantas_diarias_original_case)))}")
        else:
             st.markdown(f"📆 **{fecha_registro.strftime('%Y-%m-%d')}**: 0 plantas.")


    st.markdown("---")
    st.subheader(f"🌿 Tu diversidad vegetal esta semana ({current_user_id})")
    
    # Calcular progreso de la semana actual
    hoy = datetime.now().date()
    inicio_semana_actual = hoy - timedelta(days=hoy.weekday()) # Lunes de esta semana
    
    df_semana_actual = df_display[df_display["fecha"] >= inicio_semana_actual]
    
    plantas_consumidas_semana_actual_norm = set()
    for entrada_comida in df_semana_actual["comida"].dropna():
        items_comida = [i.strip() for i in entrada_comida.split(",") if i.strip()]
        for item_original in items_comida:
            item_norm = normalize_text(item_original)
            if item_norm in normalized_plant_food_items:
                plantas_consumidas_semana_actual_norm.add(item_norm)
    
    progreso = len(plantas_consumidas_semana_actual_norm)
    st.markdown(f"Esta semana has comido **{progreso} / 30** plantas diferentes.")
    st.progress(min(progreso / 30.0, 1.0)) # Asegurar que no exceda 1.0

    # Sugerencias
    plantas_sugerencias_original_case = [
        orig_name for norm_name, orig_name in normalized_to_original_food_map.items()
        if norm_name in normalized_plant_food_items and norm_name not in plantas_consumidas_semana_actual_norm
    ]
    
    sugerencias_final = sorted(list(set(plantas_sugerencias_original_case))) # Uniques y ordenado
    random.shuffle(sugerencias_final) # Barajar para variar

    st.subheader("💡 Sugerencias para hoy")
    if progreso < 30 and sugerencias_final:
        st.markdown("🌟 Prueba algo nuevo: " + ", ".join(sugerencias_final[:5]))
    elif progreso >= 30:
        st.success("🎉 ¡Felicidades! Ya has alcanzado o superado las 30 plantas distintas esta semana.")
    else:
        st.info("Parece que has probado todas las plantas de nuestra lista para esta semana, o no hay más sugerencias disponibles.")

    # --- Visualizaciones Plotly ---
    if not df_display.empty:
        st.subheader("📊 Gráfico: Ánimo vs. Sueño")
        fig = px.scatter(df_display.dropna(subset=['sueno', 'animo']), x="sueno", y="animo", hover_data=["fecha", "comida"], title="Relación Ánimo y Sueño")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📈 Diversidad de plantas por día")
        fig2 = px.line(df_display, x="fecha", y="diversidad_diaria", title="Evolución de la Diversidad Diaria de Plantas")
        st.plotly_chart(fig2, use_container_width=True)

        # --- ML: Regresión para predecir ánimo ---
        st.subheader("🤖 Predicción de Ánimo (ML)")
        df_ml = df_display[['sueno', 'animo', 'diversidad_diaria']].copy()
        df_ml.dropna(inplace=True) # Usar solo filas con datos completos para ML simple

        if len(df_ml) > 3 and 'sueno' in df_ml.columns and 'animo' in df_ml.columns:
            X = df_ml[["sueno", "diversidad_diaria"]] # Usar sueño y diversidad para predecir ánimo
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
        features_cluster = df_display[["diversidad_diaria", "sueno", "animo"]].copy()
        features_cluster.dropna(inplace=True)

        if len(features_cluster) >= 3: # KMeans necesita al menos tantos puntos como clusters (o más)
            # Intentar con 2 o 3 clusters si hay suficientes datos
            n_clusters_kmeans = min(3, len(features_cluster)) 
            if n_clusters_kmeans < 2: n_clusters_kmeans = 2 # Mínimo 2 clusters

            if len(features_cluster) >= n_clusters_kmeans :
                try:
                    kmeans = KMeans(n_clusters=n_clusters_kmeans, random_state=42, n_init='auto').fit(features_cluster)
                    # Añadir 'cluster' a df_display para el plot, alineando índices
                    # Esto es un poco más complejo porque features_cluster es un subconjunto de df_display
                    # Crear una columna de cluster en df_display, inicializada con NaN
                    df_display['cluster'] = pd.Series(dtype='Int64') 
                    # Asignar los labels de kmeans a las filas correspondientes en df_display
                    df_display.loc[features_cluster.index, 'cluster'] = kmeans.labels_

                    fig3 = px.scatter(df_display.dropna(subset=['cluster']), x="diversidad_diaria", y="sueno", color="cluster",
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
    if not df_user.empty:
        csv_buffer = io.StringIO()
        df_user.to_csv(csv_buffer, index=False, encoding='utf-8')
        st.download_button(
            label="⬇️ Descargar tus datos como CSV",
            data=csv_buffer.getvalue(),
            file_name=f"registro_nutribio_{current_user_id}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("No hay datos para exportar.")

# --- Mensajes sobre Prebióticos y Probióticos ---
# NUEVO: Función para mostrar mensajes
def mostrar_mensajes_pre_probioticos(df_user_registros, current_user_id):
    st.markdown("---")
    st.subheader("💡 Sabías que...")

    mensajes = [
        "Los **probióticos** son microorganismos vivos que, administrados en cantidades adecuadas, confieren un beneficio a la salud del huésped. ¡Busca yogur, kéfir o chucrut!",
        "Los **prebióticos** son el alimento de tus bacterias intestinales beneficiosas. Encuéntralos en alimentos como ajos, cebollas, puerros, espárragos, plátanos verdes y avena.",
        "Una microbiota diversa es clave para una buena salud digestiva e inmunológica. ¡Varía tus fuentes de prebióticos y probióticos!",
        "El consumo regular de prebióticos puede mejorar la absorción de minerales como el calcio.",
        "Los probióticos pueden ayudar a equilibrar tu microbiota después de un tratamiento con antibióticos.",
        "Incluir alimentos fermentados en tu dieta es una excelente forma de obtener probióticos naturales."
    ]
    st.info(random.choice(mensajes))

    # Verificar consumo reciente
    if not df_user_registros.empty:
        consumo_reciente_pro = False
        consumo_reciente_pre = False
        hoy = datetime.now().date()
        # Considerar registros de los últimos 3 días
        registros_recientes = df_user_registros[df_user_registros["fecha"] >= (hoy - timedelta(days=3))]

        for _, row in registros_recientes.iterrows():
            comida_registrada = str(row.get("comida", "")).split(",")
            for item_original in comida_registrada:
                item_norm = normalize_text(item_original.strip())
                if item_norm in normalized_probiotic_foods:
                    consumo_reciente_pro = True
                if item_norm in normalized_prebiotic_foods:
                    consumo_reciente_pre = True
            if consumo_reciente_pre and consumo_reciente_pro:
                break
        
        if not consumo_reciente_pro:
            st.warning(f"💡 {current_user_id}, parece que no has registrado probióticos recientemente. Considera añadir alimentos como kéfir, yogur natural o chucrut.")
        if not consumo_reciente_pre:
            st.warning(f"💡 {current_user_id}, ¿qué tal unos prebióticos? Ajo, cebolla, espárragos o avena son buenas opciones para alimentar tu microbiota.")


# --- Main App ---
def main():
    st.sidebar.header("👤 Usuario")
    # CAMBIO: Sistema simple de "inicio de sesión" por nombre de usuario
    if 'current_user' not in st.session_state:
        st.session_state.current_user = ""

    user_input = st.sidebar.text_input("Ingresa tu nombre de usuario:", value=st.session_state.current_user, key="user_login_input")
    
    if st.sidebar.button("Acceder / Cambiar Usuario"):
        if user_input:
            st.session_state.current_user = normalize_text(user_input.strip()) # Guardar normalizado para consistencia
            st.sidebar.success(f"Usuario actual: {st.session_state.current_user}")
        else:
            st.sidebar.error("El nombre de usuario no puede estar vacío.")

    current_user_id = st.session_state.current_user

    if not current_user_id:
        st.info("Por favor, ingresa un nombre de usuario en la barra lateral para continuar.")
        st.stop() # Detener la ejecución si no hay usuario

    # Obtener la hoja de Google Sheets y verificar encabezados
    sheet = get_sheet()
    if sheet: # Solo verificar encabezados si la hoja se cargó
        check_and_create_headers(sheet) # Asegura que los encabezados existan como se espera

    # --- Columnas para layout ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"📋 Registro diario para {current_user_id}")
        with st.form("registro_diario_form"):
            # CAMBIO: Usar nombres originales para mostrar, se normalizarán al guardar/procesar
            # El multiselect ahora usa una función para formatear opciones y permitir búsqueda sin acentos
            # Sin embargo, st.multiselect no tiene una función de formateo de opciones tan directa.
            # El usuario escribirá, y el sistema debe ser tolerante.
            # La validación se hará con nombres normalizados.
            
            # Para que el usuario pueda escribir "brocoli" y se sugiera "brócoli":
            # Streamlit no tiene esta funcionalidad directamente en multiselect.
            # Lo que podemos hacer es educar al usuario o tener una lista muy clara.
            # La normalización al guardar es lo que asegura que "BROCOLI" se trate como "brócoli".
            
            seleccionados_form = st.multiselect(
                "¿Qué comiste hoy? (Puedes escribir para buscar)",
                options=all_selectable_food_items_original_case,
                help="Escribe parte del nombre, ej: 'manza' para 'manzana'."
            )
            
            fecha_registro_form = st.date_input("Fecha del registro", datetime.now().date())
            sueno_form = st.number_input("¿Horas de sueño?", min_value=0.0, max_value=24.0, step=0.5, value=7.0)
            ejercicio_form = st.text_input("¿Ejercicio realizado?")
            animo_form = st.slider("¿Cómo te sientes hoy? (1=Mal, 5=Excelente)", 1, 5, 3)
            
            submitted_registro_manual = st.form_submit_button("Guardar Registro Manual")

            if submitted_registro_manual:
                if not seleccionados_form:
                    st.warning("Por favor, selecciona al menos un alimento.")
                else:
                    # Los `seleccionados_form` ya son los nombres canónicos/originales
                    guardar_registro(sheet, current_user_id, fecha_registro_form, seleccionados_form, sueno_form, ejercicio_form, animo_form)

    with col2:
        st.subheader("📸 Detección desde foto")
        if vision_client is None:
            st.warning("La detección por imagen no está disponible (cliente de Vision no inicializado).")
        else:
            img_file = st.file_uploader("Sube una foto de tu comida (opcional)", type=["jpg", "jpeg", "png"])

            if img_file:
                st.image(img_file, caption="Tu imagen", use_container_width=True)
                
                # Leer contenido del archivo para Vision API
                img_bytes = img_file.getvalue() # Leer una vez
                
                with st.spinner("Detectando vegetales en la imagen..."):
                    vegetales_detectados_img = detectar_vegetales_google_vision(img_bytes)

                if vegetales_detectados_img:
                    st.info(f"Posibles vegetales detectados: {', '.join(vegetales_detectados_img)}")
                    
                    with st.form("confirmar_vegetales_img_form"):
                        st.write("Por favor, confirma los vegetales y añade otros si es necesario.")
                        # Vegetales confirmados de la detección
                        confirmados_api = st.multiselect(
                            "Confirma los vegetales detectados en tu comida:",
                            options=vegetales_detectados_img,
                            default=vegetales_detectados_img
                        )
                        # Añadir manualmente otros vegetales no detectados
                        adicionales_manual_img = st.multiselect(
                            "Añade otros vegetales de tu comida (si no fueron detectados):",
                            options=[v for v in plant_food_items_original_case if v not in vegetales_detectados_img] # Evitar duplicados
                        )
                        
                        todos_seleccionados_img = sorted(list(set(confirmados_api + adicionales_manual_img)))
                        
                        st.write("**Completa los datos para este registro:**")
                        fecha_registro_img = st.date_input("Fecha del registro (imagen)", datetime.now().date(), key="fecha_img")
                        sueno_img = st.number_input("¿Horas de sueño ese día?", min_value=0.0, max_value=24.0, step=0.5, value=sueno_form, key="sueno_img") # Default del otro form
                        ejercicio_img = st.text_input("¿Ejercicio realizado ese día?", value=ejercicio_form, key="ejercicio_img")
                        animo_img = st.slider("¿Cómo te sentiste ese día? (1=Mal, 5=Excelente)", 1, 5, animo_form, key="animo_img")

                        submitted_confirmar_img = st.form_submit_button("✅ Confirmar y Guardar Vegetales de Imagen")

                        if submitted_confirmar_img:
                            if not todos_seleccionados_img:
                                st.warning("No has seleccionado ningún vegetal para guardar.")
                            else:
                                guardar_registro(sheet, current_user_id, fecha_registro_img, todos_seleccionados_img, sueno_img, ejercicio_img, animo_img)
                elif img_file and not vegetales_detectados_img: # Si se subió imagen pero no se detectó nada
                    st.warning("🤔 No se detectaron vegetales conocidos en la lista de plantas. Puedes añadirlos manualmente en el formulario de la izquierda.")


    # --- Visualización de registros y análisis (fuera de las columnas) ---
    if sheet: # Solo intentar cargar y mostrar si la hoja está disponible
        st.markdown("---")
        st.header(f"📊 Tu Progreso y Análisis ({current_user_id})")
        
        # Botón para generar resumen semanal manualmente
        if st.button(f"Calcular/Actualizar Resumen Semanal para {current_user_id} (para la semana pasada)"):
            hoy = datetime.now().date()
            lunes_esta_semana = hoy - timedelta(days=hoy.weekday())
            # El resumen siempre se calcula para la semana que acaba de terminar el domingo pasado.
            # Por lo tanto, la fecha de referencia es el lunes de esta semana.
            calcular_y_guardar_resumen_semanal_usuario(sheet, current_user_id, lunes_esta_semana)


        try:
            data_with_headers = sheet.get_all_records(expected_headers=EXPECTED_HEADERS) # Usar los encabezados esperados
            df_full = pd.DataFrame(data_with_headers)
            
            if not df_full.empty:
                # Filtrar por usuario ANTES de pasar a las funciones de display
                df_user_specific = df_full[df_full["usuario"] == current_user_id].copy()
                
                if not df_user_specific.empty:
                    # Convertir 'fecha' a datetime.date aquí para df_user_specific una vez
                    df_user_specific["fecha"] = pd.to_datetime(df_user_specific["fecha"], errors='coerce').dt.date
                    df_user_specific.dropna(subset=["fecha"], inplace=True) # Quitar filas donde la fecha es inválida
                    
                    mostrar_registros_y_analisis(df_user_specific, current_user_id)
                    
                    # Separar registros de tipo 'registro' para mensajes pre/probióticos
                    df_user_registros_tipo_registro = df_user_specific[df_user_specific['tipo'] == 'registro'].copy()
                    mostrar_mensajes_pre_probioticos(df_user_registros_tipo_registro, current_user_id)

                else:
                    st.info(f"No hay datos registrados para el usuario '{current_user_id}'. ¡Empieza a añadir tus comidas!")
            else:
                st.info("La hoja de cálculo parece estar vacía. ¡Comienza a registrar tus comidas!")

        except gspread.exceptions.GSpreadException as e:
             st.error(f"Error de gspread al obtener registros: {e}. Asegúrate que los encabezados en la hoja ('{sheet.title}') son: {', '.join(EXPECTED_HEADERS)}")
        except Exception as e:
            st.warning(f"No se pudieron cargar o procesar todos los datos de Google Sheets: {e}")
            st.info("Si acabas de empezar, puede que aún no haya datos que mostrar.")

if __name__ == "__main__":
    main()

