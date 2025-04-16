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

st.set_page_config(page_title="NutriBioMind", layout="centered")
st.title("🌱 La regla de oro: ¡30 plantas distintas por semana!")

# --- Inicialización de credenciales ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["gcp_service_account"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

# --- Conectar a Google Sheets ---
def get_sheet():
    client = gspread.authorize(creds)
    return client.open("habitos_microbiota").sheet1

# --- Datos de categorías (resumido) ---
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

grupos_vegetales = list(categorias.keys())
vegetales_validos = set([item.lower() for sub in categorias.values() for item in sub])
todos_alimentos = sorted({item for sub in categorias.values() for item in sub})

# --- Guardar registro diario ---
def guardar_registro(sheet, fecha, seleccionados, sueno, ejercicio, animo):
    fecha_str = fecha.strftime('%Y-%m-%d')
    vegetales_dia = {i.lower() for i in seleccionados if i.lower() in vegetales_validos}
    diversidad_diaria = len(vegetales_dia)
    if len(sheet.get_all_values()) == 0:
        sheet.append_row(["fecha", "comida", "sueno", "ejercicio", "animo", "diversidad_diaria", "tipo"])
    sheet.append_row([
        fecha_str, ", ".join(seleccionados), sueno, ejercicio, animo, diversidad_diaria, "registro"
    ])
    if fecha.weekday() == 0:
        guardar_resumen_semanal(sheet, fecha)

# --- Guardar resumen semanal ---
def guardar_resumen_semanal(sheet, fecha):
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    inicio_semana = fecha - timedelta(days=7)
    semana_df = df[(df["fecha"] >= inicio_semana) & (df["tipo"] == "registro")]
    vegetales_semana = set()
    for entrada in semana_df["comida"].dropna():
        vegetales_semana.update([i.strip().lower() for i in entrada.split(",") if i.strip().lower() in vegetales_validos])
    diversidad_semanal = len(vegetales_semana)
    ya_hay = df[(df["fecha"] == fecha) & (df["tipo"] == "resumen")]
    if ya_hay.empty:
        sheet.append_row([fecha.strftime('%Y-%m-%d'), "", "", "", "", diversidad_semanal, "resumen"])

# --- Visualización y análisis ---
def mostrar_registros(df):
    st.markdown("---")
    st.subheader("📅 Vegetales únicos por día")
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    for fecha, grupo in df.groupby("fecha"):
        diarios = set()
        for entrada in grupo["comida"].dropna():
            diarios.update([i.strip().lower() for i in entrada.split(",") if i.strip().lower() in vegetales_validos])
        st.markdown(f"📆 **{fecha}**: {len(diarios)} vegetales: {', '.join(sorted(diarios))}")

    st.markdown("---")
    st.subheader("🌿 Diversidad vegetal semanal")
    inicio_semana = datetime.now().date() - timedelta(days=datetime.now().weekday())
    df_semana = df[df["fecha"] >= inicio_semana]
    vegetales_semana = set()
    for entrada in df_semana["comida"].dropna():
        vegetales_semana.update([i.strip().lower() for i in entrada.split(",") if i.strip().lower() in vegetales_validos])
    progreso = len(vegetales_semana)
    st.markdown(f"Esta semana has comido **{progreso} / 30** vegetales diferentes.")
    st.progress(progreso / 30)
    sugerencias = sorted(list(vegetales_validos - vegetales_semana))[:5]
    st.subheader("💡 Sugerencias para hoy")
    if sugerencias:
        st.markdown("🌟 Prueba algo nuevo: " + ", ".join(sugerencias))
    else:
        st.success("🎉 ¡Ya has probado 30 vegetales distintos esta semana!")

    # --- Visualizaciones Plotly ---
    if not df.empty:
        df_vis = df[df['tipo'] == 'registro'].copy()
        df_vis["fecha"] = pd.to_datetime(df_vis["fecha"])
        st.subheader("📊 Gráfico: Ánimo vs. Sueño")
        fig = px.scatter(df_vis, x="sueno", y="animo", hover_data=["fecha", "comida"])
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📈 Diversidad por día")
        fig2 = px.line(df_vis, x="fecha", y="diversidad_diaria")
        st.plotly_chart(fig2, use_container_width=True)

        # --- ML: Regresión para predecir ánimo ---
        st.subheader("🤖 Predicción de Ánimo (ML)")
        X = df_vis[["sueno"]].fillna(0)
        y = df_vis["animo"]
        if len(X) > 3:
            model = LinearRegression().fit(X, y)
            st.markdown(f"Coeficiente sueño: {model.coef_[0]:.2f} — Intercepto: {model.intercept_:.2f}")

        # --- ML: Clustering perfiles ---
        st.subheader("👥 Clusters de Usuarios")
        features = df_vis[["diversidad_diaria", "sueno"]].dropna()
        if len(features) >= 3:
            kmeans = KMeans(n_clusters=2, n_init='auto').fit(features)
            df_vis["cluster"] = kmeans.labels_
            fig3 = px.scatter(df_vis, x="diversidad_diaria", y="sueno", color="cluster", hover_data=["fecha"])
            st.plotly_chart(fig3, use_container_width=True)

        # --- Export CSV ---
        st.subheader("📤 Exportar datos")
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        st.download_button("⬇️ Descargar CSV", buffer.getvalue(), file_name="registro_nutribio.csv", mime="text/csv")

# --- Main App ---
def main():
    sheet = get_sheet()
    with st.form("registro"):
        st.subheader("📋 Registro diario")
        seleccionados = st.multiselect("¿Qué comiste hoy?", options=todos_alimentos)
        sueno = st.number_input("¿Horas de sueño?", min_value=0.0, max_value=24.0, step=0.5)
        ejercicio = st.text_input("¿Ejercicio realizado?")
        animo = st.slider("¿Cómo te sientes hoy?", 1, 5, 3)
        submitted = st.form_submit_button("Guardar")
        if submitted:
            fecha = datetime.now().date()
            guardar_registro(sheet, fecha, seleccionados, sueno, ejercicio, animo)
            st.success("✅ Registro y diversidad guardados correctamente.")

    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty:
            mostrar_registros(df)
    except Exception as e:
        st.warning(f"No se pudieron cargar los datos: {e}")

if __name__ == "__main__":
    main()


