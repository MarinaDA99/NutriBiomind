import pandas as pd
import streamlit as st
import csv
import os
from datetime import datetime, timedelta
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ------------------------------
# FUNCION PARA GUARDAR EN GOOGLE SHEETS
# ------------------------------
def guardar_en_google_sheets(fila):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(creds_dict), scope)

    client = gspread.authorize(creds)
    sheet = client.open_by_key("1v9T0pF1uc6dSOApn-o12F_7qDO_ii5FkecTxAHlaW9U").sheet1
    sheet.append_row(fila)


import streamlit as st
from PIL import Image

# Configurar la página
st.set_page_config(page_title="NutriBioMind", layout="centered")

# Cargar y mostrar el logo centrado con alta resolución
logo = Image.open("logo.png")
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image(logo, width=120)  # Ajustá el tamaño: 250 o más si querés
st.markdown("</div>", unsafe_allow_html=True)


# Título principal
st.markdown("<h1 style='text-align: center;'>🌿 Tu guía hacia una microbiota saludable</h1>", unsafe_allow_html=True)

# Subtítulo
st.markdown("<h5 style='text-align: center;'>🌱 La regla de oro para una microbiota saludable: 30 plantas por semana</h3>", unsafe_allow_html=True)

# ------------------------------
# CATEGORÍAS Y ALIMENTOS
# ------------------------------
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
  "🦠 PROBIÓTICOS": ["yogur natural", "yogur griego", "yogur de cabra", "yogur de oveja", "yogur vegetal con cultivos", "kefir de leche",
  "kefir de agua", "kefir de coco", "kefir de cabra", "laban (yogur árabe)", "lassi", "ayran", "matsoni", "viili", "filmjölk",
  "suero de leche fermentado", "buttermilk tradicional", "queso azul", "queso roquefort", "queso camembert", "queso brie",
  "queso gouda curado", "queso emmental", "queso cheddar fermentado", "queso feta tradicional", "queso de cabra sin pasteurizar",
  "queso de oveja curado", "queso halloumi fermentado", "miso", "miso blanco", "miso rojo", "miso oscuro", "tempeh",
  "tempeh de soja", "tempeh de garbanzo", "natto", "tofu fermentado", "salsa de soja fermentada", "tamari", "shoyu",
  "chucrut (fermentado en crudo)", "kimchi", "repollo fermentado", "pickles fermentados (no en vinagre)", "pepino fermentado",
  "zanahoria fermentada", "remolacha fermentada", "col rizada fermentada", "fermentado de brócoli", "kombucha", "kombucha de frutas",
  "kombucha con jengibre", "kombucha casera", "vino de kombucha", "tepache", "tepache de piña", "kvass de remolacha",
  "kvass de pan de centeno", "rejuvelac (agua de trigo fermentado)", "amasake", "amazake", "fermento de arroz koji", "kinema",
  "gundruk (Nepal)", "bai jiu fermentado", "idli", "dosas fermentadas", "urd fermentado", "injera", "ogi (Nigeria)",
  "ogi de sorgo", "ogi de maíz", "ogi de mijo", "fermento de avena", "fermento de linaza", "fermento de yuca",
  "fermento de batata", "lentejas fermentadas", "garbanzos fermentados", "salsa de pescado (fermentada)", "nam pla (Tailandia)",
  "nuoc mam (Vietnam)", "balachong", "garum (romano)", "sardinas fermentadas", "anchoas fermentadas", "queso de soja",
  "natto con huevo", "fermentado de cebolla", "fermentado de ajo negro", "fermentado de apio", "fermentado de berenjena",
  "fermentado de pimiento", "fermentado de espinaca", "fermentado de setas", "pan de masa madre (con cultivo activo)",
  "vinagre de manzana sin filtrar (con madre)", "vinagre de arroz fermentado", "kombucha madre", "granos de kéfir vivos",
  "starter de yogur", "cultivo de fermentación láctica", "probióticos encapsulados naturales", "agua de kéfir casera"],
  "🌿 PREBIÓTICOS": ["ajo crudo", "cebolla cruda", "puerro", "alcachofa", "alcachofa de Jerusalén", "espárrago", "espinaca", "remolacha",
  "col rizada", "coles de Bruselas", "brócoli", "zanahoria", "chirivía", "nabo", "rábano", "calabaza", "boniato",
  "patata cocida y enfriada", "arroz cocido y enfriado", "plátano verde", "plátano macho", "manzana con piel", "kiwi",
  "pera con piel", "melocotón", "higos", "dátil", "avena", "cebada", "trigo integral", "salvado de trigo", "centeno",
  "espelta", "kamut", "freekeh", "quinoa", "sorgo", "mijo", "alforfón", "arroz salvaje", "legumbres (lentejas)",
  "garbanzos", "judías negras", "judías pintas", "judías blancas", "soja", "guisantes", "azukis", "mungo", "lupinos",
  "chia hidratada", "semillas de lino molidas", "almendras", "pistachos", "nueces", "nueces de Brasil", "anacardos",
  "cacao puro", "raíz de yacón", "raíz de diente de león", "raíz de achicoria", "topinambur", "raíz de bardana",
  "jengibre fresco", "curcuma fresca", "cardo", "berros", "canónigos", "diente de león (hojas)", "escarola", "endibia",
  "rúcula", "lechuga romana", "col lombarda", "col blanca", "repollo", "apio", "malanga", "ñame", "taro", "yuca",
  "okras", "setas (shiitake)", "setas maitake", "setas gírgola", "albahaca fresca", "perejil", "cilantro", "hinojo crudo",
  "menta", "hierbabuena", "romero", "tomillo", "orégano", "psyllium", "inulina pura", "semillas de cáñamo", "semillas de sésamo",
  "semillas de calabaza", "semillas de girasol", "pipas con cáscara", "maíz cocido", "cuscús integral"]
}

# Define las categorías que cuentan como vegetales
grupos_vegetales = [
    "🥦 Verduras y hortalizas",
    "🍎 Frutas",
    "🫘 Legumbres",
    "🌰 Frutos secos y semillas",
    "🌾 Cereales y pseudocereales"
]

# Construye un set de alimentos válidos (en minúsculas)
vegetales_validos = set()
for grupo in grupos_vegetales:
    if grupo in categorias:
        vegetales_validos.update([a.lower() for a in categorias[grupo]])
    else:
        st.warning(f"Categoría no encontrada en 'categorias': {grupo}")




todos_alimentos = sorted({item for sublist in categorias.values() for item in sublist})
# ------------------------------
# FORMULARIO DE REGISTRO
# ------------------------------
with st.form("registro"):
    st.subheader("📋 Registro diario")
    seleccionados = st.multiselect("Selecciona los alimentos que comiste hoy:", options=todos_alimentos)
    sueno = st.number_input("¿Cuántas horas dormiste?", min_value=0.0, max_value=24.0, step=0.5)
    ejercicio = st.text_input("¿Ejercicio realizado?")
    animo = st.slider("¿Cómo te sientes hoy?", 1, 5, 3)
    submitted = st.form_submit_button("Guardar")

    if submitted:
        fecha = datetime.now().strftime('%Y-%m-%d')
        categorias_contadas = {cat: 0 for cat in categorias}
        for cat, items in categorias.items():
            if any(item.lower() in [s.lower() for s in seleccionados] for item in items):
                categorias_contadas[cat] = 1

        fila = [fecha, ", ".join(seleccionados), sueno, ejercicio, animo] + list(categorias_contadas.values())
        guardar_en_google_sheets(fila)
        st.success("✅ Registro guardado en Google Sheets.")

        # ------------------------------
        # DIVERSIDAD VEGETAL SEMANAL
        # ------------------------------
        try:
            df = pd.DataFrame([fila], columns=["fecha", "comida", "sueno", "ejercicio", "animo"] + list(categorias.keys()))
            df["fecha"] = pd.to_datetime(df["fecha"])
            alimentos_semana = set()
            for entry in df["comida"].dropna():
                for alimento in entry.split(","):
                    alimento_limpio = alimento.strip().lower()
                    if alimento_limpio in vegetales_validos:
                        alimentos_semana.add(alimento_limpio)
            progreso = len(alimentos_semana)
            total_objetivo = 30
            bloques_llenos = "🟩" * progreso
            bloques_vacios = "⬜" * (total_objetivo - progreso)
            st.markdown("### 🌿 Diversidad vegetal esta semana")
            st.markdown(f"{bloques_llenos}{bloques_vacios}")
        except:
            st.info("No se pudo calcular la diversidad vegetal aún.")

        # --- CONSEJOS ---
        if sueno < 6:
            st.warning("😴 Has dormido poco. Intenta descansar al menos 7-8 horas.")
        elif sueno > 10:
            st.warning("🛌 Dormiste mucho. Evalúa si estás recuperando energía o sintiéndote fatigada.")

        if ejercicio:
            try:
                minutos = int("".join(filter(str.isdigit, ejercicio)))
                if minutos < 30:
                    st.info("🏃‍♀️ Intenta hacer al menos 30 minutos de actividad física diaria.")
                elif minutos > 180:
                    st.warning("⚠️ Demasiado ejercicio puede causar fatiga. Escucha a tu cuerpo.")
            except:
                st.info("No se pudo interpretar el tiempo de ejercicio.")

        esenciales = ["🥦 Verduras y hortalizas", "🍎 Frutas", "🦠 PROBIÓTICOS", "🌱 PREBIÓTICOS"]
        faltantes = [cat for cat in esenciales if categorias_contadas.get(cat, 0) == 0]
        if faltantes:
            st.warning("👉 Hoy no consumiste: " + ", ".join(faltantes))
        else:
            st.success("✅ ¡Incluiste todos los grupos clave!")

        st.markdown("💡 **Tip útil:** Lo ideal es combinar probióticos + prebióticos en una misma comida. Ejemplo: yogur natural con plátano o kéfir con avena y manzana rallada.")

# ------------------------------
# ANÁLISIS SEMANAL
# ------------------------------
st.markdown("---")
st.subheader("📈 Análisis semanal")

def leer_datos():
    try:
        df = pd.read_csv("data/habitos.csv", header=None, encoding='utf-8-sig')
        df.columns = ["fecha", "comida", "sueno", "ejercicio", "animo"] + list(categorias.keys())
        df["fecha"] = pd.to_datetime(df["fecha"])
        return df
    except:
        return pd.DataFrame()

df = leer_datos()
if not df.empty:
    inicio_semana = datetime.now() - timedelta(days=datetime.now().weekday())
    df_semana = df[df["fecha"] >= inicio_semana]
    suma_cat = df_semana[list(categorias.keys())].sum()
    st.bar_chart(suma_cat)

    alimentos_semana = set()
    for entry in df_semana["comida"]:
        for alimento in entry.split(","):
            alimentos_semana.add(alimento.strip().lower())

    st.markdown(f"🌿 Esta semana has consumido **{len(alimentos_semana)} / 30** vegetales distintos.")
else:
    st.info("Aún no hay datos registrados esta semana.")

