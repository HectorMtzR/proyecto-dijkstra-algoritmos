# --- IMPORTACIONES ---
from flask import Flask, render_template, request
import osmnx as ox
import networkx as nx
import matplotlib
matplotlib.use('Agg') # Modo especial para correr matplotlib en un servidor
import matplotlib.pyplot as plt
import time # Para nombres de archivo únicos

# --- INICIALIZACIÓN DE FLASK ---
app = Flask(__name__)

# --- CARGA DEL GRAFO (SE HACE UNA SOLA VEZ AL INICIAR) ---
print("Cargando el grafo de la red vial... Esto puede tardar.")
places = ["Oaxaca de Juárez, Oaxaca, México",
          "Santa Cruz Xoxocotlán, Oaxaca, México",
          "San Raymundo Jalpan, Oaxaca, México", 
          "San Antonio de la Cal, Oaxaca, México",
          "San Agustín de las Juntas, Oaxaca, México",
          "Villa de Zaachila, Oaxaca, México",
          "Santa Lucía del Camino"]
G = ox.graph_from_place(places, network_type='drive', simplify=True)

# Pre-calcular los pesos de tiempo de viaje para optimizar
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
        except (ValueError, TypeError):
            pass
    data['tiempo_viaje_seg'] = longitud_m / velocidad_ms if velocidad_ms > 0 else float('inf')
print("¡Grafo listo para recibir peticiones!")


# --- DEFINICIÓN DE LA RUTA PRINCIPAL ---
@app.route('/', methods=['GET', 'POST'])
def index():
    resultado = None # Inicializamos la variable de resultado

    # Si el usuario envía el formulario (método POST)
    if request.method == 'POST':
        try:
            # Obtenemos las coordenadas del formulario HTML
            origen_lat = float(request.form['origen_lat'])
            origen_lon = float(request.form['origen_lon'])
            destino_lat = float(request.form['destino_lat'])
            destino_lon = float(request.form['destino_lon'])

            # Encontrar nodos más cercanos
            origen_nodo = ox.nearest_nodes(G, Y=origen_lat, X=origen_lon)
            destino_nodo = ox.nearest_nodes(G, Y=destino_lat, X=destino_lon)

            # Calcular ruta
            ruta_optima_nodos = nx.shortest_path(G, source=origen_nodo, target=destino_nodo, weight='tiempo_viaje_seg')
            
            # Obtener estadísticas de la ruta
            tiempo_total_min = nx.shortest_path_length(G, source=origen_nodo, target=destino_nodo, weight='tiempo_viaje_seg') / 60
            distancia_total_km = sum(G.edges[u, v, 0]['length'] for u, v in zip(ruta_optima_nodos[:-1], ruta_optima_nodos[1:])) / 1000

            # Generar y guardar el mapa como imagen
            fig, ax = ox.plot_graph_route(G, ruta_optima_nodos, route_color='lime', route_linewidth=6, node_size=0, bgcolor='#0B161D', edge_color='w', edge_linewidth=0.3)
            
            # Generamos un nombre de archivo único para evitar problemas de caché del navegador
            timestamp = int(time.time())
            nombre_mapa = f'mapa_ruta_{timestamp}.png'
            ruta_guardado = f'static/{nombre_mapa}'
            fig.savefig(ruta_guardado, dpi=300, bbox_inches='tight', pad_inches=0)
            plt.close(fig) # Cerramos la figura para liberar memoria

            # Preparamos el diccionario de resultados para enviarlo al HTML
            resultado = {
                "distancia": f"{distancia_total_km:.2f}",
                "tiempo": f"{tiempo_total_min:.2f}",
                "mapa_url": nombre_mapa,
                "error": None
            }

        except nx.NetworkXNoPath:
            resultado = {"error": "No se pudo encontrar una ruta entre los puntos seleccionados."}
        except Exception as e:
            resultado = {"error": f"Ocurrió un error inesperado: {e}"}
            
    # Renderizamos la plantilla HTML, pasándole la variable 'resultado'
    return render_template('index.html', resultado=resultado)


# --- INICIAR LA APLICACIÓN ---
if __name__ == '__main__':
    app.run(debug=True) # debug=True nos ayuda a ver errores mientras desarrollamos