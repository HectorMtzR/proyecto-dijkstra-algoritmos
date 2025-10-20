from flask import Flask, render_template, request
import osmnx as ox
import networkx as nx
import folium
import branca # Importamos branca
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import time

app = Flask(__name__)

# --- CARGA DEL GRAFO (SE MANTIENE IGUAL) ---
print("Cargando el grafo de la red vial...")
# ... (El resto de tu código de carga y cálculo de pesos se mantiene exactamente igual)
places = ["Oaxaca de Juárez, Oaxaca", "Santa Cruz Xoxocotlán, Oaxaca", "San Raymundo Jalpan, Oaxaca"]
G = ox.graph_from_place(places, network_type='drive', simplify=True)
print("Calculando pesos de tiempo de viaje...")
VELOCIDAD_ESTANDAR_KMH = 30
KMH_A_MS = 1000 / 3600
for u, v, data in G.edges(data=True):
    longitud_m = data.get('length', 0)
    velocidad_ms = VELOCIDAD_ESTANDAR_KMH * KMH_A_MS
    maxspeed_kmh = data.get('maxspeed')
    if maxspeed_kmh:
        try:
            speed_val = float(maxspeed_kmh[0]) if isinstance(maxspeed_kmh, list) else float(maxspeed_kmh)
            velocidad_ms = speed_val * KMH_A_MS
        except (ValueError, TypeError):
            pass
    data['tiempo_viaje_seg'] = longitud_m / velocidad_ms if velocidad_ms > 0 else float('inf')
print("¡Grafo listo para recibir peticiones!")
# --- FIN DE LA CARGA DEL GRAFO ---


# --- RUTA 1: MAPA DE SELECCIÓN (VERSIÓN FINAL CON CORRECCIÓN DE CONTEXTO) ---
@app.route('/')
def index():
    mapa = folium.Map(location=[17.06, -96.72], zoom_start=14)
    map_name = mapa.get_name()

    # Añadimos 'window.parent' para que el script (dentro del iframe) pueda
    # encontrar los elementos del formulario en la página principal.
    js_code = f"""
    <script>
        function attachClickEvents() {{
            if (window['{map_name}']) {{
                var map = window['{map_name}'];
                var originMarker, destinationMarker;
                var clickCount = 0;

                map.on('click', function(e) {{
                    var coord = e.latlng;
                    
                    if (clickCount === 0) {{
                        // CORRECCIÓN AQUÍ:
                        window.parent.document.getElementById('origen_lat').value = coord.lat;
                        window.parent.document.getElementById('origen_lon').value = coord.lng;
                        
                        if (originMarker) map.removeLayer(originMarker);
                        originMarker = L.marker(coord).addTo(map).bindPopup('<b>Origen</b>').openPopup();
                        
                        // CORRECCIÓN AQUÍ:
                        window.parent.document.getElementById('instruction').innerText = "2. Ahora, selecciona el PUNTO DE DESTINO";
                        clickCount++;

                    }} else if (clickCount === 1) {{
                        // CORRECCIÓN AQUÍ:
                        window.parent.document.getElementById('destino_lat').value = coord.lat;
                        window.parent.document.getElementById('destino_lon').value = coord.lng;

                        if (destinationMarker) map.removeLayer(destinationMarker);
                        destinationMarker = L.marker(coord).addTo(map).bindPopup('<b>Destino</b>').openPopup();

                        // CORRECCIÓN AQUÍ:
                        window.parent.document.getElementById('instruction').innerText = "Calculando ruta...";
                        window.parent.document.getElementById('coordForm').submit();

                        clickCount++;
                    }}
                }});
                console.log("Manejador de clics inicializado con éxito.");
            }} else {{
                setTimeout(attachClickEvents, 50);
            }}
        }}
        attachClickEvents();
    </script>
    """
    
    mapa.get_root().html.add_child(branca.element.Element(js_code))
    mapa_html = mapa._repr_html_()
    
    return render_template('index.html', mapa_html=mapa_html)

# --- RUTA 2: CÁLCULO Y VISUALIZACIÓN (SE MANTIENE IGUAL) ---
@app.route('/ruta', methods=['POST'])
def calcular_ruta():
    # ... (Esta función no necesita ningún cambio)
    resultado = None
    try:
        origen_lat = float(request.form['origen_lat'])
        origen_lon = float(request.form['origen_lon'])
        destino_lat = float(request.form['destino_lat'])
        destino_lon = float(request.form['destino_lon'])
        origen_nodo = ox.nearest_nodes(G, Y=origen_lat, X=origen_lon)
        destino_nodo = ox.nearest_nodes(G, Y=destino_lat, X=destino_lon)
        ruta_optima_nodos = nx.shortest_path(G, source=origen_nodo, target=destino_nodo, weight='tiempo_viaje_seg')
        tiempo_total_min = nx.shortest_path_length(G, source=origen_nodo, target=destino_nodo, weight='tiempo_viaje_seg') / 60
        distancia_total_km = sum(G.edges[u, v, 0]['length'] for u, v in zip(ruta_optima_nodos[:-1], ruta_optima_nodos[1:])) / 1000
        fig, ax = ox.plot_graph_route(G, ruta_optima_nodos, route_color='lime', route_linewidth=6, node_size=0, bgcolor='#0B161D', edge_color='w', edge_linewidth=0.3)
        timestamp = int(time.time())
        nombre_mapa = f'mapa_ruta_{timestamp}.png'
        ruta_guardado = f'static/{nombre_mapa}'
        fig.savefig(ruta_guardado, dpi=300, bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        resultado = {"distancia": f"{distancia_total_km:.2f}", "tiempo": f"{tiempo_total_min:.2f}", "mapa_url": nombre_mapa, "error": None}
    except nx.NetworkXNoPath:
        resultado = {"error": "No se pudo encontrar una ruta entre los puntos seleccionados."}
    except Exception as e:
        resultado = {"error": f"Ocurrió un error inesperado: {e}"}
    return render_template('resultado.html', resultado=resultado)


if __name__ == '__main__':
    app.run(debug=True)