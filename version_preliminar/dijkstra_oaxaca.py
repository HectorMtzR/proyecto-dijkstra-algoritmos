# -*- coding: utf-8 -*-
"""
PROYECTO: RUTA ÓPTIMA CON DIJKSTRA EN OAXACA
Descripción:
Este script descarga un mapa vial de la zona metropolitana de Oaxaca, calcula la ruta más rápida
(en tiempo) entre dos puntos utilizando el algoritmo de Dijkstra y visualiza el resultado.
"""

# --- 1. IMPORTACIÓN DE LIBRERÍAS ---
import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt

print("Librerías importadas correctamente.")

# --- 2. DESCARGA Y MODELADO DEL MAPA ---
# Se definen las localidades para asegurar la cobertura completa solicitada.
places = ["Oaxaca de Juárez, Oaxaca, México",
          "Santa Cruz Xoxocotlán, Oaxaca, México",
          "San Raymundo Jalpan, Oaxaca, México", 
          "San Antonio de la Cal, Oaxaca, México",
          "San Agustín de las Juntas, Oaxaca, México",
          "Santa Lucía del Camino"]

# Se descarga la red vial usando el filtro 'drive' para incluir únicamente
# calles aptas para vehículos motorizados. 'simplify=True' corrige pequeñas
# imperfecciones topológicas del mapa.
print("Descargando el grafo de la red vial... (esto puede tardar unos minutos)")
G = ox.graph_from_place(places, network_type='drive', simplify=True)
print(f"¡Grafo descargado con éxito! Contiene {G.number_of_nodes()} nodos y {G.number_of_edges()} aristas.")

# --- 3. CÁLCULO DEL PESO DE LAS ARISTAS (TIEMPO DE VIAJE) ---
# Este es el paso crucial para que Dijkstra optimice por tiempo y no por distancia.

# Velocidad estándar en km/h para calles sin el dato 'maxspeed'.
# Este valor es una suposición razonable para calles urbanas.
VELOCIDAD_ESTANDAR_KMH = 20
# Factor de conversión de km/h a m/s (metros/segundo).
KMH_A_MS = 1000 / 3600

print("Asignando pesos (tiempo de viaje) a cada calle...")

# Iteramos sobre cada calle (arista) del grafo para calcular su tiempo de viaje.
for u, v, data in G.edges(data=True):
    longitud_m = data.get('length', 0)
    velocidad_ms = VELOCIDAD_ESTANDAR_KMH * KMH_A_MS # Velocidad por defecto

    # Verificamos si la calle tiene un límite de velocidad definido.
    maxspeed_kmh = data.get('maxspeed')
    if maxspeed_kmh:
        try:
            # El dato 'maxspeed' puede ser un string o una lista. Lo normalizamos a un número.
            speed_val = float(maxspeed_kmh[0]) if isinstance(maxspeed_kmh, list) else float(maxspeed_kmh)
            velocidad_ms = speed_val * KMH_A_MS
        except (ValueError, TypeError):
            # Si el dato no es un número válido, usamos la velocidad estándar.
            pass

    # Fórmula: Tiempo = Distancia / Velocidad. El resultado se guarda en un nuevo atributo.
    if velocidad_ms > 0:
        data['tiempo_viaje_seg'] = longitud_m / velocidad_ms
    else:
        # Evitar división por cero en casos extraños
        data['tiempo_viaje_seg'] = float('inf')


print("Cálculo de pesos finalizado.")

# --- 4. SELECCIÓN DE PUNTOS DE ORIGEN Y DESTINO ---
# Para esta versión base, definimos las coordenadas directamente en el código.
# Puedes obtener coordenadas de Google Maps (clic derecho -> "¿Qué hay aquí?").

"""
# Ejemplo 1: Origen (Santo Domingo de Guzmán) y Destino (Aeropuerto de Oaxaca)
origen_coords = (17.0654, -96.7218)
destino_coords = (17.0013, -96.7183)


# Ejemplo 2: Origen (Casa Xoxo) y Destino (Universidad)
origen_coords = (17.0347, -96.7350)
destino_coords = (16.9969, -96.7524)


# Ejemplo 3: Coordenadas Mario
origen_coords = (17.0676206026916, -96.72343737910167)
destino_coords = (17.001345610243103, -96.7181714289195)


# Ejemplo 4
# Origen: Esquina del Palacio de Gobierno
origen_coords = (17.0594, -96.7262) 
# Destino: Esquina opuesta, frente a la Catedral
destino_coords = (17.0611, -96.7248)


# Ejemplo 5
# Origen: Fuente de las 8 Regiones
origen_coords = (17.0722, -96.7317)
# Destino: Auditorio Guelaguetza
destino_coords = (17.0673, -96.7339)
"""

# Ejemplo 6:
# Origen: Parque Central de Xoxocotlán
origen_coords = (17.0305, -96.7369)
# Destino: Macroplaza Oaxaca
destino_coords = (17.068710, -96.694694)

print(f"Buscando los nodos más cercanos para Origen: {origen_coords} y Destino: {destino_coords}")

# OSMnx encuentra los nodos del grafo más cercanos a nuestras coordenadas geográficas.
origen_nodo = ox.nearest_nodes(G, Y=origen_coords[0], X=origen_coords[1])
destino_nodo = ox.nearest_nodes(G, Y=destino_coords[0], X=destino_coords[1])

print(f"Nodo de origen encontrado: {origen_nodo}")
print(f"Nodo de destino encontrado: {destino_nodo}")


# --- 5. CÁLCULO Y VISUALIZACIÓN DE LA RUTA ÓPTIMA ---
print("Calculando la ruta más rápida con el algoritmo de Dijkstra...")

try:
    # Aquí se aplica el algoritmo de Dijkstra. Le indicamos que use nuestro atributo
    # 'tiempo_viaje_seg' como el "peso" a minimizar.
    ruta_optima_nodos = nx.shortest_path(G, source=origen_nodo, target=destino_nodo, weight='tiempo_viaje_seg')
    print("¡Ruta encontrada!")

    # --- PRESENTACIÓN DE RESULTADOS (VERSIÓN CORREGIDA Y ROBUSTA) ---
    # Calculamos el tiempo total que ya nos da el algoritmo.
    tiempo_total_seg = nx.shortest_path_length(G, source=origen_nodo, target=destino_nodo, weight='tiempo_viaje_seg')
    tiempo_total_min = tiempo_total_seg / 60

    # Calculamos la distancia total manualmente, recorriendo cada tramo de la ruta.
    # Este método es más estable que usar funciones que cambian de versión.
    distancia_total_m = 0
    for i in range(len(ruta_optima_nodos) - 1):
        # Tomamos el nodo actual (u) y el siguiente (v) en la ruta
        u = ruta_optima_nodos[i]
        v = ruta_optima_nodos[i+1]
        
        # Obtenemos la longitud de la calle que los une y la sumamos
        # El [0] es porque puede haber múltiples aristas, tomamos la principal.
        distancia_total_m += G.edges[u, v, 0]['length']
    
    distancia_total_km = distancia_total_m / 1000

    print("\n" + "="*40)
    print("         RESUMEN DE LA RUTA ÓPTIMA")
    print("="*40)
    print(f"Distancia total del recorrido: {distancia_total_km:.2f} km")
    print(f"Tiempo de viaje estimado: {tiempo_total_min:.2f} minutos")
    print("="*40 + "\n")


    # --- VISUALIZACIÓN EN EL MAPA ---
    # `ox.plot_graph_route` es una función muy útil para dibujar el grafo y la ruta sobre él.
    fig, ax = ox.plot_graph_route(
        G,
        ruta_optima_nodos,
        route_color='lime',      # Color de la ruta
        route_linewidth=6,       # Ancho de la línea de la ruta
        node_size=0,             # Ocultamos los nodos para un mapa más limpio
        bgcolor='#0B161D',       # Color de fondo oscuro
        edge_color='w',          # Color de las calles
        edge_linewidth=0.3       # Ancho de línea de las calles
    )
    ax.set_title("Ruta Más Rápida en la Zona Metropolitana de Oaxaca", fontsize=16, color='white')
    plt.show()

except nx.NetworkXNoPath:
    print(f"No se pudo encontrar una ruta entre el nodo {origen_nodo} y el nodo {destino_nodo}.")