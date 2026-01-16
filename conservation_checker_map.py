import streamlit as st
import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="UK Conservation Area Checker", layout="wide")

st.title("🏛️ UK Conservation Area Checker")
st.write("Enter a postcode to check whether it lies within a conservation area.")

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def geocode_postcode(postcode: str):
    postcode = postcode.replace(" ", "")
    url = f"https://api.postcodes.io/postcodes/{postcode}"
    r = requests.get(url)
    if r.status_code != 200:
        return None
    data = r.json()["result"]
    return data["longitude"], data["latitude"]

def normalise_schema(gdf, source):
    if source == "England":
        gdf["area_name"] = gdf.get("name", "Unknown")
        gdf["doc_url"] = gdf.get("documentation-url")
    elif source == "Wales":
        gdf["area_name"] = gdf.get("NAME", "Unknown")
        gdf["doc_url"] = None

    gdf["source"] = source
    return gdf[["area_name", "doc_url", "source", "geometry"]]

@st.cache_data
def load_conservation_areas():
    # ---------- England ----------
    eng1 = gpd.read_file("conservation-area-1.geojson")
    eng2 = gpd.read_file("conservation-area-2.geojson")

    england = gpd.GeoDataFrame(
        pd.concat([eng1, eng2], ignore_index=True),
        crs="EPSG:4326"
    )
    england = normalise_schema(england, "England")

    # ---------- Wales ----------
    wales = gpd.read_file("conservation-area-wales.json")

    if wales.crs is None:
        wales = wales.set_crs(epsg=27700)

    wales = wales.to_crs(epsg=4326)
    wales = normalise_schema(wales, "Wales")

    # ---------- Combine ----------
    all_areas = gpd.GeoDataFrame(
        pd.concat([england, wales], ignore_index=True),
        crs="EPSG:4326"
    )

    return all_areas

# --------------------------------------------------
# Load data
# --------------------------------------------------

areas = load_conservation_areas()

# --------------------------------------------------
# UI
# --------------------------------------------------

postcode = st.text_input("Postcode", placeholder="e.g. N19 5BX")

if postcode:
    coords = geocode_postcode(postcode)

    if not coords:
        st.error("Postcode not found.")
        st.stop()

    lon, lat = coords
    point = gpd.GeoDataFrame(
        geometry=[Point(lon, lat)],
        crs="EPSG:4326"
    )

    # Spatial test
    inside = areas[areas.contains(point.iloc[0].geometry)]

    # --------------------------------------------------
    # Results
    # --------------------------------------------------

    if inside.empty:
        st.success("✅ This postcode is NOT inside a conservation area.")
    else:
        st.warning("⚠️ This postcode IS inside a conservation area.")

        for _, row in inside.iterrows():
            st.markdown(f"### {row['area_name']} ({row['source']})")
            if row["doc_url"]:
                st.markdown(f"[📄 Documentation]({row['doc_url']})")

    # --------------------------------------------------
    # Map
    # --------------------------------------------------

    m = folium.Map(location=[lat, lon], zoom_start=12)

    # Postcode marker
    folium.Marker(
        [lat, lon],
        tooltip="Postcode location",
        icon=folium.Icon(color="red", icon="home")
    ).add_to(m)

    # 10km radius
    folium.Circle(
        radius=10000,
        location=[lat, lon],
        color="blue",
        fill=False
    ).add_to(m)

    # Nearby conservation areas
    nearby = areas[areas.geometry.distance(point.iloc[0].geometry) < 0.1]

    folium.GeoJson(
        nearby,
        name="Conservation Areas",
        style_function=lambda x: {
            "fillColor": "green",
            "color": "green",
            "weight": 1,
            "fillOpacity": 0.3,
        },
        tooltip=folium.GeoJsonTooltip(fields=["area_name", "source"])
    ).add_to(m)

    st.subheader("🗺️ Map")
    st_folium(m, width=900, height=600)
