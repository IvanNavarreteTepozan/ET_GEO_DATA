
import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from datetime import datetime
import time
import random
import os
import shutil

def overpass_query(area_name, tags, date=None, endpoint="https://overpass.kumi.systems/api/interpreter", timeLimit=30):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    filters = []
    for k, v in tags.items():
        if v is True:
            filters.append(f'node["{k}"](area.searchArea);')
        else:
            filters.append(f'node["{k}"="{v}"](area.searchArea);')
    
    filters_str = "\n".join(filters)
    
    query = f"""
    [out:json][timeout:{timeLimit}][date:"{date}"];
    area["name"="{area_name}"]->.searchArea;
    (
    {filters_str}
    );
    out body;
    """
    
    response = requests.get(endpoint, params={'data': query})
    if response.status_code != 200:
        raise Exception(f"Error en la consulta: {response.status_code} {response.text}")
    
    data = response.json()
    elements = data.get('elements', [])
    
    if not elements:
        return pd.DataFrame() 

    df = pd.DataFrame(elements)
    
    if 'lat' in df.columns and 'lon' in df.columns:
        df['geometry'] = df.apply(lambda row: Point(row['lon'], row['lat']), axis=1)
        gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
        return gdf
    else:
        return df

def try_query(tries=10, timeLimit=60, areaName="*", tags={"amenity":"bank"}, date=None):

    estado = False
    secuence = 0
    df = pd.DataFrame() 

    while estado != True and secuence < tries:
        secuence += 1
        try:
            df = overpass_query(
                timeLimit=timeLimit,
                area_name=areaName,
                tags=tags,
                date=date)
            estado = True
        except Exception as e:
            error_msg = str(e)
            if "server is probably too busy" in error_msg.lower():
                print(f"Intento {secuence} fallido: servidor ocupado")
                time.sleep(random.randint(3,20)) # Para  no mandar peticiones unua y otra y otra vez 
            else:
                print(f"Intento {secuence} fallido: error -> {error_msg}")
                return None
    return df
            
def select_all_from_overpass(tries, timeLimit, areaName, tags, date):
    
    df= try_query(tries=tries, timeLimit=timeLimit,areaName=areaName, tags=tags, date=date)
    
    if 'tags' not in df.columns:
        return df
    
    tags_df = pd.json_normalize(df['tags'])
    
    df2= pd.concat([df.drop(columns=['tags']), tags_df], axis=1)
    if 'lat'  in df.columns or 'lon'  in df.columns :
        df2= df2.rename(columns={"lat": "Latitud", "lon": "Longitud"})
    df2.drop(columns="geometry", inplace=True)
    return df2




def save_data(df, NombreArchivo="Datos.csv", CarpetaDestino=None):

    if not NombreArchivo.lower().endswith(".csv"):
        NombreArchivo += ".csv"

    df.to_csv(NombreArchivo, index=False)

    ruta_actual = os.getcwd()
    ruta_padre = os.path.dirname(ruta_actual)
    origen = os.path.join(ruta_actual, NombreArchivo)

    if CarpetaDestino in ("C1_ingresosAltos", "C2_ingresosMedios", "C3_ingresosBajos"):
        destino_carpeta = os.path.join(ruta_padre, CarpetaDestino)
        os.makedirs(destino_carpeta, exist_ok=True)  # crea carpeta si no existe
        destino = os.path.join(destino_carpeta, NombreArchivo)
    elif CarpetaDestino is not None:
        destino= CarpetaDestino
        os.makedirs(destino, exist_ok=True)
    else:
        print("Ruta vacía, no se movió el archivo.")
        return

    shutil.move(origen, destino)
    print(f"Archivo movido de {origen} a {destino}")


def CrearDatosDeEntrenamiento(RUTA_ACTUAL,RUTA_DESTINO, AREA_ESTUDIO ,  FECHA_CONSULTA , CONFIG):
    for carpeta_negocio, configuraciones in CONFIG.items():

        ruta_destino = os.path.join(RUTA_DESTINO, carpeta_negocio)
        os.makedirs(ruta_destino, exist_ok=True)
    
        for config in configuraciones:
            nombre_archivo = config["archivo"]
            tags_consulta = config["tags"]
        
            print(f"-> Extrayendo datos para: {nombre_archivo} en {carpeta_negocio}...")
        
            try:

                df = select_all_from_overpass(
                    tries=5,
                    timeLimit=60,
                    areaName=AREA_ESTUDIO,
                    tags=tags_consulta,
                    date=FECHA_CONSULTA
                )
            
            # Validar que df no esté vacío o sea None antes de guardar
                if df is not None and not df.empty:
                    origen_temporal = os.path.join(RUTA_ACTUAL, nombre_archivo)
                    df.to_csv(origen_temporal, index=False)
                
                # Mover a la carpeta de negocio
                    destino_final = os.path.join(ruta_destino, nombre_archivo)
                    shutil.move(origen_temporal, destino_final)
                
                    print(f"   [ÉXITO] Archivo guardado en: {carpeta_negocio}/{nombre_archivo}")
                else:
                    print(f"   [VACÍO] No se encontraron datos para {tags_consulta}")
                
            except Exception as e:
                print(f"   [ERROR] Falló la descarga de {nombre_archivo}: {e}")

    print("\n¡Automatización completada! Tus datos están segmentados y listos para el análisis espacial.")
