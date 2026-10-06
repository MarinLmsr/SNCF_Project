"""Interface Streamlit du projet d'analyse de la ponctualité des TGV."""

import streamlit as st


def main() -> None:
    """Afficher la structure de l'application en français."""
    st.set_page_config(
        page_title="SNCF — Ponctualité des TGV",
        page_icon="🚄",
        layout="wide",
    )

    st.title("🚄 Analyse de la ponctualité des TGV")
    st.caption("Projet en cours de développement — données à intégrer.")

    vue_ensemble, lignes, causes = st.tabs(
        ["Vue d'ensemble", "Détail par ligne", "Causes des retards"]
    )

    with vue_ensemble:
        st.header("Vue d'ensemble du réseau")
        st.write(
            "Explorez la ponctualité des TGV, les annulations "
            "et les différences entre les lignes."
        )
        st.info(
            "À venir : indicateurs clés et classement des lignes "
            "selon leurs taux de retard et d'annulation."
        )

    with lignes:
        st.header("Détail par ligne")
        st.write(
            "Analysez une liaison entre une gare de départ "
            "et une gare d'arrivée."
        )
        st.info(
            "À venir : sélection des gares et évolution mensuelle "
            "des retards et des annulations."
        )

    with causes:
        st.header("Causes des retards")
        st.write("Découvrez les principales causes de retard des TGV.")
        st.info(
            "À venir : répartition des causes et évolution "
            "selon la période et la ligne sélectionnées."
        )


if __name__ == "__main__":
    main()
