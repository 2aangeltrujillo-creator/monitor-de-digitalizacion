import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
from io import StringIO
import unicodedata

# ----------------- CONFIG BÁSICA -----------------
st.set_page_config(page_title="Monitor Digital Municipal", layout="wide")

# Estilo matplotlib
plt.rcParams.update({
    "figure.facecolor": "#ffffff",
    "axes.facecolor": "#f9fafb",
    "axes.edgecolor": "#e5e7eb",
    "axes.grid": True,
    "grid.color": "#e5e7eb",
    "grid.linestyle": "--",
    "grid.alpha": 0.6,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
})


# ----------------- ESTILO CUSTOM (CSS) -----------------
def set_custom_style():
    st.markdown(
        """
        <style>
        /* Fuente y espaciado general */
        html, body, [class*="css"]  {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 1.5rem;
            max-width: 1200px;
        }

        /* Sidebar estilo institucional (azul oscuro) */
        [data-testid="stSidebar"] {
            background: #020617;
            border-right: 1px solid #1f2937;
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] li {
            color: #e5e7eb !important;
        }

        [data-testid="stSidebar"] hr {
            border-color: #1f2937;
        }

        /* Tarjetas KPI */
        .kpi-card {
            padding: 0.6rem 0.9rem;
            border-radius: 0.9rem;
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
        }

        .kpi-title {
            font-size: 0.78rem;
            color: #6b7280;
            margin-bottom: 0.15rem;
        }

        .kpi-value {
            font-size: 1.4rem;
            font-weight: 600;
            color: #111827;
        }

        /* Separadores suaves */
        .soft-divider {
            margin: 0.8rem 0 0.4rem 0;
            border-top: 1px solid #e5e7eb;
        }

        /* Título principal estilo “USS” */
        .main-title h1 {
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
            background: linear-gradient(90deg, #0b1120, #1d4ed8);
            -webkit-background-clip: text;
            color: transparent;
        }

        .main-title p {
            margin-top: 0;
            color: #6b7280;
            font-size: 0.98rem;
        }

        /* --- FIX PARA MODO OSCURO --- */
        @media (prefers-color-scheme: dark) {
            .main-title h1 {
                /* Cambiamos a Blanco -> Azul Claro para que resalte sobre negro */
                background: linear-gradient(90deg, #f8fafc, #60a5fa);
                -webkit-background-clip: text;
                color: transparent;
            }
            .main-title p {
                color: #cbd5e1; /* Subtítulo más claro */
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


set_custom_style()

# ----------------- CONSTANTES -----------------
P34_COLOR = "#1d4ed8"   # azul institucional
P19_COLOR = "#0f766e"   # verde sobrio
NO_COLOR   = "#b91c1c"  # rojo más oscuro

PREGUNTAS_PRINCIPALES = ["P10", "P11", "P12"]
BLOQUE_P19 = [f"P19.{i}" for i in range(1, 12)]


# ----------------- HELPERS -----------------
def render_kpi(title: str, value: str):
    """Dibuja una tarjeta KPI sin usar st.metric (así no aparece la barra fea)."""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def quitar_acentos(texto):
    if not isinstance(texto, str):
        texto = str(texto)
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def normalizar_clave_comuna(txt):
    if not isinstance(txt, str):
        txt = str(txt)
    txt = quitar_acentos(txt).upper()
    for prefix in ["ILUSTRE MUNICIPALIDAD DE ", "MUNICIPALIDAD DE ", "MUNICIPALIDAD "]:
        txt = txt.replace(prefix, "")
    txt = txt.replace(" ", "").replace("-", "").replace("'", "")
    return txt.strip()


def clasificar_nivel(valor):
    if valor <= 3:
        return "Bajo (Iniciando)"
    elif valor <= 7:
        return "Medio (En desarrollo)"
    else:
        return "Alto (Avanzado)"


def prettify_columns(df, extra_map=None):
    base_map = {
        "MUNICIPALIDAD": "Municipalidad",
        "region_nombre": "Región",
        "Nivel_Madurez": "Nivel de madurez",
        "indice_digitalizacion": "Índice de digitalización (P34)",
        "P19_promedio": "Digitalización interna (P19)",
    }
    if extra_map:
        base_map.update(extra_map)
    return df.rename(columns=base_map)


def abreviar_muni(nombre, max_len=16):
    s = str(nombre)
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def binarizar(df_cols):
    df_num = df_cols.apply(pd.to_numeric, errors="coerce")
    df_num = df_num.where(df_num.isin([0, 1]), 0)
    return df_num.fillna(0).astype(int)


def make_pie(df_view, col, label_si, label_no):
    if col not in df_view.columns:
        st.caption(f"{col} no está disponible en la base.")
        return
    si = int(df_view[col].sum())
    no = int(len(df_view) - si)
    if si + no == 0:
        st.caption(f"Sin datos suficientes para {col} en esta vista.")
        return
    fig, ax = plt.subplots(figsize=(3.6, 3.6))
    ax.pie(
        [si, no],
        labels=[label_si, label_no],
        autopct="%1.0f%%",
        colors=[P19_COLOR, NO_COLOR],
        textprops={"fontsize": 8},
    )
    ax.axis("equal")
    st.pyplot(fig)


def explorar_bloque(df_region, comuna_sel, tipo, cols_p34=None):
    """Explorador genérico para P19 y P34 (reduce código repetido)."""
    if tipo == "P19":
        col_val = "P19_promedio"
        titulo_tabla = "bloque P19"
        titulo_valor = "P19 promedio"
        ylabel = "P19 promedio (0 a 1)"
        color = P19_COLOR
        cap_top = "Se muestran las {n} comunas con mayor P19 promedio para legibilidad."
        cap_reg = "P19 promedio resume las funciones declaradas del área informática."
        cap_com = "Si la barra de la comuna supera el promedio regional, declara más funciones de TI que la media."
    else:
        col_val = "indice_digitalizacion"
        titulo_tabla = "bloque P34"
        titulo_valor = "Índice de digitalización (P34)"
        ylabel = "Índice de digitalización (suma P34.x)"
        color = P34_COLOR
        cap_top = "Se muestran las {n} comunas con mayor índice P34 para legibilidad."
        cap_reg = "El índice P34 indica en cuántas áreas municipales existen sistemas de administración."
        cap_com = "La comparación muestra si la comuna está sobre o bajo el promedio regional en cobertura de sistemas."

    if comuna_sel == "Todas las comunas":
        st.markdown(f"#### Tabla de comunas de la región ({titulo_tabla})")
        df_tab = df_region[["MUNICIPALIDAD", "Nivel_Madurez", "indice_digitalizacion", "P19_promedio"]]
        st.dataframe(prettify_columns(df_tab).sort_values("Municipalidad"))

        st.markdown(f"#### Comparación de comunas según {titulo_valor}")
        df_plot = df_region.sort_values(col_val, ascending=False)
        max_munis = 20
        if len(df_plot) > max_munis:
            df_plot = df_plot.head(max_munis)
            st.caption(cap_top.format(n=max_munis))

        df_plot["Etiqueta"] = df_plot["MUNICIPALIDAD"].apply(abreviar_muni)
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.barh(df_plot["Etiqueta"], df_plot[col_val], color=color)
        ax.set_xlabel(ylabel)
        ax.set_ylabel("Municipio")
        ax.invert_yaxis()
        st.pyplot(fig)
        st.caption(cap_reg)
        return

    df_comuna = df_region[df_region["MUNICIPALIDAD"] == comuna_sel]
    if df_comuna.empty:
        st.warning("No se encontró información para la comuna seleccionada.")
        return

    row = df_comuna.iloc[0]
    st.markdown(f"#### Ficha comunal – {titulo_tabla}")

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        render_kpi("Comuna", comuna_sel)
    with col_b:
        render_kpi("Región", row["region_nombre"])
    with col_c:
        render_kpi("Nivel de madurez", row["Nivel_Madurez"])
    with col_d:
        val_str = f"{row[col_val]:.2f}" if tipo == "P19" else f"{row[col_val]:.0f}"
        render_kpi(titulo_valor, val_str)

    st.markdown('<hr class="soft-divider">', unsafe_allow_html=True)

    media_reg = df_region[col_val].mean()
    st.write(
        f"Comparación de la comuna **{comuna_sel}** con el promedio de la región "
        f"**{row['region_nombre']}** ({titulo_tabla})."
    )

    fig, ax = plt.subplots()
    ax.bar(
        ["Comuna seleccionada", "Promedio regional"],
        [row[col_val], media_reg],
        color=[color, "#9ca3af"],
    )
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    st.pyplot(fig)
    st.caption(cap_com)

    if tipo == "P34" and cols_p34:
        st.markdown("---")
        st.write("Sistemas por área municipal (P34.x) activos en la comuna seleccionada")

        detalle_p34 = df_comuna[cols_p34].T.reset_index()
        detalle_p34.columns = ["Pregunta", "Valor"]
        detalle_p34 = detalle_p34[detalle_p34["Valor"] > 0]

        if detalle_p34.empty:
            st.info("La comuna no declara sistemas activos en P34.x.")
            return

        detalle_p34["Etiqueta"] = (
            detalle_p34["Pregunta"]
            .str.replace("P34", "", regex=False)
            .str.replace("_", " ", regex=False)
            .str.strip()
        )

        max_items_det = 20
        if len(detalle_p34) > max_items_det:
            detalle_p34 = detalle_p34.head(max_items_det)
            st.caption(
                f"Se muestran los primeros {max_items_det} ítems de P34.x activados para esta comuna."
            )

        fig6, ax6 = plt.subplots(figsize=(10, 4))
        ax6.bar(detalle_p34["Etiqueta"], detalle_p34["Valor"], color=P34_COLOR)
        ax6.set_xticklabels(detalle_p34["Etiqueta"], rotation=90)
        ax6.set_ylabel("Presencia del sistema (1 = presente)")
        ax6.grid(axis="y", linestyle="--", alpha=0.4)
        st.pyplot(fig6)
        st.caption("Cada ítem P34.x corresponde a un área específica con sistema de administración.")


# ----------------- CARGA DE DATOS -----------------
@st.cache_data(show_spinner=False)
def cargar_datos():
    url_csv = "https://datos.gob.cl/datastore/dump/a6e3cfd1-08d7-4221-abb8-ee6d766a4820?bom=True"
    try:
        r = requests.get(url_csv, timeout=30)
        r.raise_for_status()
        try:
            content = r.content.decode("utf-8")
        except UnicodeDecodeError:
            content = r.content.decode("latin1", errors="ignore")
        df = pd.read_csv(StringIO(content), low_memory=False)
    except Exception:
        return pd.DataFrame(), [], [], []

    def get_api(endpoint):
        try:
            r = requests.get(
                f"https://apis.digital.gob.cl/dpa/{endpoint}",
                headers={"User-Agent": "Mozilla"},
                timeout=5,
            )
            if r.status_code == 200:
                return pd.DataFrame(r.json())
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    comunas = get_api("comunas")
    provincias = get_api("provincias")
    regiones = get_api("regiones")

    df["Comuna_clave"] = df["MUNICIPALIDAD"].apply(normalizar_clave_comuna)

    if not comunas.empty:
        comunas = comunas.rename(
            columns={
                "codigo": "codigo_comuna",
                "codigo_padre": "codigo_provincia",
                "nombre": "nombre_comuna",
            }
        )
        comunas["Comuna_clave"] = comunas["nombre_comuna"].apply(normalizar_clave_comuna)

        provincias = provincias.rename(
            columns={"codigo": "codigo_provincia", "codigo_padre": "codigo_region"}
        )
        regiones = regiones.rename(
            columns={"codigo": "codigo_region", "nombre": "region_nombre"}
        )

        full_geo = comunas.merge(provincias, on="codigo_provincia").merge(
            regiones, on="codigo_region"
        )

        df = df.merge(
            full_geo[["Comuna_clave", "region_nombre"]].drop_duplicates(),
            on="Comuna_clave",
            how="left",
        )
        df["region_nombre"] = df["region_nombre"].fillna("Desconocida")

        # Parche manual
        comuna_region_codigo = {
            "SANTIAGO": "13",
            "LLAYLLAY": "05",
            "LACALERA": "05",
            "MARCHIGUE": "06",
            "TREHUACO": "16",
            "PAIHUANO": "04",
            "OHIGGINS": "11",
        }
        if not regiones.empty:
            for clave_comuna, cod_region in comuna_region_codigo.items():
                nombre_region = regiones.loc[
                    regiones["codigo_region"] == cod_region, "region_nombre"
                ]
                if not nombre_region.empty:
                    df.loc[df["Comuna_clave"] == clave_comuna, "region_nombre"] = nombre_region.iloc[0]
    else:
        df["region_nombre"] = "Sin clasificar"

    cols_binarias = [p for p in PREGUNTAS_PRINCIPALES if p in df.columns]
    if cols_binarias:
        df[cols_binarias] = (
            df[cols_binarias].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
        )

    cols_p19 = [p for p in BLOQUE_P19 if p in df.columns]
    if cols_p19:
        p19_bin = binarizar(df[cols_p19])
        df[cols_p19] = p19_bin
        df["P19_promedio"] = p19_bin.mean(axis=1)
    else:
        df["P19_promedio"] = 0.0

    cols_p34 = [c for c in df.columns if c.startswith("P34")]
    if cols_p34:
        p34_bin = binarizar(df[cols_p34])
        df[cols_p34] = p34_bin
        df["indice_digitalizacion"] = p34_bin.sum(axis=1)
    else:
        df["indice_digitalizacion"] = 0

    df["Nivel_Madurez"] = df["indice_digitalizacion"].apply(clasificar_nivel)

    return df, cols_binarias, cols_p19, cols_p34


with st.spinner("Conectando con datos.gob.cl..."):
    df, cols_main, cols_p19, cols_p34 = cargar_datos()

if df.empty:
    st.error("No fue posible cargar los datos. Verifica tu conexión y vuelve a intentar.")
    st.stop()

df_base = df.copy()
regiones_validas = sorted(
    [r for r in df_base["region_nombre"].dropna().unique().tolist()
     if r not in ("Desconocida", "Sin clasificar")]
)

# ----------------- SIDEBAR -----------------
st.sidebar.title("Dirección de variables")

with st.sidebar.expander("General", expanded=False):
    st.markdown(
        """
- **P10 – Sitio web institucional** (0 = No, 1 = Sí).  
- **P11 – Redes sociales** (0 = No, 1 = Sí).  
- **P12 – Trámites en línea** (1 = ofrece en línea, 0 = solo presencial).  
- **Nivel de madurez digital**: se construye a partir del índice P34 (Bajo / Medio / Alto).
"""
    )

with st.sidebar.expander("Bloque P19 – ¿Qué mide cada punto?", expanded=False):
    st.markdown(
        """
**P19.x** indica funciones del área informática (0 = No, 1 = Sí).  
En los gráficos se consideran, por ejemplo:

- **P19.1**: adquisiciones TIC (equipos, sistemas, licencias).  
- **P19.2**: infraestructura, redes y comunicaciones.  
- **P19.3**: sistemas de información y bases de datos.  
- **P19.4**: sitio web institucional.  
- **P19.5**: mantención de equipos y sistemas.  
- **P19.6**: soporte técnico / mesa de ayuda.  
- **P19.7**: desarrollo o mejora de aplicaciones.  
- **P19.8**: capacitación en servicios en línea.  
- **P19.9**: mejora de procesos con TI.  
- **P19.10**: terminales de autoservicio u otros canales digitales.

**P19 promedio** es el promedio de estas funciones (entre 0 y 1).
"""
    )

with st.sidebar.expander("Bloque P34 – ¿Qué mide cada punto?", expanded=False):
    st.markdown(
        """
**P34.x** indica sistemas de administración en áreas municipales (0 = No, 1 = Sí).  
En los gráficos se consideran, por ejemplo:

- **P34.1**: presupuesto y contabilidad.  
- **P34.2**: finanzas y tesorería.  
- **P34.3**: personal y remuneraciones.  
- **P34.4**: adquisiciones / abastecimiento.  
- **P34.5**: obras municipales.  
- **P34.6**: área social / desarrollo comunitario.  
- **P34.7**: patentes y derechos municipales.  
- **P34.8**: tránsito y permisos de circulación.  
- **P34.9**: juzgado de policía local.  
- **P34.10**: educación municipal.  
- **P34.11**: salud municipal.  
- **P34.12**: planificación (SECPLAN) u otras áreas técnicas.

El **índice de digitalización (P34)** es la suma de las P34.x activas en cada municipio.
"""
    )

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
**Fuentes de datos y APIs utilizadas**

- CSV encuesta de digitalización:  
  https://datos.gob.cl/datastore/dump/a6e3cfd1-08d7-4221-abb8-ee6d766a4820  
- API División Político Administrativa (DPA):  
  https://apis.digital.gob.cl/dpa
"""
)

# ----------------- CUERPO PRINCIPAL -----------------
st.markdown(
    """
<div class="main-title">
  <h1>Monitor de Digitalización Municipal</h1>
  <p>Visualización del nivel de digitalización de las municipalidades de Chile</p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
- **Panorama general**: resumen por región, indicadores clave y niveles de madurez.  
- **Comparaciones avanzadas**: promedios regionales, relación P19–P34 y ranking de municipios.  
- **Explorador regional y comunal**: detalle por región y comuna para P19 y P34.
"""
)

tab1, tab2, tab3 = st.tabs(
    ["Panorama general", "Comparaciones avanzadas", "🔍 Explorador regional y comunal"]
)

# ---------- TAB 1 ----------
with tab1:
    st.subheader("Panorama general por región")

    regiones_pg = ["Todo el país"] + regiones_validas
    region_pg_sel = st.selectbox("Región a visualizar", regiones_pg, key="pg_region")

    df_view_pg = df_base.copy()
    if region_pg_sel != "Todo el país":
        df_view_pg = df_view_pg[df_view_pg["region_nombre"] == region_pg_sel]

    if df_view_pg.empty:
        st.warning("No hay municipios para la combinación de filtros seleccionada.")
    else:
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        with col_kpi1:
            render_kpi("Municipios en la vista", f"{len(df_view_pg):,}")
        with col_kpi2:
            render_kpi(
                "Servicios digitales promedio (P34)",
                f"{df_view_pg['indice_digitalizacion'].mean():.1f}",
            )
        with col_kpi3:
            render_kpi(
                "Digitalización interna promedio (P19)",
                f"{df_view_pg['P19_promedio'].mean():.2f}",
            )
        with col_kpi4:
            render_kpi(
                "Municipios con alta madurez",
                f"{int((df_view_pg['Nivel_Madurez'] == 'Alto (Avanzado)').sum()):,}",
            )

        st.caption(
            "P19 resume las funciones del área informática y P34 la existencia de sistemas por área municipal; "
            "con P34 se construye el índice de madurez digital."
        )

        st.markdown('<hr class="soft-divider">', unsafe_allow_html=True)

        if region_pg_sel != "Todo el país":
            st.write("Servicios digitales por municipio de la región seleccionada (índice P34).")
        else:
            st.write("Servicios digitales por municipio (índice P34, muestra limitada).")

        df_plot = df_view_pg.sort_values("indice_digitalizacion", ascending=False)
        max_munis = 20
        if len(df_plot) > max_munis:
            df_plot = df_plot.head(max_munis)
            st.caption(
                f"Se muestran los {max_munis} municipios con mayor índice de digitalización "
                "para mantener la legibilidad del gráfico."
            )

        df_plot["Etiqueta"] = df_plot["MUNICIPALIDAD"].apply(abreviar_muni)
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.barh(df_plot["Etiqueta"], df_plot["indice_digitalizacion"], color=P34_COLOR)
        ax.set_xlabel("Índice de digitalización (suma P34.x)")
        ax.set_ylabel("Municipio")
        ax.invert_yaxis()
        st.pyplot(fig)

        st.markdown('<hr class="soft-divider">', unsafe_allow_html=True)
        st.write("Presencia de sitio web, redes sociales y trámites en línea (P10, P11, P12).")

        col_p10, col_p11, col_p12 = st.columns(3)
        with col_p10:
            make_pie(df_view_pg, "P10", "Con sitio web", "Sin sitio web")
        with col_p11:
            make_pie(df_view_pg, "P11", "Usan redes sociales", "No usan redes")
        with col_p12:
            make_pie(df_view_pg, "P12", "Ofrecen trámites en línea", "Solo presencial")

        st.markdown('<hr class="soft-divider">', unsafe_allow_html=True)
        st.write("Distribución de niveles de madurez digital (a partir del índice P34).")
        madurez_counts = df_view_pg["Nivel_Madurez"].value_counts().reindex(
            ["Alto (Avanzado)", "Medio (En desarrollo)", "Bajo (Iniciando)"],
            fill_value=0,
        )
        fig3, ax3 = plt.subplots()
        ax3.bar(
            madurez_counts.index,
            madurez_counts.values,
            color=[P19_COLOR, "#f97316", "#94a3b8"],
        )
        ax3.set_ylabel("Cantidad de municipios")
        st.pyplot(fig3)

# ---------- TAB 2 ----------
with tab2:
    st.subheader("Comparaciones avanzadas")
    st.markdown(
        "Promedios regionales, relación entre digitalización interna (P19) y cobertura de sistemas (P34), "
        "y ranking de municipios según índice P34."
    )

    if df_base.empty:
        st.warning("No hay datos disponibles.")
    else:
        sub_reg, sub_rel, sub_rank = st.tabs(
            ["Promedios por región", "Relación P19–P34", "Ranking de municipios"]
        )

        with sub_reg:
            st.markdown("### Promedio por región")
            variable_opciones = {
                "Índice de digitalización (P34)": "indice_digitalizacion",
                "Digitalización interna promedio (P19)": "P19_promedio",
            }
            var_label_reg = st.selectbox(
                "Variable a visualizar por región",
                list(variable_opciones.keys()),
                key="adv_var_region",
            )
            var_col_reg = variable_opciones[var_label_reg]

            df_reg_filt = df_base[df_base["region_nombre"].isin(regiones_validas)].copy()
            grp_reg = df_reg_filt.groupby("region_nombre")[var_col_reg].mean().sort_values()

            fig7, ax7 = plt.subplots(figsize=(10, 6))
            color_sel = P34_COLOR if var_col_reg == "indice_digitalizacion" else P19_COLOR
            grp_reg.plot(kind="barh", ax=ax7, color=color_sel)
            ax7.set_xlabel(var_label_reg)
            ax7.set_ylabel("Región")
            st.pyplot(fig7)

        with sub_rel:
            st.markdown("### Relación entre P19 promedio y P34 según nivel de madurez")
            niveles_orden = ["Bajo (Iniciando)", "Medio (En desarrollo)", "Alto (Avanzado)"]
            colores_nivel = {
                "Bajo (Iniciando)": "#f97316",
                "Medio (En desarrollo)": "#eab308",
                "Alto (Avanzado)": "#22c55e",
            }

            fig9, ax9 = plt.subplots(figsize=(7, 5))
            for nivel in niveles_orden:
                sub = df_base[df_base["Nivel_Madurez"] == nivel]
                if not sub.empty:
                    ax9.scatter(
                        sub["P19_promedio"],
                        sub["indice_digitalizacion"],
                        label=nivel,
                        alpha=0.7,
                        s=40,
                        color=colores_nivel[nivel],
                        marker="o",
                        edgecolors="black",
                        linewidths=0.5,
                    )
            ax9.set_xlabel("Digitalización interna (P19 promedio)")
            ax9.set_ylabel("Índice de digitalización (P34)")
            ax9.grid(True, linestyle="--", alpha=0.4)
            ax9.legend(title="Nivel de madurez")
            st.pyplot(fig9)

            corr_val = df_base["P19_promedio"].corr(df_base["indice_digitalizacion"])
            if pd.notna(corr_val):
                st.caption(
                    f"La correlación entre P19 promedio y el índice P34 es aproximadamente {corr_val:.2f} "
                    "(1 indica relación positiva fuerte, 0 ausencia de relación)."
                )

        with sub_rank:
            st.markdown("### Ranking de municipios según índice de digitalización (P34)")
            ambitos_rank = ["Todo el país"] + regiones_validas
            ambito_sel = st.selectbox(
                "Ámbito del ranking", ambitos_rank, key="rank_scope"
            )

            df_rank = df_base[
                ["MUNICIPALIDAD", "region_nombre", "indice_digitalizacion", "Nivel_Madurez"]
            ].copy()
            if ambito_sel != "Todo el país":
                df_rank = df_rank[df_rank["region_nombre"] == ambito_sel]

            if df_rank.empty:
                st.info("No hay municipios en el ámbito seleccionado.")
            else:
                df_rank_display = prettify_columns(df_rank).sort_values(
                    "Índice de digitalización (P34)", ascending=False
                ).reset_index(drop=True)
                st.dataframe(df_rank_display)

# ---------- TAB 3 ----------
with tab3:
    st.subheader("🔍 Explorador regional y comunal")
    st.markdown(
        "Selecciona una región y luego una comuna (o todas) para explorar los bloques **P19** y **P34**."
    )

    region_sel = st.selectbox("Región", regiones_validas, key="expl_region")
    df_region = df_base[df_base["region_nombre"] == region_sel]

    if df_region.empty:
        st.warning("No hay municipios en la región seleccionada.")
    else:
        comunas_opts = ["Todas las comunas"] + sorted(
            df_region["MUNICIPALIDAD"].dropna().unique().tolist()
        )
        comuna_sel = st.selectbox("Comuna", comunas_opts, key="expl_comuna")

        sub_p19, sub_p34 = st.tabs(
            ["Bloque P19 – Digitalización interna", "Bloque P34 – Servicios digitales"]
        )

        with sub_p19:
            st.markdown(
                "El bloque **P19** muestra el grado de desarrollo de las funciones del área informática."
            )
            explorar_bloque(df_region, comuna_sel, "P19")

        with sub_p34:
            st.markdown(
                "El bloque **P34** muestra en cuántas áreas municipales existen sistemas de administración."
            )
            explorar_bloque(df_region, comuna_sel, "P34", cols_p34=cols_p34)
