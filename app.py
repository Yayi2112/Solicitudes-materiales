import streamlit as st
import pandas as pd
from PIL import Image
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from streamlit_drawable_canvas import st_canvas

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema de Recepción de Materiales", layout="wide")

# --- USUARIOS Y CLAVES ---
USUARIOS = {
    "admin": {"clave": "1234", "rol": "Administrador"},
    "supervisor": {"clave": "5678", "rol": "Supervisor"}
}

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = ""
if "rol_actual" not in st.session_state:
    st.session_state.rol_actual = ""

# --- ALMACENAMIENTO DE SOLICITUDES EN MEMORIA ---
if 'solicitudes' not in st.session_state:
    st.session_state.solicitudes = {}

# --- PANTALLA DE LOGIN ---
if not st.session_state.autenticado:
    st.title("🔒 Acceso Restringido - Recepción de Materiales")
    col1, _ = st.columns([1, 2])
    with col1:
        user_input = st.text_input("Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        
        if st.button("Iniciar Sesión"):
            user_clean = user_input.strip().lower()
            if user_clean in USUARIOS and USUARIOS[user_clean]["clave"] == pass_input:
                st.session_state.autenticado = True
                st.session_state.usuario_actual = user_clean
                st.session_state.rol_actual = USUARIOS[user_clean]["rol"]
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()

# --- BARRA LATERAL ---
st.sidebar.write(f"👤 Conectado como: **{st.session_state.rol_actual}**")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.session_state.usuario_actual = ""
    st.session_state.rol_actual = ""
    st.rerun()

st.title("📦 Sistema de Recepción y Verificación de Materiales")

# --- MÓDULO DE CARGA (SOLO ADMINISTRADOR) CON LECTURA DE HOJA 2 ---
if st.session_state.rol_actual == "Administrador":
    st.subheader("⚙️ Cargar Nueva Solicitud")
    col_num, col_file = st.columns([1, 2])
    
    with col_num:
        nuevo_num_solicitud = st.text_input("Número de Solicitud / Proyecto:", "1001")
        
    with col_file:
        uploaded_file = st.file_uploader("Cargar lista de materiales (Excel o CSV)", type=["xlsx", "csv"])

    if st.button("Guardar y Publicar Solicitud"):
        if uploaded_file is not None and nuevo_num_solicitud:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    # 1. Intentar leer la Hoja 2 (index 1) sin encabezados para buscar encabezados reales
                    try:
                        df_temp = pd.read_excel(uploaded_file, sheet_name=1, header=None)
                        hoja_usada = 1
                    except Exception:
                        df_temp = pd.read_excel(uploaded_file, sheet_name=0, header=None)
                        hoja_usada = 0

                    # 2. Buscar fila con encabezados reales
                    header_row = 0
                    for idx, row in df_temp.iterrows():
                        row_values = row.astype(str).str.lower().tolist()
                        if any(k in row_values for k in ['item', 'descripción', 'descripcion', 'unidad', 'cantidad', 'oc', 'nv']):
                            header_row = idx
                            break

                    # 3. Leer DataFrame definitivo
                    df = pd.read_excel(uploaded_file, sheet_name=hoja_usada, header=header_row)

                # Limpieza de filas y columnas totalmente vacías
                df = df.dropna(how='all').dropna(how='all', axis=1)

                if 'Verificado' not in df.columns:
                    df['Verificado'] = False
                if 'Observaciones' not in df.columns:
                    df['Observaciones'] = ""

                # Guardar en la estructura de la aplicación
                st.session_state.solicitudes[nuevo_num_solicitud] = {
                    "data": df
                }
                st.success(f"✅ Solicitud N°{nuevo_num_solicitud} guardada correctamente desde la Hoja 2.")
            except Exception as e:
                st.error(f"Error al procesar el archivo: {e}")
        else:
            st.warning("Debe ingresar un número de solicitud y adjuntar un archivo.")

st.divider()

# --- MÓDULO DE SELECCIÓN Y DESPLEGABLE DE SOLICITUDES ---
st.subheader("📋 Solicitudes Disponibles")

lista_solicitudes = list(st.session_state.solicitudes.keys())

if not lista_solicitudes:
    st.info("ℹ️ No hay solicitudes registradas en el sistema. Un Administrador debe cargar una nueva solicitud.")
else:
    solicitud_seleccionada = st.selectbox(
        "Seleccione la solicitud que desea revisar / verificar:",
        options=lista_solicitudes
    )

    if solicitud_seleccionada:
        datos_solicitud = st.session_state.solicitudes[solicitud_seleccionada]
        df_actual = datos_solicitud["data"]

        st.markdown(f"### 📂 Materiales de la Solicitud N° {solicitud_seleccionada}")

        # Tabla editable
        edited_df = st.data_editor(
            df_actual,
            column_config={
                "Verificado": st.column_config.CheckboxColumn("Recibido OK", default=False),
                "Observaciones": st.column_config.TextColumn("Observaciones", default="")
            },
            disabled=[col for col in df_actual.columns if col not in ['Verificado', 'Observaciones']],
            use_container_width=True,
            hide_index=True,
            key=f"editor_{solicitud_seleccionada}"
        )

        st.session_state.solicitudes[solicitud_seleccionada]["data"] = edited_df

        # Avance de verificación
        total_items = len(edited_df)
        items_verificados = edited_df['Verificado'].sum() if 'Verificado' in edited_df.columns else 0
        porcentaje = int((items_verificados / total_items) * 100) if total_items > 0 else 0

        st.progress(porcentaje / 100)
        st.caption(f"Avance de verificación: {porcentaje}% ({items_verificados}/{total_items} ítems)")

        # Alerta visual al llegar al 100%
        if porcentaje == 100:
            st.success(f"🎉 ¡SOLICITUD N° {solicitud_seleccionada} COMPLETADA AL 100%! Todos los materiales han sido verificados.")

        # --- EVIDENCIA Y FIRMAS ---
        st.divider()
        st.subheader("Captura de Evidencia y Firmas")
        col_cam, col_fir1, col_fir2 = st.columns(3)

        with col_cam:
            st.write("**Fotografía de Respaldo**")
            foto = st.camera_input("Tomar foto del material", key=f"cam_{solicitud_seleccionada}")

        with col_fir1:
            st.write("**Firma Revisor / Recepción**")
            canvas_rev = st_canvas(
                stroke_width=2, stroke_color="#000000", background_color="#FFFFFF",
                height=150, width=250, key=f"canvas_rev_{solicitud_seleccionada}"
            )

        with col_fir2:
            st.write("**Firma Bodega / Entrega**")
            canvas_bod = st_canvas(
                stroke_width=2, stroke_color="#000000", background_color="#FFFFFF",
                height=150, width=250, key=f"canvas_bod_{solicitud_seleccionada}"
            )

        # --- GENERADOR DE PDF ---
        st.divider()
        if st.button("📄 Generar Reporte PDF", key=f"pdf_{solicitud_seleccionada}"):
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
            story = []
            styles = getSampleStyleSheet()

            title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor("#003366"), alignment=1)
            story.append(Paragraph(f"REPORTE DE RECEPCIÓN DE MATERIALES - N° {solicitud_seleccionada}", title_style))
            story.append(Spacer(1, 15))

            tabla_data = [["Estado", "Descripción / Ítem", "Observación"]]
            for _, row in edited_df.iterrows():
                estado = "OK" if row.get("Verificado", False) else "PENDIENTE"
                desc = str(row.iloc[0]) if len(row) > 0 else "N/A"
                obs = str(row.get("Observaciones", ""))
                tabla_data.append([estado, desc, obs])

            t = Table(tabla_data, colWidths=[80, 270, 200])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            story.append(t)
            story.append(Spacer(1, 20))

            doc.build(story)
            buffer.seek(0)

            st.download_button(
                label="⬇️ Descargar PDF de Recepción",
                data=buffer,
                file_name=f"Recepcion_Solicitud_{solicitud_seleccionada}.pdf",
                mime="application/pdf"
            )
