import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import os
import glob
import uuid
import time
import streamlit.components.v1 as components
import math
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Track Dashboard", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# --- ESTILOS CSS (DISEÑO PREMIUM OSCURO) ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {background-color: transparent !important;}
    
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; font-weight: 400; }
    h1, h2, h3, h4, h5, h6 { font-weight: 500 !important; color: #e8e8f0 !important; }
    p, label { color: #9090b0 !important; }
    
    div[data-testid="stVerticalBlockBorderWrapper"] { border: 0.5px solid #1e1e2e !important; background-color: #111120 !important; border-radius: 8px !important; }
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div, div[data-baseweb="calendar"] { background-color: #0d0d18 !important; border: 0.5px solid #1e1e2e !important; border-radius: 8px !important; }
    
    button[kind="primary"] { background: linear-gradient(135deg, #7c3aed, #a855f7) !important; border: none !important; color: white !important; font-weight: 500 !important; border-radius: 6px !important; }
    button[kind="secondary"] { background-color: #0d0d14 !important; border: 0.5px solid #1e1e2e !important; color: #a78bfa !important; }
    
    div[data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 500 !important; color: #e8e8f0 !important; }
    div[data-testid="stMetricDelta"] svg { display: none; }
    
    .live-preview { background-color: #0d0d14; border: 1px solid #1e1e2e; border-radius: 8px; padding: 15px; margin-bottom: 15px; color: #a78bfa; text-align: center; font-weight: 500; }
    .food-card { background-color: #0d0d14; border-left: 3px solid #7c3aed; padding: 10px 15px; border-radius: 4px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
    .run-card { background-color: #0d0d14; border-left: 3px solid #fc4c02; padding: 15px; border-radius: 6px; margin-bottom: 15px; }
    .set-row-done { background-color: rgba(34, 197, 94, 0.1); border-left: 3px solid #22c55e; padding: 8px 15px; border-radius: 4px; margin-bottom: 5px; color: #e8e8f0; display: flex; justify-content: space-between; }
    .splits-box { background-color: #0d0d18; border: 1px solid #1e1e2e; padding: 10px; border-radius: 6px; margin-top: 10px; font-size: 13px; color: #a78bfa; }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# --- CONEXIÓN A SUPABASE ---
# ============================================================
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_supabase()

# ============================================================
# --- FUNCIONES DE BASE DE DATOS (reemplazan los CSV) ---
# ============================================================

def db_leer(tabla: str) -> pd.DataFrame:
    """Lee todos los registros de una tabla de Supabase."""
    try:
        res = supabase.table(tabla).select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            if 'fecha' in df.columns:
                df['fecha'] = pd.to_datetime(df['fecha']).dt.date
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error leyendo {tabla}: {e}")
        return pd.DataFrame()

def db_insertar(tabla: str, datos: dict):
    """Inserta un registro en Supabase."""
    try:
        # Convertir fechas a string para JSON
        datos_limpios = {}
        for k, v in datos.items():
            if isinstance(v, datetime.date):
                datos_limpios[k] = v.isoformat()
            elif isinstance(v, float) and math.isnan(v):
                datos_limpios[k] = None
            else:
                datos_limpios[k] = v
        supabase.table(tabla).insert(datos_limpios).execute()
    except Exception as e:
        st.error(f"Error insertando en {tabla}: {e}")

def db_borrar(tabla: str, campo: str, valor):
    """Borra un registro por su campo identificador."""
    try:
        supabase.table(tabla).delete().eq(campo, valor).execute()
    except Exception as e:
        st.error(f"Error borrando en {tabla}: {e}")

def db_borrar_fecha(tabla: str, fecha):
    """Borra todos los registros de una fecha concreta."""
    try:
        supabase.table(tabla).delete().eq('fecha', fecha.isoformat()).execute()
    except Exception as e:
        st.error(f"Error borrando fecha en {tabla}: {e}")

def db_upsert_actividad(fecha, pasos, deportes_detalle, kcal_actividad, mantenimiento_total):
    """Actualiza o crea el registro de actividad del día."""
    try:
        supabase.table('historial_actividad').upsert({
            'fecha': fecha.isoformat(),
            'pasos': pasos,
            'deportes_detalle': deportes_detalle,
            'kcal_actividad': int(kcal_actividad),
            'mantenimiento_total': int(mantenimiento_total)
        }, on_conflict='fecha').execute()
    except Exception as e:
        st.error(f"Error actualizando actividad: {e}")

def db_upsert_nutricion(fecha, kcal, proteina, carbos, grasas, detalle):
    """Actualiza o crea el registro nutricional del día."""
    try:
        supabase.table('historial_nutricion').upsert({
            'fecha': fecha.isoformat(),
            'kcal_consumidas': int(kcal),
            'proteina': int(proteina),
            'carbos': int(carbos),
            'grasas': int(grasas),
            'detalle_comidas': detalle
        }, on_conflict='fecha').execute()
    except Exception as e:
        st.error(f"Error actualizando nutrición: {e}")

def db_upsert_metrica(fecha, peso, grasa):
    """Actualiza o crea una métrica corporal."""
    try:
        supabase.table('historial_metricas').upsert({
            'fecha': fecha.isoformat(),
            'peso_kg': float(peso),
            'grasa_pct': float(grasa)
        }, on_conflict='fecha').execute()
    except Exception as e:
        st.error(f"Error guardando métrica: {e}")

# ============================================================
# --- FUNCIONES AUXILIARES ---
# ============================================================

def formato_ritmo(min_float):
    try:
        m = int(min_float)
        s = int(round((min_float - m) * 60))
        if s == 60: m += 1; s = 0
        return f"{m}:{s:02d}"
    except: return "0:00"

def formato_tiempo(min_float):
    try:
        h = int(min_float // 60)
        m = int(min_float % 60)
        s = int(round((min_float - int(min_float)) * 60))
        if s == 60: m += 1; s = 0
        if h > 0: return f"{h}h {m:02d}m {s:02d}s"
        return f"{m:02d}m {s:02d}s"
    except: return "00m 00s"

@st.cache_data(ttl=3600)
def cargar_supermercado_csv():
    """Carga el catálogo de alimentos desde Supabase."""
    try:
        res = supabase.table('catalogo_alimentos').select("*").execute()
        if res.data:
            return pd.DataFrame(res.data)
        return pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def cargar_ejercicios_csv():
    """Carga el catálogo de ejercicios desde Supabase."""
    try:
        res = supabase.table('catalogo_ejercicios').select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            return df[['grupo_muscular', 'ejercicio']].dropna().drop_duplicates()
        return pd.DataFrame(columns=['grupo_muscular', 'ejercicio'])
    except:
        return pd.DataFrame(columns=['grupo_muscular', 'ejercicio'])

df_supermercado = cargar_supermercado_csv()
df_ejercicios = cargar_ejercicios_csv()

# ============================================================
# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
# ============================================================
hoy = datetime.date.today()

if 'datos_diarios' not in st.session_state:
    df = db_leer('historial_metricas')
    if not df.empty:
        df = df.rename(columns={'peso_kg': 'Peso (kg)', 'grasa_pct': 'Grasa (%)', 'fecha': 'Fecha'})
    st.session_state['datos_diarios'] = df

if 'historial_act' not in st.session_state:
    st.session_state['historial_act'] = db_leer('historial_actividad')

if 'historial_entrenamientos' not in st.session_state:
    st.session_state['historial_entrenamientos'] = db_leer('historial_entrenamientos')

if 'historial_running' not in st.session_state:
    df_r = db_leer('historial_running')
    if not df_r.empty:
        for col in ['distancia', 'tiempo_min', 'ritmo']:
            if col in df_r.columns:
                df_r[col] = pd.to_numeric(df_r[col], errors='coerce').fillna(0.0)
        if 'bpm' in df_r.columns:
            df_r['bpm'] = pd.to_numeric(df_r['bpm'], errors='coerce')
        if 'sensacion' in df_r.columns:
            df_r['sensacion'] = pd.to_numeric(df_r['sensacion'], errors='coerce').fillna(7).astype(int)
    st.session_state['historial_running'] = df_r

# Recuperar pasos y calorías del día de hoy
df_act_memoria = st.session_state['historial_act']
df_act_hoy = df_act_memoria[df_act_memoria['fecha'] == hoy] if not df_act_memoria.empty and 'fecha' in df_act_memoria.columns else pd.DataFrame()

if 'pasos_hoy' not in st.session_state:
    st.session_state['pasos_hoy'] = int(df_act_hoy['pasos'].iloc[0]) if not df_act_hoy.empty else 0
if 'gasto_total_hoy' not in st.session_state:
    st.session_state['gasto_total_hoy'] = int(df_act_hoy['mantenimiento_total'].iloc[0]) if not df_act_hoy.empty else 2500

# Recuperar comidas del día de hoy
if 'comidas_hoy' not in st.session_state:
    df_cd = db_leer('historial_comidas_detalle')
    if not df_cd.empty and 'fecha' in df_cd.columns:
        st.session_state['comidas_hoy'] = df_cd[df_cd['fecha'] == hoy].to_dict('records')
    else:
        st.session_state['comidas_hoy'] = []

# Recuperar deportes del día de hoy
if 'deportes_hoy' not in st.session_state:
    df_dep = db_leer('historial_cardio_detalle')
    if not df_dep.empty and 'fecha' in df_dep.columns:
        st.session_state['deportes_hoy'] = df_dep[df_dep['fecha'] == hoy].to_dict('records')
    else:
        st.session_state['deportes_hoy'] = []

if 'entrenamiento_activo' not in st.session_state:
    st.session_state['entrenamiento_activo'] = False
    st.session_state['hora_inicio_entreno'] = None
    st.session_state['rutina_activa'] = []

# Reset de medianoche
if 'dia_actual' not in st.session_state:
    st.session_state['dia_actual'] = hoy
if st.session_state['dia_actual'] != hoy:
    st.session_state['deportes_hoy'] = []
    st.session_state['comidas_hoy'] = []
    st.session_state['rutina_activa'] = []
    st.session_state['entrenamiento_activo'] = False
    st.session_state['pasos_hoy'] = 0
    st.session_state['dia_actual'] = hoy

# ============================================================
# --- MENÚ LATERAL ---
# ============================================================
with st.sidebar:
    st.markdown("### ⚡ Panel de Control")
    opciones_menu = ["📊 Dashboard Diario", "🍎 Nutrición y Dieta", "🏋️ Entrenamiento (Hevy)", "🏃‍♂️ Running (Strava)", "⚖️ Registrar Métricas", "📸 Evolución Visual"]
    opcion = st.radio("Menú", opciones_menu, label_visibility="collapsed")
    st.markdown("---")

# ============================================================
# --- PANTALLA 1: DASHBOARD ---
# ============================================================
if opcion == "📊 Dashboard Diario":
    st.markdown("###### Resumen Diario y Gasto Calórico")
    st.markdown("<br>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("#### 🚶‍♂️ Movimiento Base")
        pasos = st.number_input("Pasos acumulados hoy", min_value=0, step=1000, key="pasos_hoy")

        st.markdown("---")
        st.markdown("#### 🏃‍♂️ Añadir Cardio / Deportes Extra")
        col_d1, col_d2, col_d3 = st.columns([1.5, 1, 1])
        with col_d1: tipo_entreno = st.selectbox("Deporte", ["Fútbol", "Tenis", "Natación", "Ciclismo", "Pádel"])
        with col_d2: minutos = st.number_input("Tiempo (min)", min_value=1, value=60, step=5)
        with col_d3:
            st.write(""); st.write("")
            btn_add = st.button("➕ Añadir Actividad", use_container_width=True)

        if btn_add:
            mets = {"Fútbol": 9.0, "Tenis": 7.5, "Pádel": 8.0, "Natación": 9.0, "Ciclismo": 8.0}
            calorias_entreno = minutos * mets.get(tipo_entreno, 7.0)  # BUG CORREGIDO: minutos (no minutes)
            nuevo_dep = {
                "id_unico": str(uuid.uuid4()),
                "fecha": hoy.isoformat(),
                "deporte": tipo_entreno,
                "minutos": minutos,
                "calorias": int(calorias_entreno)
            }
            db_insertar('historial_cardio_detalle', nuevo_dep)
            st.session_state['deportes_hoy'].append(nuevo_dep)
            st.rerun()

        if st.session_state['deportes_hoy']:
            st.markdown("##### 📋 Actividades de hoy:")
            for dep in st.session_state['deportes_hoy']:
                col_info, col_del = st.columns([4, 1])
                with col_info:
                    st.info(f"✔️ **{dep.get('deporte', dep.get('Deporte',''))}** ({dep.get('minutos', dep.get('Minutos',''))} min) → {dep.get('calorias', dep.get('Calorías', 0))} kcal")
                with col_del:
                    if st.button("❌", key=f"del_{dep['id_unico']}"):
                        db_borrar('historial_cardio_detalle', 'id_unico', dep['id_unico'])
                        st.session_state['deportes_hoy'] = [d for d in st.session_state['deportes_hoy'] if d['id_unico'] != dep['id_unico']]
                        st.rerun()

    tmb = (10 * 85.0) + (6.25 * 185) - (5 * 22) + 5
    calorias_pasos = pasos * 0.04
    total_calorias_deportes = sum(d.get('calorias', d.get('Calorías', 0)) for d in st.session_state['deportes_hoy'])
    gasto_total = tmb + calorias_pasos + total_calorias_deportes
    st.session_state['gasto_total_hoy'] = gasto_total

    detalle_deportes = " | ".join([f"{d.get('deporte','?')} ({d.get('minutos','?')}m)" for d in st.session_state['deportes_hoy']]) or "Ninguno"
    db_upsert_actividad(hoy, pasos, detalle_deportes, calorias_pasos + total_calorias_deportes, gasto_total)

    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1: st.metric("🔥 Mantenimiento Total", f"{int(gasto_total)} kcal")
    with col_kpi2: st.metric("⚙️ Tasa Basal (TMB)", f"{int(tmb)} kcal")
    with col_kpi3: st.metric("👟 Gasto Extra", f"{int(calorias_pasos + total_calorias_deportes)} kcal")

    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### 📈 Evolución Histórica")
        df_plot = st.session_state['datos_diarios']
        if df_plot.empty:
            st.info("Aún no has registrado ningún peso.")
        else:
            df_plot = df_plot.sort_values(by="Fecha") if 'Fecha' in df_plot.columns else df_plot.sort_values(by="fecha")
            fecha_col = 'Fecha' if 'Fecha' in df_plot.columns else 'fecha'
            peso_col = 'Peso (kg)' if 'Peso (kg)' in df_plot.columns else 'peso_kg'
            grasa_col = 'Grasa (%)' if 'Grasa (%)' in df_plot.columns else 'grasa_pct'
            colores_grasa = ['#FF4B4B' if val > 18 else '#00C853' for val in df_plot[grasa_col]]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_plot[fecha_col], y=df_plot[peso_col], name='Peso (kg)', mode='lines+markers', line=dict(color='#7c3aed', width=3), marker=dict(size=6)))
            fig.add_trace(go.Scatter(x=df_plot[fecha_col], y=df_plot[grasa_col], name='% Grasa', mode='lines+markers', line=dict(color='rgba(255,255,255,0.2)', width=2, dash='dot'), marker=dict(color=colores_grasa, size=10, line=dict(width=1, color='white'))))
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(showgrid=False, color='#FAFAFA'), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color='#FAFAFA'), hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# ============================================================
# --- PANTALLA 2: NUTRICIÓN ---
# ============================================================
elif opcion == "🍎 Nutrición y Dieta":
    st.markdown("## 🍎 Ingesta Diaria")
    if df_supermercado.empty:
        st.error("⚠️ No se encontró el catálogo de alimentos en la base de datos.")
    else:
        cat_col = 'categoria' if 'categoria' in df_supermercado.columns else 'Categoría'
        ali_col = 'alimento' if 'alimento' in df_supermercado.columns else 'Alimento'
        kcal_col = 'kcal_100g' if 'kcal_100g' in df_supermercado.columns else 'Kcal_100g'
        prot_col = 'proteina_100g' if 'proteina_100g' in df_supermercado.columns else 'Proteina_100g'
        carb_col = 'carbos_100g' if 'carbos_100g' in df_supermercado.columns else 'Carbos_100g'
        gras_col = 'grasas_100g' if 'grasas_100g' in df_supermercado.columns else 'Grasas_100g'

        with st.container(border=True):
            st.markdown("#### 🍽️ Buscador de Alimentos")
            col_cat, col_alim, col_gr = st.columns([1.5, 2, 1])
            with col_cat:
                lista_categorias = sorted(df_supermercado[cat_col].astype(str).unique().tolist())
                categoria_sel = st.selectbox("1️⃣ Categoría", lista_categorias)
            with col_alim:
                lista_alimentos_filtrada = df_supermercado[df_supermercado[cat_col] == categoria_sel][ali_col].tolist()
                alimento_sel = st.selectbox("2️⃣ Alimento", sorted(lista_alimentos_filtrada))
            with col_gr:
                gramos = st.number_input("⚖️ Gramos", min_value=1.0, value=100.0, step=10.0)

            if alimento_sel:
                datos = df_supermercado[df_supermercado[ali_col] == alimento_sel].iloc[0]
                factor = gramos / 100.0
                k_live = datos[kcal_col] * factor
                p_live = datos[prot_col] * factor
                c_live = datos[carb_col] * factor
                g_live = datos[gras_col] * factor
                st.markdown(f"<div class='live-preview'>⚡ <b>{gramos}g de {alimento_sel}</b> aportan: <span style='color:#e8e8f0; font-size:18px; margin-left:10px;'>{int(k_live)} kcal</span> | 🥩 {int(p_live)}g P | 🍚 {int(c_live)}g C | 🥑 {int(g_live)}g G</div>", unsafe_allow_html=True)

            if st.button("➕ Registrar Ingesta", type="primary", use_container_width=True):
                nueva_comida = {
                    "id_unico": str(uuid.uuid4()),
                    "fecha": hoy.isoformat(),
                    "alimento": alimento_sel,
                    "gramos": float(gramos),
                    "kcal": float(k_live),
                    "proteina": float(p_live),
                    "carbos": float(c_live),
                    "grasas": float(g_live)
                }
                db_insertar('historial_comidas_detalle', nueva_comida)
                st.session_state['comidas_hoy'].append(nueva_comida)
                st.rerun()

        tot_kcal = sum(c.get('kcal', c.get('Kcal', 0)) for c in st.session_state['comidas_hoy'])
        tot_prot = sum(c.get('proteina', c.get('Proteina', 0)) for c in st.session_state['comidas_hoy'])
        tot_carb = sum(c.get('carbos', c.get('Carbos', 0)) for c in st.session_state['comidas_hoy'])
        tot_gras = sum(c.get('grasas', c.get('Grasas', 0)) for c in st.session_state['comidas_hoy'])
        mantenimiento = st.session_state.get('gasto_total_hoy', 2500)
        balance = tot_kcal - mantenimiento

        detalle_comidas = " | ".join([f"{c.get('alimento', c.get('Alimento',''))} ({c.get('gramos', c.get('Gramos',''))}g)" for c in st.session_state['comidas_hoy']])
        db_upsert_nutricion(hoy, tot_kcal, tot_prot, tot_carb, tot_gras, detalle_comidas)

        st.markdown("<br>", unsafe_allow_html=True)
        col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
        with col_kpi1: st.metric("🔥 Calorías Consumidas", f"{int(tot_kcal)} kcal", delta=f"{int(balance)} kcal (Balance)", delta_color="inverse")
        with col_kpi2: st.metric("🥩 Proteínas Totales", f"{int(tot_prot)} g")
        with col_kpi3: st.metric("🍚 Carbos / 🥑 Grasas", f"{int(tot_carb)} g / {int(tot_gras)} g")

        if st.session_state['comidas_hoy']:
            st.markdown("#### 🍽️ Diario de hoy")
            with st.container(border=True):
                for com in st.session_state['comidas_hoy']:
                    nombre = com.get('alimento', com.get('Alimento', ''))
                    gr = com.get('gramos', com.get('Gramos', 0))
                    kc = com.get('kcal', com.get('Kcal', 0))
                    pr = com.get('proteina', com.get('Proteina', 0))
                    ca = com.get('carbos', com.get('Carbos', 0))
                    ga = com.get('grasas', com.get('Grasas', 0))
                    col_info, col_del = st.columns([8, 1])
                    with col_info:
                        st.markdown(f"<div class='food-card'><div><b>{nombre}</b> ({gr}g)</div><div style='color:#9090b0; font-size:14px;'>{int(kc)} kcal | P: {int(pr)} | C: {int(ca)} | G: {int(ga)}</div></div>", unsafe_allow_html=True)
                    with col_del:
                        st.write("")
                        if st.button("❌", key=f"del_comida_{com['id_unico']}"):
                            db_borrar('historial_comidas_detalle', 'id_unico', com['id_unico'])
                            st.session_state['comidas_hoy'] = [c for c in st.session_state['comidas_hoy'] if c['id_unico'] != com['id_unico']]
                            st.rerun()

# ============================================================
# --- PANTALLA 3: ENTRENAMIENTO ---
# ============================================================
elif opcion == "🏋️ Entrenamiento (Hevy)":

    if not st.session_state['entrenamiento_activo']:
        st.markdown("## 🏋️ Iniciar Entrenamiento")
        if st.button("▶️ Empezar Sesión Vacía", type="primary", use_container_width=True):
            st.session_state['entrenamiento_activo'] = True
            st.session_state['hora_inicio_entreno'] = time.time()
            st.session_state['rutina_activa'] = []
            st.rerun()
    else:
        start_ts = st.session_state['hora_inicio_entreno']
        components.html(f"""
            <div style='text-align: center; background-color: #0d0d18; padding: 15px; border-radius: 8px; border: 1px solid #7c3aed; font-family: sans-serif;'>
                <p style='margin:0; font-size:14px; color:#a78bfa; font-weight: bold;'>ENTRENAMIENTO EN CURSO</p>
                <h2 style='color: #e8e8f0; margin:5px 0 0 0; font-size: 32px;' id='timer'>00:00</h2>
            </div>
            <script>
                var start = {start_ts} * 1000;
                setInterval(function() {{
                    var now = new Date().getTime();
                    var diff = Math.floor((now - start) / 1000);
                    var h = Math.floor(diff / 3600);
                    var m = Math.floor((diff % 3600) / 60).toString().padStart(2, '0');
                    var s = (diff % 60).toString().padStart(2, '0');
                    document.getElementById('timer').innerText = (h > 0 ? h + ":" : "") + m + ":" + s;
                }}, 1000);
            </script>
        """, height=110)

        st.markdown("<br>", unsafe_allow_html=True)
        col_fin1, col_fin2 = st.columns([3, 1])
        with col_fin1:
            if st.button("⏹️ FINALIZAR Y GUARDAR ENTRENAMIENTO", use_container_width=True):
                nuevas_series = []
                for ej in st.session_state['rutina_activa']:
                    for s_idx, serie in enumerate(ej['series']):
                        nuevas_series.append({
                            'fecha': hoy.isoformat(),
                            'grupo': ej['grupo'],
                            'ejercicio': ej['nombre'],
                            'serie': s_idx + 1,
                            'repeticiones': serie['reps'],
                            'peso': serie['peso']
                        })
                if nuevas_series:
                    for s in nuevas_series:
                        db_insertar('historial_entrenamientos', s)
                    # Recargar historial
                    st.session_state['historial_entrenamientos'] = db_leer('historial_entrenamientos')
                    minutos_totales = (time.time() - start_ts) / 60.0
                    calorias_gym = minutos_totales * 5.5
                    nuevo_dep = {
                        "id_unico": str(uuid.uuid4()),
                        "fecha": hoy.isoformat(),
                        "deporte": "Pesas (Gym)",
                        "minutos": int(minutos_totales),
                        "calorias": int(calorias_gym)
                    }
                    db_insertar('historial_cardio_detalle', nuevo_dep)
                    st.session_state['deportes_hoy'].append(nuevo_dep)
                    st.session_state['entrenamiento_activo'] = False
                    st.session_state['rutina_activa'] = []
                    st.success("¡Entrenamiento guardado!")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.warning("⚠️ Añade alguna serie antes de finalizar.")
        with col_fin2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state['entrenamiento_activo'] = False
                st.session_state['rutina_activa'] = []
                st.rerun()

        st.markdown("---")
        for ej_idx, ej in enumerate(st.session_state['rutina_activa']):
            with st.container(border=True):
                col_title, col_del_ej = st.columns([8, 1])
                with col_title: st.markdown(f"<h4 style='color:#7c3aed; margin:0;'>{ej['nombre']}</h4>", unsafe_allow_html=True)
                with col_del_ej:
                    if st.button("🗑️", key=f"del_ej_{ej['id']}"):
                        st.session_state['rutina_activa'].pop(ej_idx)
                        st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)
                for s_idx, serie in enumerate(ej['series']):
                    st.markdown(f"<div class='set-row-done'><span><b>S{s_idx + 1}</b></span><span>{serie['reps']} reps</span><span>{serie['peso']} kg</span><span>✔️</span></div>", unsafe_allow_html=True)
                col_r, col_p, col_add = st.columns([1, 1, 1])
                with col_r:
                    default_reps = ej['series'][-1]['reps'] if ej['series'] else 10
                    reps_input = st.number_input("Reps", min_value=1, value=default_reps, key=f"r_{ej['id']}")
                with col_p:
                    default_peso = float(ej['series'][-1]['peso']) if ej['series'] else 20.0
                    peso_input = st.number_input("Kg", min_value=0.0, value=default_peso, step=2.5, key=f"p_{ej['id']}")
                with col_add:
                    st.write(""); st.write("")
                    if st.button("✔️ Añadir", type="secondary", use_container_width=True, key=f"btn_add_{ej['id']}"):
                        ej['series'].append({"reps": reps_input, "peso": peso_input})
                        st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("➕ Añadir Ejercicio a la rutina"):
            if df_ejercicios.empty:
                st.error("No se encontró el catálogo de ejercicios.")
            else:
                grp_col = 'grupo_muscular' if 'grupo_muscular' in df_ejercicios.columns else 'Grupo Muscular'
                ej_col = 'ejercicio' if 'ejercicio' in df_ejercicios.columns else 'Ejercicio (Equipamiento)'
                col_eg1, col_eg2 = st.columns(2)
                with col_eg1:
                    lista_grupos = sorted(df_ejercicios[grp_col].unique().tolist())
                    grupo_sel = st.selectbox("Grupo Muscular", lista_grupos, key="sel_g")
                with col_eg2:
                    lista_ejs = sorted(df_ejercicios[df_ejercicios[grp_col] == grupo_sel][ej_col].tolist())
                    ejercicio_sel = st.selectbox("Ejercicio", lista_ejs, key="sel_e")

                df_hist = st.session_state['historial_entrenamientos']
                if not df_hist.empty:
                    ej_col_hist = 'ejercicio' if 'ejercicio' in df_hist.columns else 'Ejercicio'
                    fecha_col_hist = 'fecha' if 'fecha' in df_hist.columns else 'Fecha'
                    hist_filtrado = df_hist[df_hist[ej_col_hist] == ejercicio_sel]
                    if not hist_filtrado.empty:
                        ultima_fecha = hist_filtrado[fecha_col_hist].max()
                        series_pasadas = hist_filtrado[hist_filtrado[fecha_col_hist] == ultima_fecha]
                        rep_col = 'repeticiones' if 'repeticiones' in series_pasadas.columns else 'Repeticiones'
                        pes_col = 'peso' if 'peso' in series_pasadas.columns else 'Peso'
                        texto_pasado = " | ".join([f"{int(row[rep_col])}x{row[pes_col]}kg" for _, row in series_pasadas.iterrows()])
                        st.info(f"⏱️ **Última vez:** {texto_pasado}")

                if st.button("Añadir a mi sesión", type="primary"):
                    st.session_state['rutina_activa'].append({"id": str(uuid.uuid4()), "nombre": ejercicio_sel, "grupo": grupo_sel, "series": []})
                    st.rerun()

# ============================================================
# --- PANTALLA 4: RUNNING ---
# ============================================================
elif opcion == "🏃‍♂️ Running (Strava)":
    st.markdown("## 🏃‍♂️ Diario de Carrera (Strava Mode)")

    with st.container(border=True):
        st.markdown("#### ⏱️ Registrar Nueva Carrera")
        col_f, col_d, col_t1, col_t2 = st.columns(4)
        with col_f: fecha_run = st.date_input("Fecha", hoy)
        with col_d: dist_run = st.number_input("Distancia (km)", min_value=0.1, value=5.0, step=0.1)
        with col_t1: min_run = st.number_input("Minutos Totales", min_value=0, value=25, step=1)
        with col_t2: sec_run = st.number_input("Segundos Totales", min_value=0, max_value=59, value=0, step=1)

        col_p, col_s = st.columns(2)
        with col_p:
            bpm_run = st.number_input("Pulsaciones (BPM) - Opcional", min_value=40, max_value=250, value=None, step=1, placeholder="Ej: 150")
        with col_s:
            sensacion = st.slider("Sensaciones y Esfuerzo (1 = Suave, 10 = Máximo)", 1, 10, 7)

        splits_guardar = ""
        km_enteros = int(dist_run)
        if km_enteros >= 1:
            with st.expander("⏱️ Desglosar Ritmo por Kilómetro (Splits)"):
                st.write("Apunta el tiempo de cada kilómetro:")
                lista_splits = []
                for k in range(1, km_enteros + 1):
                    col_sk, col_sm, col_ss = st.columns([1, 2, 2])
                    col_sk.write(f"**Km {k}**")
                    sm = col_sm.number_input("Min", min_value=0, max_value=59, value=5, key=f"s_m_{k}", label_visibility="collapsed")
                    ss = col_ss.number_input("Seg", min_value=0, max_value=59, value=0, key=f"s_s_{k}", label_visibility="collapsed")
                    lista_splits.append(f"{sm}:{ss:02d}")
                splits_guardar = " | ".join([f"Km{i+1}: {sp}" for i, sp in enumerate(lista_splits)])

        if st.button("💾 Guardar Carrera en mi Historial", type="primary", use_container_width=True):
            tiempo_total_min = min_run + (sec_run / 60.0)
            ritmo_calc = tiempo_total_min / dist_run if dist_run > 0 else 0
            nuevo_run = {
                "id_unico": str(uuid.uuid4()),
                "fecha": fecha_run.isoformat(),
                "distancia": float(dist_run),
                "tiempo_min": float(tiempo_total_min),
                "ritmo": float(ritmo_calc),
                "bpm": int(bpm_run) if bpm_run is not None else None,
                "sensacion": int(sensacion),
                "splits": splits_guardar
            }
            db_insertar('historial_running', nuevo_run)
            nuevo_run['fecha'] = fecha_run
            st.session_state['historial_running'] = pd.concat([st.session_state['historial_running'], pd.DataFrame([nuevo_run])], ignore_index=True)

            if fecha_run == hoy:
                peso_actual = 85.0
                if not st.session_state['datos_diarios'].empty:
                    df_m = st.session_state['datos_diarios']
                    peso_col = 'Peso (kg)' if 'Peso (kg)' in df_m.columns else 'peso_kg'
                    fecha_col_m = 'Fecha' if 'Fecha' in df_m.columns else 'fecha'
                    peso_actual = df_m.sort_values(fecha_col_m, ascending=False).iloc[0][peso_col]
                multiplicador = 1 + ((sensacion - 5) * 0.05)
                kcal_run = int((dist_run * peso_actual) * multiplicador)
                nuevo_dep_run = {
                    "id_unico": str(uuid.uuid4()),
                    "fecha": hoy.isoformat(),
                    "deporte": f"Running {dist_run}km",
                    "minutos": int(tiempo_total_min),
                    "calorias": kcal_run
                }
                db_insertar('historial_cardio_detalle', nuevo_dep_run)
                st.session_state['deportes_hoy'].append(nuevo_dep_run)

            st.success("¡Carrera registrada con éxito!")
            st.rerun()

    df_run = st.session_state['historial_running']
    if not df_run.empty:
        carreras_validas = df_run[pd.to_numeric(df_run['distancia'], errors='coerce').fillna(0) >= 1.0]
        if not carreras_validas.empty:
            mejor_carrera = carreras_validas.loc[pd.to_numeric(carreras_validas['ritmo'], errors='coerce').idxmin()]
            T1 = float(mejor_carrera['tiempo_min'])
            D1 = float(mejor_carrera['distancia'])
            pred_5k = T1 * ((5.0 / D1) ** 1.06)
            pred_10k = T1 * ((10.0 / D1) ** 1.06)
            pred_21k = T1 * ((21.0975 / D1) ** 1.06)

            st.markdown("#### 🔮 Predicciones de Rendimiento (Algoritmo Riegel)")
            st.info(f"💡 Mejor carrera: **{D1}km** a **{formato_ritmo(float(mejor_carrera['ritmo']))} min/km**")
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                with st.container(border=True): st.metric("🎯 5K", formato_tiempo(pred_5k))
            with col_p2:
                with st.container(border=True): st.metric("🎯 10K", formato_tiempo(pred_10k))
            with col_p3:
                with st.container(border=True): st.metric("🎯 Media Maratón", formato_tiempo(pred_21k))

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 👟 Tu Historial de Carreras")
        df_hist_ord = df_run.sort_values(by="fecha", ascending=False)
        for _, run in df_hist_ord.iterrows():
            with st.container(border=True):
                bpm_text = ""
                if pd.notna(run.get('bpm')) and str(run.get('bpm', '')).strip() not in ('', 'nan', 'None'):
                    try: bpm_text = f"❤️ {int(float(run['bpm']))} ppm &nbsp;|&nbsp; "
                    except: pass
                st.markdown(f"""
                <div class="run-card">
                    <div style="width: 100%;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div><b style="color:#fc4c02; font-size:18px;">{run['distancia']} km</b> &nbsp;&nbsp;|&nbsp;&nbsp; {run['fecha']}</div>
                            <div>⏱️ {formato_tiempo(float(run['tiempo_min']))} &nbsp;&nbsp;|&nbsp;&nbsp; ⚡ {formato_ritmo(float(run['ritmo']))} /km</div>
                        </div>
                        <div style="margin-top:10px; color:#9090b0;">
                            <span>{bpm_text}🔋 Esfuerzo: {run['sensacion']}/10</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if run.get('splits') and str(run.get('splits', '')).strip() not in ('', 'nan'):
                    st.markdown(f"<div class='splits-box'><b>⏱️ Parciales:</b> {run['splits']}</div>", unsafe_allow_html=True)
                col_spc, col_del = st.columns([9, 1])
                with col_del:
                    if st.button("❌", key=f"del_run_{run['id_unico']}"):
                        db_borrar('historial_running', 'id_unico', run['id_unico'])
                        st.session_state['historial_running'] = df_run[df_run['id_unico'] != run['id_unico']]
                        st.rerun()
    else:
        st.info("Registra tu primera carrera para que el algoritmo empiece a calcular tus predicciones.")

# ============================================================
# --- PANTALLA 5: MÉTRICAS ---
# ============================================================
elif opcion == "⚖️ Registrar Métricas":
    st.markdown("## ⚖️ Añadir Nuevos Datos")
    col1, col2 = st.columns([1, 1.5])
    with col1:
        with st.container(border=True):
            fecha_registro = st.date_input("📅 Fecha", hoy)
            peso_input = st.number_input("⚖️ Peso (kg)", value=85.0, step=0.1)
            grasa_input = st.number_input("📉 % Grasa", value=14.0, step=0.1)
            if st.button("➕ Guardar Peso", type="primary", use_container_width=True):
                db_upsert_metrica(fecha_registro, peso_input, grasa_input)
                # Actualizar sesión
                df = st.session_state['datos_diarios']
                fecha_col_m = 'Fecha' if 'Fecha' in df.columns else 'fecha'
                if not df.empty:
                    df = df[df[fecha_col_m] != fecha_registro]
                nuevo = pd.DataFrame({'Fecha': [fecha_registro], 'Peso (kg)': [peso_input], 'Grasa (%)': [grasa_input]})
                st.session_state['datos_diarios'] = pd.concat([df, nuevo], ignore_index=True)
                st.success("¡Guardado!")
    with col2:
        with st.container(border=True):
            st.markdown("#### Historial")
            df_m = st.session_state['datos_diarios']
            if df_m.empty:
                st.write("Sin datos.")
            else:
                fecha_col_m = 'Fecha' if 'Fecha' in df_m.columns else 'fecha'
                st.dataframe(df_m.sort_values(by=fecha_col_m, ascending=False).head(15), use_container_width=True, hide_index=True)

# ============================================================
# --- PANTALLA 6: FOTOS ---
# ============================================================
elif opcion == "📸 Evolución Visual":
    st.markdown("## 📸 Archivo Fotográfico")
    st.info("💡 Las fotos se guardan en Supabase Storage. Sube una foto para empezar.")

    with st.container(border=True):
        st.markdown("#### 📤 Subir nueva foto")
        col_sub1, col_sub2 = st.columns(2)
        with col_sub1: fecha_subida = st.date_input("Fecha de captura", hoy, key="fecha_subida")
        with col_sub2: foto_subida = st.file_uploader("Sube la imagen", type=['jpg', 'png', 'jpeg'], label_visibility="collapsed")
        if foto_subida is not None:
            if st.button("Guardar foto", type="primary"):
                try:
                    nombre_archivo = f"foto_{fecha_subida}.jpg"
                    supabase.storage.from_("fotos-progreso").upload(
                        nombre_archivo,
                        foto_subida.getvalue(),
                        {"content-type": "image/jpeg", "upsert": "true"}
                    )
                    st.success("✅ Foto guardada en la nube")
                except Exception as e:
                    st.error(f"Error subiendo foto: {e}")

    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### 📅 Ver Foto de un Día")
        fecha_ver = st.date_input("Selecciona un día", hoy, key="fecha_ver")
        try:
            nombre_archivo = f"foto_{fecha_ver}.jpg"
            url_foto = supabase.storage.from_("fotos-progreso").get_public_url(nombre_archivo)
            st.image(url_foto, caption=f"Físico el {fecha_ver.strftime('%d/%m/%Y')}", width=400)
        except:
            st.info("No hay foto registrada este día.")
