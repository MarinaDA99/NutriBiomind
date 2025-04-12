import pandas as pd
import streamlit as st
import csv
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="NutriMind", layout="centered")
st.title("🌱 NutriMind: Tu coach de hábitos saludables")

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

todos_alimentos = sorted({item for sublist in categorias.values() for item in sublist})

# ------------------------------
# REGISTRO DIARIO
# ------------------------------
with st.form("registro"):
    st.subheader("📋 Registro diario")

    seleccionados = st.multiselect(
        "Selecciona los alimentos que comiste hoy:",
        options=todos_alimentos,
        help="Puedes seleccionar varios (usa Ctrl/Cmd)"
    )

    sueno = st.number_input("¿Cuántas horas dormiste?", min_value=0.0, max_value=24.0, step=0.5)
    ejercicio = st.text_input("¿Ejercicio realizado (ej: 30 min caminata)?")
    animo = st.slider("¿Cómo te sientes hoy?", 1, 5, 3)
    submitted = st.form_submit_button("Guardar")

    if submitted:
        fecha = datetime.now().strftime('%Y-%m-%d')
        categorias_contadas = {cat: 0 for cat in categorias}
        for cat, items in categorias.items():
            if any(item.lower() in [s.lower() for s in seleccionados] for item in items):
                categorias_contadas[cat] = 1

        os.makedirs("data", exist_ok=True)
        with open("data/habitos.csv", "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([fecha, ", ".join(seleccionados), sueno, ejercicio, animo] + list(categorias_contadas.values()))

        st.success("✅ Registro guardado correctamente.")
        # ------------------------------
        # 🌿 Cálculo de vegetales únicos esta semana (desde el lunes)
        # ------------------------------
        try:
            df = pd.read_csv("data/habitos.csv", header=None)
            df.columns = ["fecha", "comida", "sueno", "ejercicio", "animo"] + list(categorias.keys())
            df["fecha"] = pd.to_datetime(df["fecha"])

            # Filtrar desde el lunes de esta semana
            inicio_semana = datetime.now() - timedelta(days=datetime.now().weekday())
            df_semana = df[df["fecha"] >= inicio_semana]

            # Juntar todos los alimentos de la semana
            alimentos_semana = set()
            for entry in df_semana["comida"]:
                for alimento in entry.split(","):
                    alimentos_semana.add(alimento.strip().lower())

            # Mostrar progreso semanal
            total_objetivo = 30
            progreso = len(alimentos_semana)
            st.success(f"🌿 Llevas {progreso}/{total_objetivo} vegetales distintos esta semana.")
        except Exception as e:
            st.info("No se pudo calcular la diversidad vegetal aún.")

        # ------------------------------
        # 🌿 Diversidad vegetal semanal tras registrar
        # ------------------------------
        try:
            df = pd.read_csv("data/habitos.csv", header=None)
            df.columns = ["fecha", "comida", "sueno", "ejercicio", "animo"] + list(categorias.keys())
            df["fecha"] = pd.to_datetime(df["fecha"])

            # Solo datos desde el lunes
            inicio_semana = datetime.now() - timedelta(days=datetime.now().weekday())
            df_semana = df[df["fecha"] >= inicio_semana]

            # Juntar alimentos únicos
            alimentos_semana = set()
            for entry in df_semana["comida"].dropna():
                for alimento in entry.split(","):
                    alimentos_semana.add(alimento.strip().lower())

            # Vegetales objetivo para contar progreso
            vegetales_objetivo = [
  # Frutas
  "mandarinas", "naranjas", "kiwi", "uva", "manzanas", "peras", "granada", "plátanos", "fresas", "frambuesas",
  "moras", "arándanos", "cerezas", "melocotón", "albaricoques", "ciruelas", "mango", "papaya", "piña", "melón",
  "sandía", "higos", "caquis", "lichi", "maracuyá", "guayaba", "chirimoya", "carambola", "níspero", "pomelo",
  "lima", "limón", "coco", "aguacate", "tomate cherry", "grosellas", "zarzamoras", "plátano macho", "dátiles",

  # Verduras y hortalizas
  "judía tierna", "nabo", "col", "col de Bruselas", "coliflor", "puerro", "apio", "acelgas", "espinacas", "brécol",
  "escarola", "endibia", "rábanos", "ajos tiernos", "alcachofa", "chirivía", "espárragos", "zanahorias", "calabaza",
  "calabacín", "cardo", "cebolla", "cebolleta", "col blanca", "col lombarda", "col rizada (kale)", "hinojo",
  "lechuga romana", "lechuga iceberg", "pepino", "pimiento rojo", "pimiento verde", "remolacha", "tomate", "boniato",
  "patata", "ñame", "taro", "malanga", "yuca", "okra", "pak choi", "berza", "acedera", "mostaza verde",
  "diente de león", "berros", "canónigos", "mizuna", "tatsoi",

  # Setas y hongos
  "champiñones", "shiitakes", "gírgolas", "maitake", "enoki", "portobello", "rebozuelo", "trompeta de la muerte",
  "seta de cardo", "seta de chopo", "seta de pie azul", "seta de pino", "seta de haya", "seta de álamo",
  "seta de abedul", "seta de roble",

  # Legumbres
  "lentejas", "garbanzos", "judías", "habas", "guisantes", "azukis", "soja", "judía blanca", "judía roja",
  "judía negra", "mungo", "lupino", "alubia pinta", "alubia canela", "alubia carilla", "alubia de Lima",
  "alubia de riñón", "alubia moteada", "alubia escarlata", "alubia borlotti", "alubia navy",

  # Frutos secos y semillas
  "almendras", "avellanas", "nueces", "nueces de Brasil", "nueces de macadamia", "piñones", "pistachos", "anacardos",
  "cacahuetes", "pipas de calabaza", "pipas de girasol", "semillas de sésamo", "semillas de chía", "linaza",
  "semillas de lino", "semillas de amapola", "semillas de cáñamo", "semillas de alcaravea", "semillas de hinojo",
  "semillas de mostaza", "semillas de albahaca", "semillas de comino", "semillas de coriandro", "semillas de anís",
  "semillas de cardamomo", "semillas de nigella", "semillas de fenogreco", "semillas de ajonjolí negro",

  # Granos, cereales y tubérculos
  "trigo", "avena", "cebada", "centeno", "arroz", "maíz", "alforfón", "amaranto", "teff", "mijo", "quinoa",
  "espelta", "kamut", "sorgo", "farro", "freekeh", "bulgur", "candeal", "arroz salvaje", "moniato", "tupinambo"
]

            consumidos = [v for v in vegetales_objetivo if v in alimentos_semana]
            progreso = len(consumidos)
            total = 30

            bloques_llenos = "🟩" * progreso
            bloques_vacios = "⬜" * (total - progreso)

            # Mostrar progreso único con cuadritos
            total_objetivo = 30
            progreso = len(alimentos_semana)
            bloques_llenos = "🟩" * progreso
            bloques_vacios = "⬜" * (total_objetivo - progreso)

            st.markdown("### 🌿 Diversidad vegetal esta semana")
            st.markdown(f"{bloques_llenos}{bloques_vacios}")

        except Exception as e:
            st.info("No se pudo calcular la diversidad vegetal aún.")

            # Lista completa de vegetales (puedes expandirla)
            vegetales_objetivo = [
                "acelga", "apio", "berenjena", "brócoli", "calabacín", "calabaza", "cardo", "cebolla", "cebolleta", "col blanca", "col de Bruselas", "col lombarda", "col rizada (kale)", "coliflor", "endibia", "escarola", "espárrago", "espinaca", "hinojo", "judía verde", "lechuga romana", "lechuga iceberg", "nabo", "pepino", "pimiento rojo", "pimiento verde", "puerro", "rábano", "remolacha", "tomate", "zanahoria", "alcachofa", "chirivía", "boniato (batata)", "patata", "ñame", "taro", "malanga", "yuca", "okra", "pak choi", "berza", "acedera", "mostaza verde", "diente de león (hojas)", "berro", "canónigos", "mizuna", "tatsoi", "escarola rizada",
"manzana", "pera", "plátano", "naranja", "mandarina", "kiwi", "uva", "granada", "fresa", "frambuesa", "mora", "arándano", "cereza", "melocotón", "albaricoque", "ciruela", "mango", "papaya", "piña", "melón", "sandía", "higo", "caqui", "lichi", "maracuyá", "guayaba", "chirimoya", "carambola", "níspero", "pomelo", "lima", "limón", "coco", "aguacate", "tomate cherry", "grosella", "zarzamora", "mandarino", "plátano macho", "dátil",
"almendra", "avellana", "nuez", "nuez de Brasil", "nuez de macadamia", "pistacho", "anacardo", "cacahuete", "pipa de girasol", "pipa de calabaza", "semilla de sésamo", "semilla de chía", "semilla de lino", "semilla de amapola", "semilla de cáñamo", "semilla de alcaravea", "semilla de hinojo", "semilla de mostaza", "semilla de albahaca", "semilla de comino", "semilla de coriandro", "semilla de anís", "semilla de cardamomo", "semilla de nigella", "semilla de fenogreco", "semilla de ajonjolí negro", "semilla de calabaza tostada", "semilla de girasol tostada", "semilla de lino dorado", "semilla de chía blanca",
"lenteja", "garbanzo", "judía blanca", "judía roja", "judía negra", "habas", "guisantes", "soja", "azuki", "mungo", "lupino", "alubia pinta", "alubia canela", "alubia carilla", "alubia de Lima", "alubia de riñón", "alubia moteada", "alubia escarlata", "alubia borlotti", "alubia navy",
"trigo integral", "avena", "cebada", "centeno", "arroz integral", "maíz", "quinoa", "amaranto", "mijo", "teff", "alforfón (trigo sarraceno)", "espelta", "kamut", "sorgo", "farro", "freekeh", "trigo bulgur", "trigo candeal", "trigo sarraceno tostado (kasha)", "arroz salvaje",
"champiñón", "shiitake", "maitake", "gírgola (ostra)", "enoki", "portobello", "rebozuelo", "trompeta de la muerte", "seta de cardo", "seta de chopo", "seta de pie azul", "seta de pino", "seta de haya", "seta de álamo", "seta de abedul", "seta de roble", "seta de caoba", "seta de castaño", "seta de aliso", "seta de fresno",
"albahaca", "perejil", "cilantro", "menta", "hierbabuena", "romero", "tomillo", "orégano", "salvia", "estragón", "eneldo", "cebollino", "laurel", "mejorana", "ajedrea", "lemongrass", "curry (hojas)", "hoja de lima kaffir", "hoja de laurel indio",
"ajo crudo", "cebolla cruda", "alcachofa de Jerusalén", "plátano verde", "achicoria", "diente de león (hojas y raíz)", "raíz de yacón", "salvado de trigo", "manzana con piel", "patata cocida y enfriada"
            ]

            # Leer los alimentos únicos consumidos esta semana
            def cargar_datos():
                try:
                    df = pd.read_csv("data/habitos.csv", header=None, encoding="utf-8-sig")
                    df.columns = ["fecha", "comida", "sueno", "ejercicio", "animo"] + list(categorias.keys())
                    df["fecha"] = pd.to_datetime(df["fecha"], errors='coerce')
                    return df
                except Exception as e:
                    st.warning(f"No se pudo cargar el archivo CSV: {e}")
                    return pd.DataFrame()

            df = cargar_datos()

            # Filtrar solo desde el lunes
            inicio_semana = datetime.now() - timedelta(days=datetime.now().weekday())
            df_semana = df[df["fecha"] >= inicio_semana]

            # Agrupar todos los alimentos
            alimentos_semana = set()
            for entry in df_semana["comida"].dropna():
                for alimento in entry.split(","):
                    alimentos_semana.add(alimento.strip().lower())

            consumidos = [v for v in vegetales_objetivo if v in alimentos_semana]
            faltantes = [v for v in vegetales_objetivo if v not in alimentos_semana]

            total = 30
            progreso = len(consumidos)
            bloques_llenos = "🟩" * progreso
            bloques_vacios = "⬜" * (total - progreso)

            st.markdown(f"### 🌱 Diversidad vegetal semanal")
            st.markdown(f"**{progreso}/30 vegetales distintos esta semana**")
            st.markdown(f"{bloques_llenos}{bloques_vacios}")

            if faltantes:
                with st.expander("Ver vegetales que aún puedes añadir"):
                    st.write(", ".join(faltantes))

        except Exception as e:
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

        # Faltantes importantes
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

    # Mostrar gráfico de categorías ✅/❌ por semana
    suma_cat = df_semana[list(categorias.keys())].sum()
    st.bar_chart(suma_cat)

    # Contar diversidad de alimentos vegetales (únicos)
    alimentos_semana = set()
    for entry in df_semana["comida"]:
        for alimento in entry.split(","):
            alimentos_semana.add(alimento.strip().lower())

    st.markdown(f"🌿 Esta semana has consumido **{len(alimentos_semana)} / 30** vegetales distintos.")
else:
    st.info("Aún no hay datos registrados esta semana.")
