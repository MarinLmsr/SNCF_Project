import pandas as pd
import plotly.graph_objects as go

import app


def test_build_bundle_figure_alterne_boxplot_et_histogramme():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6], "c": [7, 8, 9]})

    fig = app.boxhistplot_bundle_figure(df, ["a", "b", "c"], ncols=4)

    assert len(fig.data) == 6
    assert [type(t) for t in fig.data] == [go.Box, go.Histogram] * 3
    assert [t.name for t in fig.data] == ["a", "a", "b", "b", "c", "c"]
