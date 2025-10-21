# ==============================================================================
# 1. IMPORTACIÓN DE LIBRERÍAS
# ==============================================================================
# Se importan todas las herramientas necesarias para la aplicación.
# Flask para el servidor web, OSMnx para los mapas, Folium para la interactividad, etc.

from flask import Flask, render_template, request, jsonify
import osmnx as ox
import networkx as nx
import folium
import branca
import matplotlib
matplotlib.use('Agg') # Configuración para que Matplotlib funcione sin interfaz gráfica en el servidor.
import matplotlib.pyplot as plt
import time
import math

# ==============================================================================
# 2. IMPLEMENTACIÓN DEL ALGORITMO DE DIJKSTRA
# ==============================================================================
# Esta función contiene la lógica principal para encontrar el camino más corto.
# Se independiza de las librerías para un entendimiento más profundo del proceso.

def dijkstra_personalizado(graph, start_node, end_node):
    """
    Implementación adaptada del algoritmo de Dijkstra.

    Encuentra la ruta más corta (basada en el peso 'tiempo_viaje_seg') desde un
    nodo de inicio a un nodo de fin en un grafo de NetworkX.

    Args:
        graph (networkx.Graph): El grafo de OSMnx/NetworkX que representa la red de calles.
        start_node: El ID del nodo de inicio de la ruta.
        end_node: El ID del nodo de destino de la ruta.

    Returns:
        tuple: Una tupla que contiene:
               - La lista de nodos de la ruta óptima.
               - El costo total (tiempo en segundos) de esa ruta.
               Devuelve (None, math.inf) si no se encuentra una ruta.
    """
    # 2.1. Inicialización de estructuras de datos
    # 'distancias' guarda el costo mínimo conocido para llegar a cada nodo desde el inicio.
    distancias = {node: math.inf for node in graph.nodes}
    distancias[start_node] = 0
    # 'nodos_anteriores' permite reconstruir el camino guardando el "paso anterior" para cada nodo.
    nodos_anteriores = {node: None for node in graph.nodes}
    # 'nodos_no_visitados' es la lista de todos los nodos que aún no hemos procesado.
    nodos_no_visitados = list(graph.nodes)

    # 2.2. Bucle principal del algoritmo
    # El bucle se ejecuta mientras queden nodos por visitar.
    while nodos_no_visitados:
        # Encuentra el nodo no visitado con la distancia más corta acumulada.
        distancia_minima = math.inf
        nodo_actual = None
        for nodo in nodos_no_visitados:
            if distancias[nodo] < distancia_minima:
                distancia_minima = distancias[nodo]
                nodo_actual = nodo
        
        # Si hemos llegado al nodo final, la ruta está encontrada.
        if nodo_actual == end_node:
            ruta = []
            nodo_temporal = end_node
            # Reconstruimos la ruta hacia atrás, desde el final hasta el principio.
            while nodo_temporal is not None:
                ruta.append(nodo_temporal)
                nodo_temporal = nodos_anteriores[nodo_temporal]
            return ruta[::-1], distancias[end_node] # Devolvemos la ruta en orden y el costo final.

        # Si el nodo más cercano es inalcanzable, no hay más caminos posibles.
        if nodo_actual is None:
            break

        # 2.3. Exploración de vecinos
        # Para el nodo actual, revisamos todos sus vecinos directos.
        for vecino in graph.neighbors(nodo_actual):
            # Obtenemos el "peso" de la calle entre el nodo actual y su vecino.
            peso = graph.edges[nodo_actual, vecino, 0].get('tiempo_viaje_seg', math.inf)
            # Calculamos la nueva distancia posible pasando por el nodo actual.
            nueva_distancia = distancias[nodo_actual] + peso
            
            # Si este nuevo camino es más corto que el que ya conocíamos, lo actualizamos.
            if nueva_distancia < distancias[vecino]:
                distancias[vecino] = nueva_distancia
                nodos_anteriores[vecino] = nodo_actual
        
        # Marcamos el nodo actual como "visitado" para no procesarlo de nuevo.
        nodos_no_visitados.remove(nodo_actual)
            
    # Si el bucle termina sin haber llegado al 'end_node', no existe una ruta.
    return None, math.inf

# ==============================================================================
# 3. CONFIGURACIÓN DE LA APLICACIÓN FLASK Y CARGA DE DATOS
# ==============================================================================
# Se inicializa la aplicación web y se realiza la carga pesada de datos una sola vez
# al arrancar el servidor para optimizar el rendimiento.

app = Flask(__name__)

# --- Carga y pre-procesamiento del grafo ---
print("Cargando el grafo de la red vial...")
places = ["Oaxaca de Juárez, Oaxaca, México",
          "Santa Cruz Xoxocotlán, Oaxaca, México",
          "San Raymundo Jalpan, Oaxaca, México", 
          "San Antonio de la Cal, Oaxaca, México",
          "San Agustín de las Juntas, Oaxaca, México",
          "Santa Lucía del Camino, Oaxaca, México",
          "Villa de Zaachila, Oaxaca, México"]
G = ox.graph_from_place(places, network_type='drive', simplify=True)

print("Calculando pesos de tiempo de viaje para cada calle...")
VELOCIDAD_ESTANDAR_KMH = 15
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
    # Se calcula y asigna el peso a cada calle (arista) del grafo.
    data['tiempo_viaje_seg'] = longitud_m / velocidad_ms if velocidad_ms > 0 else float('inf')
print("¡Grafo listo para recibir peticiones!")

# ==============================================================================
# 4. RUTAS DE LA APLICACIÓN (ENDPOINTS)
# ==============================================================================
# Definen las URLs que la aplicación puede recibir y qué hacer con ellas.

# --- Ruta 1: Página principal ('/') ---
@app.route('/')
def index():
    """
    Renderiza la página de inicio.
    Prepara el mapa interactivo de Folium con sus límites y el script de interactividad.
    """
    mapa = folium.Map(location=[17.06, -96.72], zoom_start=13)
    
    # Dibuja el polígono que delimita el área de operación del mapa.
    nodes = ox.graph_to_gdfs(G, edges=False)
    convex_hull_polygon = nodes.unary_union.convex_hull
    hull_points = [(lat, lon) for lon, lat in convex_hull_polygon.exterior.coords]
    folium.Polygon(
        locations=hull_points,
        color="#ff7800",
        weight=2,
        fill=True,
        fill_color="#ffff00",
        fill_opacity=0.1
    ).add_to(mapa)
    
    # Inyecta el código JavaScript en el mapa para manejar los clics del usuario.
    # Este script se comunica con la página principal para actualizar el formulario.
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
    
    # Convierte el mapa de Folium a HTML para mostrarlo en la plantilla.
    mapa_html = mapa._repr_html_()
    
    return render_template('index.html', mapa_html=mapa_html)

# --- Ruta 2: API para el cálculo ('/ruta') ---
@app.route('/ruta', methods=['POST'])
def calcular_ruta_api():
    """
    Endpoint de la API que calcula la ruta y devuelve los resultados como JSON.
    """
    try:
        # 4.1. Recibe y procesa los datos enviados por el usuario.
        data = request.get_json()
        origen_lat = float(data['origen_lat'])
        origen_lon = float(data['origen_lon'])
        destino_lat = float(data['destino_lat'])
        destino_lon = float(data['destino_lon'])

        # Encuentra los nodos del grafo más cercanos a las coordenadas dadas.
        origen_nodo = ox.nearest_nodes(G, Y=origen_lat, X=origen_lon)
        destino_nodo = ox.nearest_nodes(G, Y=destino_lat, X=destino_lon)

        # 4.2. Ejecuta el algoritmo de Dijkstra.
        ruta_optima_nodos, tiempo_total_seg = dijkstra_personalizado(G, origen_nodo, destino_nodo)

        if ruta_optima_nodos is None:
            return jsonify({"success": False, "error": "No se pudo encontrar una ruta entre los puntos seleccionados."})

        # 4.3. Procesa los resultados.
        tiempo_total_min = tiempo_total_seg / 60
        distancia_total_km = sum(G.edges[u, v, 0]['length'] for u, v in zip(ruta_optima_nodos[:-1], ruta_optima_nodos[1:])) / 1000

        # Recopila los datos para la tabla de desglose de la ruta.
        segmentos = []
        for i in range(len(ruta_optima_nodos) - 1):
            u = ruta_optima_nodos[i]
            v = ruta_optima_nodos[i+1]
            edge_data = G.edges[u, v, 0]
            nombre_calle = edge_data.get('name', 'Calle sin nombre')
            if isinstance(nombre_calle, list):
                nombre_calle = nombre_calle[0]
            distancia_m = edge_data.get('length', 0)
            tiempo_seg = edge_data.get('tiempo_viaje_seg', 0)
            velocidad_kmh = (distancia_m / tiempo_seg) * 3.6 if tiempo_seg > 0 else 0
            segmentos.append({
                "calle": nombre_calle,
                "distancia": f"{distancia_m:.0f} m",
                "velocidad": f"{velocidad_kmh:.1f} km/h",
                "tiempo": f"{tiempo_seg:.1f} s"
            })
        
        # 4.4. Genera la imagen del mapa resultante.
        fig, ax = ox.plot_graph_route(
            G, 
            ruta_optima_nodos,
            route_color='lime', 
            route_linewidth=6, 
            node_size=0, 
            bgcolor='#0B161D', 
            edge_color='gray', 
            edge_linewidth=0.5,
            show=False,
            close=False
        )
        
        # Dibuja los marcadores de inicio y fin.
        origen_coords = (G.nodes[origen_nodo]['y'], G.nodes[origen_nodo]['x'])
        destino_coords = (G.nodes[destino_nodo]['y'], G.nodes[destino_nodo]['x'])
        ax.scatter(origen_coords[1], origen_coords[0], s=200, c='lime', marker='o', zorder=5, label='Origen')
        ax.scatter(destino_coords[1], destino_coords[0], s=200, c='red', marker='X', zorder=5, label='Destino')

        # Aplica el zoom manual al área de la ruta.
        x = [G.nodes[n]['x'] for n in ruta_optima_nodos]
        y = [G.nodes[n]['y'] for n in ruta_optima_nodos]
        margen = 0.008
        ax.set_xlim(min(x) - margen, max(x) + margen)
        ax.set_ylim(min(y) - margen, max(y) + margen)
        
        # Guarda la figura como un archivo de imagen.
        timestamp = int(time.time())
        nombre_mapa = f'mapa_ruta_{timestamp}.png'
        ruta_guardado = f'static/{nombre_mapa}'
        fig.savefig(ruta_guardado, dpi=300, bbox_inches='tight', pad_inches=0)
        plt.close(fig)

        # 4.5. Devuelve todos los datos al front-end en formato JSON.
        return jsonify({
            "success": True,
            "distancia": f"{distancia_total_km:.2f}",
            "tiempo": f"{tiempo_total_min:.2f}",
            "mapa_url": f"/static/{nombre_mapa}",
            "segmentos": segmentos
        })

    except Exception as e:
        print(f"Error en el servidor: {e}")
        return jsonify({"success": False, "error": f"Ocurrió un error inesperado en el servidor."})

# ==============================================================================
# 5. INICIO DE LA APLICACIÓN
# ==============================================================================
# Este bloque solo se ejecuta cuando el script se corre directamente (`python app.py`).
if __name__ == '__main__':
    app.run(debug=True)