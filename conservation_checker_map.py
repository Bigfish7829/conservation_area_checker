import streamlit as st
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import requests
import folium
from streamlit_folium import st_folium

# -------------------------
# Page config
# -------------------------
st.set_page_config(
    page_title="UK Conservation Area Checker",
    layout="wide"
)

st.title("England Conservation Area Checker")

st.markdown(
    "Check whether a postcode in England falls within a conservation area and view nearby conservation areas within 10 km."
)


# -------------------------
# Load conservation areas (cached)
# -------------------------
@st.cache_data
def load_conservation_areas():
    gdf1 = gpd.read_file("conservation-area-1.geojson")
    gdf2 = gpd.read_file("conservation-area-2.geojson")

    gdf = gpd.GeoDataFrame(
        pd.concat([gdf1, gdf2], ignore_index=True),
        crs="EPSG:4326"
    )

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)

    return gdf

areas = load_conservation_areas()

# -------------------------
# Helper functions
# -------------------------
def postcode_to_point(postcode: str):
    url = f"https://api.postcodes.io/postcodes/{postcode.replace(' ', '')}"
    r = requests.get(url, timeout=10)

    if r.status_code != 200:
        return None

    data = r.json()
    if data["status"] != 200 or data["result"] is None:
        return None

    return Point(
        data["result"]["longitude"],
        data["result"]["latitude"]
    )

def areas_within_radius(point: Point, areas_gdf, km=10):
    point_gdf = gpd.GeoDataFrame(
        geometry=[point], crs="EPSG:4326"
    ).to_crs(27700)

    areas_m = areas_gdf.to_crs(27700)
    buffer_geom = point_gdf.buffer(km * 1000).iloc[0]

    nearby = areas_m[areas_m.intersects(buffer_geom)]

    return nearby.to_crs(4326), buffer_geom

# -------------------------
# UI
# -------------------------
postcode = st.text_input(
    "Enter a UK postcode",
    placeholder="e.g. NW5 4QB"
)

if postcode:
    point = postcode_to_point(postcode)

    if point is None:
        st.error("❌ Invalid postcode")
        st.stop()

    inside = areas[areas.geometry.intersects(point)]
    nearby, buffer_geom = areas_within_radius(point, areas, km=10)

    # -------------------------
    # Results
    # -------------------------
    if not inside.empty:
        st.success("✅ This postcode IS in a conservation area")

        for _, row in inside.iterrows():
            st.markdown(f"### {row['name']}")
            st.write(f"**Reference:** {row['reference']}")

            doc_url = row.get("documentation-url")
            if isinstance(doc_url, str) and doc_url.startswith("http"):
                st.markdown(
                    f"[📄 View conservation area documentation]({doc_url})"
                )
    else:
        st.warning("❌ This postcode is NOT in a conservation area")

    # -------------------------
    # Map
    # -------------------------
    m = folium.Map(
        location=[point.y, point.x],
        zoom_start=12,
        tiles="OpenStreetMap"
    )

    # 10 km radius
    folium.GeoJson(
        buffer_geom.__geo_interface__,
        name="10 km radius",
        style_function=lambda x: {
            "fillColor": "#3186cc",
            "color": "#3186cc",
            "weight": 1,
            "fillOpacity": 0.1,
        },
    ).add_to(m)

    # Conservation areas
    for _, row in nearby.iterrows():
        tooltip_text = row["name"]
        if isinstance(row.get("documentation-url"), str):
            tooltip_text += " (documentation available)"

        folium.GeoJson(
            row.geometry.__geo_interface__,
            tooltip=tooltip_text,
            style_function=lambda x: {
                "fillColor": "green",
                "color": "darkgreen",
                "weight": 2,
                "fillOpacity": 0.4,
            },
        ).add_to(m)

    # Postcode marker
    folium.Marker(
        location=[point.y, point.x],
        popup=postcode,
        icon=folium.Icon(color="red", icon="home"),
    ).add_to(m)

    folium.LayerControl().add_to(m)

    st_folium(m, width=900, height=600)

# -------------------------
# Footer
# -------------------------
st.markdown(
    "---\n"
    "_Uses postcode centroid data (postcodes.io) for screening purposes only._"
)
