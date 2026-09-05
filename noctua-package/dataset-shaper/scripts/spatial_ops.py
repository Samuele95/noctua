#!/usr/bin/env python3
"""
spatial_ops.py — the geographic half of the /dataset-shaper step catalog, imported by
shape.py ONLY when a recipe carries a `spatial_*` step.

Two implementations sit behind the same ops. When `pyproj` (and, for joins, `geopandas`) is
installed, coordinates are transformed by the real CRS machinery. When it is not, distances
and grids fall back to a **local equirectangular projection about the data's own centroid**,
in metres, which is accurate to a fraction of a percent over a city and degrades with extent —
and every result records which of the two ran, because a distance whose projection nobody can
name is a number without a unit. `spatial_join` has no fallback: an overlay needs geopandas,
and the step fails with an ERROR naming the missing package rather than approximating it.

Nothing here reprojects without a declared CRS: `parse_geometry` must have supplied one, and
shape.py refuses the recipe otherwise.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

EARTH_R = 6371008.8


def have(mod):
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def _coords(d, lat, lon):
    return (pd.to_numeric(d[lat], errors="coerce").values,
            pd.to_numeric(d[lon], errors="coerce").values)


def local_projection(la, lo):
    """Metres about the centroid: x east, y north. Deterministic, dependency-free, honest
    about being local."""
    lat0, lon0 = float(np.nanmean(la)), float(np.nanmean(lo))
    x = np.radians(lo - lon0) * EARTH_R * math.cos(math.radians(lat0))
    y = np.radians(la - lat0) * EARTH_R
    return x, y, {"kind": "equirectangular about the centroid", "lat0": lat0, "lon0": lon0,
                  "units": "metres", "exact": False}


def project_xy(d, lat, lon, from_crs, to_crs, fitted=None):
    la, lo = _coords(d, lat, lon)
    if to_crs and have("pyproj"):
        from pyproj import Transformer
        tr = Transformer.from_crs(from_crs or "EPSG:4326", to_crs, always_xy=True)
        x, y = tr.transform(lo, la)
        return np.asarray(x), np.asarray(y), {"kind": "pyproj", "from": from_crs, "to": to_crs,
                                              "units": "crs units", "exact": True}
    if fitted:
        lat0, lon0 = fitted["lat0"], fitted["lon0"]
        x = np.radians(lo - lon0) * EARTH_R * math.cos(math.radians(lat0))
        y = np.radians(la - lat0) * EARTH_R
        return x, y, dict(fitted, reused=True)
    return local_projection(la, lo)


def op_spatial_reproject(ctx, step, geom):
    p = step.get("params") or {}
    to_crs = p.get("to_crs")
    lat, lon = geom["lat"], geom["lon"]
    fit = ctx.parts[ctx.fit_part]
    la, lo = _coords(fit, lat, lon)
    _, _, meta = project_xy(fit, lat, lon, ctx.crs, to_crs)
    names = (p.get("x", "x_m"), p.get("y", "y_m"))
    def apply(d):
        d = d.copy()
        x, y, _ = project_xy(d, lat, lon, ctx.crs, to_crs, fitted=meta if not meta.get("exact") else None)
        d[names[0]], d[names[1]] = x, y
        return d
    ctx.set_all(apply)
    for n in names:
        ctx.lineage.setdefault(n, []).append(step["id"])
    ctx.emit(f"# spatial_reproject -> {names} via {meta['kind']} (see the manifest for its parameters)",
             f"_f = FITTED[{repr(step['id'])}]",
             "for k in parts:",
             f"    _la = pd.to_numeric(parts[k][{repr(lat)}], errors='coerce').values",
             f"    _lo = pd.to_numeric(parts[k][{repr(lon)}], errors='coerce').values",
             "    if _f['projection'].get('kind') == 'pyproj':",
             "        from pyproj import Transformer",
             "        _tr = Transformer.from_crs(_f['projection']['from'] or 'EPSG:4326', _f['projection']['to'], always_xy=True)",
             "        _x, _y = _tr.transform(_lo, _la)",
             "    else:",
             "        _lat0, _lon0 = _f['projection']['lat0'], _f['projection']['lon0']",
             f"        _x = np.radians(_lo - _lon0) * {EARTH_R} * np.cos(np.radians(_lat0))",
             f"        _y = np.radians(_la - _lat0) * {EARTH_R}",
             f"    parts[k][{repr(names[0])}], parts[k][{repr(names[1])}] = _x, _y")
    return {"projection": meta, "columns_added": list(names), "to_crs": to_crs}


def op_spatial_distance(ctx, step, geom):
    p = step.get("params") or {}
    to = p.get("to")
    name = p.get("name") or "distance_m"
    lat, lon = geom["lat"], geom["lon"]
    fit = ctx.parts[ctx.fit_part]
    la, lo = _coords(fit, lat, lon)
    _, _, meta = project_xy(fit, lat, lon, ctx.crs, p.get("via_crs"))
    if not isinstance(to, dict) or "lat" not in to or "lon" not in to:
        raise ValueError("spatial_distance needs params.to = {lat, lon} (a reference point); an "
                         "external layer needs spatial_join and geopandas")
    def apply(d):
        d = d.copy()
        x, y, _ = project_xy(d, lat, lon, ctx.crs, p.get("via_crs"),
                             fitted=meta if not meta.get("exact") else None)
        ref = pd.DataFrame({lat: [to["lat"]], lon: [to["lon"]]})
        rx, ry, _ = project_xy(ref, lat, lon, ctx.crs, p.get("via_crs"),
                               fitted=meta if not meta.get("exact") else None)
        d[name] = np.hypot(x - rx[0], y - ry[0])
        return d
    ctx.set_all(apply)
    ctx.lineage.setdefault(name, []).append(step["id"])
    ctx.emit(f"# spatial_distance -> {name} (metres to {to})",
             f"_f = FITTED[{repr(step['id'])}]",
             "for k in parts:",
             f"    _la = pd.to_numeric(parts[k][{repr(lat)}], errors='coerce').values",
             f"    _lo = pd.to_numeric(parts[k][{repr(lon)}], errors='coerce').values",
             "    _lat0, _lon0 = _f['projection']['lat0'], _f['projection']['lon0']",
             f"    _x = np.radians(_lo - _lon0) * {EARTH_R} * np.cos(np.radians(_lat0))",
             f"    _y = np.radians(_la - _lat0) * {EARTH_R}",
             f"    _rx = np.radians({to['lon']} - _lon0) * {EARTH_R} * np.cos(np.radians(_lat0))",
             f"    _ry = np.radians({to['lat']} - _lat0) * {EARTH_R}",
             f"    parts[k][{repr(name)}] = np.hypot(_x - _rx, _y - _ry)")
    return {"projection": meta, "columns_added": [name], "to": to}


def op_spatial_grid(ctx, step, geom):
    p = step.get("params") or {}
    kind = p.get("kind", "square")
    size = float(p.get("size_m", 1000))
    name = p.get("name") or "cell_id"
    agg = p.get("aggregate") or {}
    lat, lon = geom["lat"], geom["lon"]
    fit = ctx.parts[ctx.fit_part]
    _, _, meta = project_xy(fit, lat, lon, ctx.crs, p.get("via_crs"))
    if kind == "h3":
        if not have("h3"):
            raise ValueError("spatial_grid kind=h3 needs the h3 package; use kind=square for a "
                             "metric grid with no extra dependency")
        import h3
        res = int(p.get("resolution", 8))
        def cell(d):
            la, lo = _coords(d, lat, lon)
            return [h3.latlng_to_cell(a, b, res) if np.isfinite(a) and np.isfinite(b) else None
                    for a, b in zip(la, lo)]
    else:
        def cell(d):
            x, y, _ = project_xy(d, lat, lon, ctx.crs, p.get("via_crs"),
                                 fitted=meta if not meta.get("exact") else None)
            return [f"{int(np.floor(a / size))}_{int(np.floor(b / size))}"
                    if np.isfinite(a) and np.isfinite(b) else None for a, b in zip(x, y)]
    added = [name]
    fitted_agg = {}
    if agg:
        f = fit.copy()
        f[name] = cell(f)
        for col, how in agg.items():
            t = f.groupby(name)[col].agg(how)
            fitted_agg[col] = {"how": how, "table": {str(k): float(v) for k, v in t.items()
                                                     if pd.notna(v)}}
            added.append(f"{name}_{col}_{how}")
    def apply(d):
        d = d.copy()
        d[name] = cell(d)
        for col, spec in fitted_agg.items():
            d[f"{name}_{col}_{spec['how']}"] = d[name].map(spec["table"]).astype(float)
        return d
    ctx.set_all(apply)
    for a in added:
        ctx.lineage.setdefault(a, []).append(step["id"])
    ctx.emit(f"# spatial_grid kind={kind} -> {added}",
             f"_f = FITTED[{repr(step['id'])}]")
    if kind == "h3":
        ctx.emit("import h3 as _h3",
                 "for k in parts:",
                 f"    _la = pd.to_numeric(parts[k][{repr(lat)}], errors='coerce').values",
                 f"    _lo = pd.to_numeric(parts[k][{repr(lon)}], errors='coerce').values",
                 f"    parts[k][{repr(name)}] = [_h3.latlng_to_cell(a, b, {int(p.get('resolution', 8))})"
                 "        if np.isfinite(a) and np.isfinite(b) else None for a, b in zip(_la, _lo)]")
    else:
        ctx.emit("for k in parts:",
                 f"    _la = pd.to_numeric(parts[k][{repr(lat)}], errors='coerce').values",
                 f"    _lo = pd.to_numeric(parts[k][{repr(lon)}], errors='coerce').values",
                 "    _lat0, _lon0 = _f['projection']['lat0'], _f['projection']['lon0']",
                 f"    _x = np.radians(_lo - _lon0) * {EARTH_R} * np.cos(np.radians(_lat0))",
                 f"    _y = np.radians(_la - _lat0) * {EARTH_R}",
                 f"    parts[k][{repr(name)}] = [f'{{int(np.floor(a / {size}))}}_{{int(np.floor(b / {size}))}}'"
                 "        if np.isfinite(a) and np.isfinite(b) else None for a, b in zip(_x, _y)]")
    for col, spec in fitted_agg.items():
        agg_col = f"{name}_{col}_{spec['how']}"
        ctx.emit("for k in parts: parts[k][%s] = parts[k][%s].map("
                 "_f['aggregates'][%s]['table']).astype(float)"
                 % (repr(agg_col), repr(name), repr(col)))
    return {"projection": meta, "kind": kind, "size_m": size, "columns_added": added,
            "aggregates": fitted_agg}


def op_spatial_features(ctx, step, geom):
    p = step.get("params") or {}
    want = p.get("features") or ["n_neighbours_within"]
    radius = float(p.get("radius_m", 1000))
    lat, lon = geom["lat"], geom["lon"]
    fit = ctx.parts[ctx.fit_part]
    _, _, meta = project_xy(fit, lat, lon, ctx.crs, p.get("via_crs"))
    added = []
    def apply(d):
        d = d.copy()
        x, y, _ = project_xy(d, lat, lon, ctx.crs, p.get("via_crs"),
                             fitted=meta if not meta.get("exact") else None)
        P = np.column_stack([x, y])
        ok = np.isfinite(P).all(axis=1)
        if "centroid_x" in want:
            d["centroid_x_m"] = x
            added.append("centroid_x_m")
        if "centroid_y" in want:
            d["centroid_y_m"] = y
            added.append("centroid_y_m")
        if "n_neighbours_within" in want and ok.sum() > 1:
            from sklearn.neighbors import NearestNeighbors
            nn = NearestNeighbors(radius=radius).fit(P[ok])
            counts = np.array([len(i) - 1 for i in nn.radius_neighbors(P[ok],
                                                                      return_distance=False)])
            col = np.full(len(d), np.nan)
            col[ok] = counts
            d[f"n_within_{int(radius)}m"] = col
            added.append(f"n_within_{int(radius)}m")
        if "nearest_distance" in want and ok.sum() > 1:
            from sklearn.neighbors import NearestNeighbors
            nn = NearestNeighbors(n_neighbors=2).fit(P[ok])
            dist, _ = nn.kneighbors(P[ok])
            col = np.full(len(d), np.nan)
            col[ok] = dist[:, 1]
            d["nearest_neighbour_m"] = col
            added.append("nearest_neighbour_m")
        return d
    ctx.set_all(apply)
    for a in dict.fromkeys(added):
        ctx.lineage.setdefault(a, []).append(step["id"])
    ctx.emit(f"# spatial_features {want} radius={radius} m",
             f"_f = FITTED[{repr(step['id'])}]['projection']",
             "for k in parts:",
             f"    _la = pd.to_numeric(parts[k][{repr(lat)}], errors='coerce').values",
             f"    _lo = pd.to_numeric(parts[k][{repr(lon)}], errors='coerce').values",
             "    _lat0, _lon0 = _f['lat0'], _f['lon0']",
             f"    _x = np.radians(_lo - _lon0) * {EARTH_R} * np.cos(np.radians(_lat0))",
             f"    _y = np.radians(_la - _lat0) * {EARTH_R}",
             "    _P = np.column_stack([_x, _y]); _ok = np.isfinite(_P).all(axis=1)")
    if "centroid_x" in want:
        ctx.emit("    parts[k]['centroid_x_m'] = _x")
    if "centroid_y" in want:
        ctx.emit("    parts[k]['centroid_y_m'] = _y")
    if "n_neighbours_within" in want:
        ctx.emit("    from sklearn.neighbors import NearestNeighbors as _NN",
                 f"    _nn = _NN(radius={radius}).fit(_P[_ok])",
                 "    _c = np.array([len(i) - 1 for i in _nn.radius_neighbors(_P[_ok], return_distance=False)])",
                 "    _col = np.full(len(parts[k]), np.nan); _col[_ok] = _c",
                 f"    parts[k][{repr('n_within_' + str(int(radius)) + 'm')}] = _col")
    if "nearest_distance" in want:
        ctx.emit("    from sklearn.neighbors import NearestNeighbors as _NN2",
                 "    _nn2 = _NN2(n_neighbors=2).fit(_P[_ok])",
                 "    _d, _ = _nn2.kneighbors(_P[_ok])",
                 "    _col2 = np.full(len(parts[k]), np.nan); _col2[_ok] = _d[:, 1]",
                 "    parts[k]['nearest_neighbour_m'] = _col2")
    return {"projection": meta, "columns_added": sorted(dict.fromkeys(added)), "radius_m": radius,
            "features": want}


def op_spatial_join(ctx, step, geom):
    if not have("geopandas"):
        raise ValueError("spatial_join needs geopandas (and an external layer file); there is no "
                         "honest fallback for an overlay, so this step fails rather than "
                         "approximating it")
    import geopandas as gpd
    from shapely.geometry import Point
    p = step.get("params") or {}
    layer_path = p.get("layer")
    how, pred = p.get("how", "left"), p.get("predicate", "within")
    cols = p.get("columns") or []
    lat, lon = geom["lat"], geom["lon"]
    ext = gpd.read_file(layer_path)
    def apply(d):
        g = gpd.GeoDataFrame(d.copy(), geometry=[Point(b, a) for a, b in zip(
            pd.to_numeric(d[lat], errors="coerce"), pd.to_numeric(d[lon], errors="coerce"))],
            crs=ctx.crs or "EPSG:4326").to_crs(ext.crs)
        j = gpd.sjoin(g, ext[cols + ["geometry"]] if cols else ext, how=how, predicate=pred)
        return pd.DataFrame(j.drop(columns=["geometry", "index_right"], errors="ignore"))
    before = ctx.cols()
    ctx.set_all(apply)
    added = [c for c in ctx.cols() if c not in before]
    for a in added:
        ctx.lineage.setdefault(a, []).append(step["id"])
    import hashlib
    dig = "sha256:" + hashlib.sha256(open(layer_path, "rb").read()).hexdigest()
    ctx.emit(f"# spatial_join with {layer_path} ({dig}) — needs geopandas")
    return {"layer": layer_path, "layer_digest": dig, "how": how, "predicate": pred,
            "columns_added": added}


OPS = {"spatial_reproject": op_spatial_reproject, "spatial_distance": op_spatial_distance,
       "spatial_grid": op_spatial_grid, "spatial_features": op_spatial_features,
       "spatial_join": op_spatial_join}
