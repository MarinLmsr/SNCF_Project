import streamlit as st
import pandas as pd
import plotly.express as px

file_path = "/Users/jbg/SandBoxPython/LAMBERT_IADATA700/Sncf_Project/SNCF_Project/data/regularite-mensuelle-tgv-aqst.csv"


geogares = {
    "BORDEAUX ST JEAN": [44.8261, -0.5574],
    "LE MANS": [48.0063, 0.1982],
    "PARIS MONTPARNASSE": [48.8404, 2.3199],
    "POITIERS": [46.5804, 0.3266],
    "ST MALO": [48.6519, -2.0185],
    "TOULOUSE MATABIAU": [43.6110, 1.4539],
    "VANNES": [47.6576, -2.7584],
    "REIMS": [49.2591, 4.0246],
    "DOUAI": [50.3708, 3.0910],
    "LILLE": [50.6363, 3.0713],
    "PARIS NORD": [48.8809, 2.3553],
    "AIX EN PROVENCE TGV": [43.3910, 5.3167],
    "ANNECY": [45.9046, 6.1231],
    "GRENOBLE": [45.1945, 5.7147],
    "LYON PART DIEU": [45.7602, 4.8594],
    "MACON LOCHE": [46.3256, 4.8040],
    "MARSEILLE ST CHARLES": [43.3027, 5.3803],
    "MONTPELLIER": [43.6058, 3.8809],
    "PARIS LYON": [48.8443, 2.3743],
    "BARCELONA": [41.3791, 2.1396],
    "FRANCFORT": [50.1069, 8.6631],
    "MADRID": [40.4061, -3.6908],
    "ST PIERRE DES CORPS": [47.3895, 0.7166],
    "TOURS": [47.3895, 0.6937],
    "PARIS EST": [48.8839, 2.3596],
    "PARIS VAUGIRARD": [48.8404, 2.3199],
    "RENNES": [48.1032, -1.6724],
    "BESANCON FRANCHE COMTE TGV": [47.2474, 5.9520],
    "DIJON VILLE": [47.3222, 5.0220],
    "PERPIGNAN": [42.6957, 2.8815],
    "VALENCE ALIXAN TGV": [44.9927, 4.8896],
    "STUTTGART": [48.7862, 9.1837],
    "METZ": [49.1098, 6.1774],
    "NANCY": [48.6900, 6.1766],
    "NANTES": [47.2175, -1.5402],
    "LE CREUSOT MONTCEAU MONTCHANIN": [46.7712, 4.4192],
    "MARNE LA VALLEE": [48.8757, 2.6510],
    "NICE VILLE": [43.7046, 7.2611],
    "ITALIE": [45.8844, 8.6041],
    "LAUSANNE": [46.5167, 6.6292],
    "ANGOULEME": [45.6497, 0.1600],
    "BREST": [48.3881, -4.4798],
    "LA ROCHELLE VILLE": [46.1574, -1.1463],
    "QUIMPER": [47.9955, -4.0957],
    "STRASBOURG": [48.5853, 7.7339],
    "AVIGNON TGV": [43.9257, 4.7795],
    "MULHOUSE VILLE": [47.7464, 7.3417],
    "SAINT ETIENNE CHATEAUCREUX": [45.4403, 4.4001],
    "GENEVE": [46.2100, 6.1425],
    "ANGERS SAINT LAUD": [47.4603, -0.5533],
    "LAVAL": [48.0683, -0.7654],
    "ARRAS": [50.2863, 2.7774],
    "DUNKERQUE": [51.0345, 2.3763],
    "TOURCOING": [50.7221, 3.1609],
    "BELLEGARDE (AIN)": [46.1060, 5.8244],
    "CHAMBERY CHALLES LES EAUX": [45.5836, 5.9198],
    "NIMES": [43.8324, 4.3649],
    "TOULON": [43.1260, 5.9345],
    "ZURICH": [47.3777, 8.5404],
}


try:
    gdf = pd.read_csv(geofile_path, sep=";")
except FileNotFoundError:
    st.error(f"Le fichier {geofile_path} est introuvable.")

try:
    df = pd.read_csv(file_path, sep=";")
except FileNotFoundError:
    st.error(f"Le fichier {file_path} est introuvable.")

gdf = (
    pd.DataFrame.from_dict(geogares, orient="index", columns=["lat", "lon"])
    .reset_index()
    .rename(columns={"index": "Nom_Gare"})
)
print(gdf.head())

gares = df["Gare de départ"].unique().tolist()


def carte(gares):
    d = gdf[gdf["Nom_Gare"].isin(gares)]

    fig = px.scatter_map(
        d,
        lat="lat",
        lon="lon",
        hover_name="Nom_Gare",
        zoom=4.5,
        center={"lat": 46.6, "lon": 2.4},
        height=600,
        map_style="open-street-map",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    fig.update_traces(marker=dict(size=14, color="red"))
    st.plotly_chart(fig, use_container_width=True)
    return d


geo = carte(gares)
