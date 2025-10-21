# dijkstra_custom.py
import math

def dijkstra_personalizado(graph, start_node, end_node):
    """
    Implementación adaptada del algoritmo de Dijkstra.

    Encuentra la ruta más corta (basada en 'tiempo_viaje_seg') desde un nodo de
    inicio a un nodo de fin en un grafo de NetworkX.

    Args:
        graph (networkx.Graph): El grafo de OSMnx/NetworkX.
        start_node: El nodo de inicio de la ruta.
        end_node: El nodo de destino de la ruta.

    Returns:
        tuple: Una tupla conteniendo (lista_de_nodos_ruta, costo_total_ruta).
               Devuelve (None, math.inf) si no se encuentra una ruta.
    """
    # 1. Inicialización
    # Guardará la distancia más corta conocida desde el inicio hasta cada nodo
    distancias = {node: math.inf for node in graph.nodes}
    distancias[start_node] = 0
    
    # Guardará el nodo previo en la ruta más corta para poder reconstruirla
    nodos_anteriores = {node: None for node in graph.nodes}
    
    # Lista de nodos que aún necesitamos visitar
    nodos_no_visitados = list(graph.nodes)

    while nodos_no_visitados:
        # 2. Encontrar el nodo no visitado con la distancia más corta
        distancia_minima = math.inf
        nodo_actual = None
        for nodo in nodos_no_visitados:
            if distancias[nodo] < distancia_minima:
                distancia_minima = distancias[nodo]
                nodo_actual = nodo
        
        # Si llegamos al nodo final, podemos terminar y reconstruir la ruta
        if nodo_actual == end_node:
            ruta = []
            nodo_temporal = end_node
            while nodo_temporal is not None:
                ruta.append(nodo_temporal)
                nodo_temporal = nodos_anteriores[nodo_temporal]
            # La ruta está en orden inverso, la volteamos
            return ruta[::-1], distancias[end_node]

        # Si no hay un nodo alcanzable, salimos del bucle
        if nodo_actual is None:
            break

        # 3. Calcular distancias a través del nodo actual hacia sus vecinos
        # Usamos graph.neighbors() para que funcione con el objeto de NetworkX
        for vecino in graph.neighbors(nodo_actual):
            # Obtenemos el peso de nuestra arista (calle)
            peso = graph.edges[nodo_actual, vecino, 0].get('tiempo_viaje_seg', math.inf)
            nueva_distancia = distancias[nodo_actual] + peso
            
            if nueva_distancia < distancias[vecino]:
                distancias[vecino] = nueva_distancia
                nodos_anteriores[vecino] = nodo_actual
        
        # 4. Marcar el nodo actual como visitado
        nodos_no_visitados.remove(nodo_actual)
            
    # Si el bucle termina y no llegamos al final, no hay ruta
    return None, math.inf