from flask import Flask, render_template, request, jsonify # jsonify es nuevo
import osmnx as ox
import networkx as nx
import folium
import branca
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import time

app = Flask(__name__)

# --- CARGA DEL GRAFO (SE MANTIENE IGUAL) ---
print("Cargando el grafo de la red vial...")
places = ["Oaxaca de Juárez, Oaxaca, México",
          "Santa Cruz Xoxocotlán, Oaxaca, México",
          "San Raymundo Jalpan, Oaxaca, México", 
          "San Antonio de la Cal, Oaxaca, México",
          "San Agustín de las Juntas, Oaxaca, México",
          "Santa Lucía del Camino, Oaxaca, México",
          "Villa de Zaachila, Oaxaca, México"]

G = ox.graph_from_place(places, network_type='drive', simplify=True)
# Pre-calcular los pesos...
# (El resto del código de carga y cálculo de pesos se mantiene exactamente igual)
print("Calculando pesos de tiempo de viaje...")
VELOCIDAD_ESTANDAR_KMH = 20
KMH_A_MS = 1000 / 3600
for u, v, data in G.edges(data=True):
    longitud_m = data.get('length', 0)
    velocidad_ms = VELOCIDAD_ESTANDAR_KMH * KMH_A_MS
    maxspeed_kmh = data.get('maxspeed')
    if maxspeed_kmh:
        try:
            speed_val = float(maxspeed_kmh[0]) if isinstance(maxspeed_kmh, list) else float(maxspeed_kmh)
            velocidad_ms = speed_val * KMH_A_MS
        except (ValueError, TypeError): pass
    data['tiempo_viaje_seg'] = longitud_m / velocidad_ms if velocidad_ms > 0 else float('inf')
print("¡Grafo listo para recibir peticiones!")
# --- FIN DE LA CARGA DEL GRAFO ---

# --- RUTA 1: PÁGINA PRINCIPAL (CON LÍMITES REFINADOS) ---
@app.route('/')
def index():
    mapa = folium.Map(location=[17.06, -96.72], zoom_start=13)

    # --- NUEVO: DIBUJAR LÍMITES PRECISOS DEL MAPA (CASCO CONVEXO) ---
    # Obtenemos los nodos del grafo como un GeoDataFrame
    nodes = ox.graph_to_gdfs(G, edges=False)
    
    # Calculamos el casco convexo que envuelve a todos los nodos
    convex_hull_polygon = nodes.unary_union.convex_hull
    
    # Obtenemos las coordenadas del polígono.
    # Folium espera (lat, lon), pero el polígono nos da (lon, lat), así que las invertimos.
    hull_points = [(lat, lon) for lon, lat in convex_hull_polygon.exterior.coords]
    
    # Dibujamos el polígono en el mapa en lugar del rectángulo
    folium.Polygon(
        locations=hull_points,
        color="#ff7800",
        weight=2,
        fill=True,
        fill_color="#ffff00",
        fill_opacity=0.1
    ).add_to(mapa)
    
    # --- El resto de la función (inyector de JavaScript) se mantiene exactamente igual ---
    map_name = mapa.get_name()
    js_code = f"""
    <script>
        function attachClickEvents() {{
            if (window['{map_name}']) {{
                var map = window['{map_name}'];
                var originMarker, destinationMarker;
                var clickCount = 0;

                function updateFormFields(lat, lon) {{
                    if (clickCount === 0) {{
                        window.parent.document.getElementById('origen_lat').value = lat.toFixed(6);
                        window.parent.document.getElementById('origen_lon').value = lon.toFixed(6);
                    }} else if (clickCount === 1) {{
                        window.parent.document.getElementById('destino_lat').value = lat.toFixed(6);
                        window.parent.document.getElementById('destino_lon').value = lon.toFixed(6);
                    }}
                }}

                map.on('click', function(e) {{
                    var coord = e.latlng;
                    if (clickCount >= 2) {{ return; }}

                    updateFormFields(coord.lat, coord.lng);
                    
                    if (clickCount === 0) {{
                        if (originMarker) map.removeLayer(originMarker);
                        originMarker = L.marker(coord).addTo(map).bindPopup('<b>Origen</b>').openPopup();
                        window.parent.document.getElementById('instruction').innerText = "Selecciona el PUNTO DE DESTINO";
                        clickCount++;
                    }} else if (clickCount === 1) {{
                        if (destinationMarker) map.removeLayer(destinationMarker);
                        destinationMarker = L.marker(coord).addTo(map).bindPopup('<b>Destino</b>').openPopup();
                        window.parent.document.getElementById('instruction').innerText = "¡Puntos listos! Presiona 'Calcular Ruta'";
                        clickCount++;
                        window.parent.document.getElementById('calculate-btn').disabled = false;
                    }}
                }});

                window.parent.document.addEventListener('resetMap', function() {{
                    if(originMarker) map.removeLayer(originMarker);
                    if(destinationMarker) map.removeLayer(destinationMarker);
                    clickCount = 0;
                    originMarker = null;
                    destinationMarker = null;
                }});

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

# --- RUTA 2: API PARA CALCULAR LA RUTA (MODIFICADA) ---
@app.route('/ruta', methods=['POST'])
def calcular_ruta_api():
    try:
        data = request.get_json()
        origen_lat = float(data['origen_lat'])
        origen_lon = float(data['origen_lon'])
        destino_lat = float(data['destino_lat'])
        destino_lon = float(data['destino_lon'])

        origen_nodo = ox.nearest_nodes(G, Y=origen_lat, X=origen_lon)
        destino_nodo = ox.nearest_nodes(G, Y=destino_lat, X=destino_lon)

        ruta_optima_nodos = nx.shortest_path(G, source=origen_nodo, target=destino_nodo, weight='tiempo_viaje_seg')
        
        tiempo_total_min = nx.shortest_path_length(G, source=origen_nodo, target=destino_nodo, weight='tiempo_viaje_seg') / 60
        distancia_total_km = sum(G.edges[u, v, 0]['length'] for u, v in zip(ruta_optima_nodos[:-1], ruta_optima_nodos[1:])) / 1000

        fig, ax = ox.plot_graph_route(G, ruta_optima_nodos, route_color='lime', route_linewidth=2, node_size=0, bgcolor='#0B161D', edge_color='w', edge_linewidth=0.15)
        timestamp = int(time.time())
        nombre_mapa = f'mapa_ruta_{timestamp}.png'
        ruta_guardado = f'static/{nombre_mapa}'
        fig.savefig(ruta_guardado, dpi=300, bbox_inches='tight', pad_inches=0)
        plt.close(fig)

        return jsonify({
            "success": True,
            "distancia": f"{distancia_total_km:.2f}",
            "tiempo": f"{tiempo_total_min:.2f}",
            "mapa_url": f"/static/{nombre_mapa}"
        })

    except nx.NetworkXNoPath:
        return jsonify({"success": False, "error": "No se pudo encontrar una ruta entre los puntos seleccionados."})
    except Exception as e:
        return jsonify({"success": False, "error": f"Ocurrió un error: {e}"})

if __name__ == '__main__':
    app.run(debug=True)