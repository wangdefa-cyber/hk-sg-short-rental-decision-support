"""Build a real host-listing-neighbourhood network for Gephi."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pandas as pd

from src.config import OUTPUT_DIR, PROCESSED_DIR, TABLES_DIR

CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡"}


def _neighbourhood_key(city_key: str, neighbourhood: str) -> str:
    return f"{city_key}:neighbourhood:{neighbourhood}"


def build_graph(df: pd.DataFrame) -> nx.Graph:
    multi_hosts = df.groupby(["city_key", "host_key"]).filter(lambda x: len(x) >= 2)
    graph = nx.Graph()
    for _, row in multi_hosts.iterrows():
        host_key = row["host_key"]
        listing_key = row["listing_key"]
        district_key = _neighbourhood_key(row["city_key"], row["neighbourhood"])
        if host_key not in graph:
            graph.add_node(
                host_key,
                label=host_key.split(":", 1)[1],
                node_type="host",
                city_key=row["city_key"],
                city_name=CITY_NAMES[row["city_key"]],
            )
        if listing_key not in graph:
            listing_attrs = {
                "label": str(row["listing_id"]),
                "node_type": "listing",
                "city_key": row["city_key"],
                "city_name": CITY_NAMES[row["city_key"]],
                "neighbourhood": row["neighbourhood"],
                "room_type": row["room_type"],
            }
            if pd.notna(row["price_clean"]):
                listing_attrs["price_local"] = float(row["price_clean"])
            graph.add_node(listing_key, **listing_attrs)
        if district_key not in graph:
            graph.add_node(
                district_key,
                label=row["neighbourhood"],
                node_type="neighbourhood",
                city_key=row["city_key"],
                city_name=CITY_NAMES[row["city_key"]],
            )
        graph.add_edge(host_key, listing_key, edge_type="host_operates_listing", weight=1.0)
        graph.add_edge(listing_key, district_key, edge_type="listing_located_in", weight=1.0)
    return graph


def run() -> dict:
    dim = pd.read_parquet(PROCESSED_DIR / "dim_listing.parquet")
    fact = pd.read_parquet(PROCESSED_DIR / "fact_listing_snapshot.parquet")
    df = dim.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    graph = build_graph(df)
    degree = dict(graph.degree())
    nx.set_node_attributes(graph, degree, "degree")

    gephi_dir = OUTPUT_DIR / "gephi"
    gephi_dir.mkdir(parents=True, exist_ok=True)
    nodes = pd.DataFrame(
        [
            {
                "id": node,
                **attrs,
                "degree": degree[node],
            }
            for node, attrs in graph.nodes(data=True)
        ]
    )
    edges = pd.DataFrame(
        [
            {
                "source": source,
                "target": target,
                "type": attrs["edge_type"],
                "weight": attrs["weight"],
            }
            for source, target, attrs in graph.edges(data=True)
        ]
    )
    nodes.to_csv(gephi_dir / "nodes.csv", index=False, encoding="utf-8-sig")
    edges.to_csv(gephi_dir / "edges.csv", index=False, encoding="utf-8-sig")
    nx.write_gexf(graph, gephi_dir / "host_listing_neighbourhood.gexf")

    summary = {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "node_types": nodes["node_type"].value_counts().to_dict(),
        "edge_types": edges["type"].value_counts().to_dict(),
        "connected_components": nx.number_connected_components(graph),
        "density": nx.density(graph),
        "largest_component_nodes": len(max(nx.connected_components(graph), key=len)),
        "by_city": {},
        "scope": "仅多房源房东及其房源，关系来自真实 host_id 和 listing_id；未生成任何虚构边。",
    }
    for city_key, group in nodes.groupby("city_key"):
        summary["by_city"][city_key] = group["node_type"].value_counts().to_dict()
    (TABLES_DIR / "network_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (gephi_dir / "README.md").write_text(
        "# Gephi 导入说明\n\n"
        "1. 打开 Gephi，选择 `host_listing_neighbourhood.gexf`。\n"
        "2. 节点颜色可按 `node_type` 区分房东、房源和社区。\n"
        "3. 节点大小可按 `degree` 或 `weighted_degree` 调整。\n"
        "4. 该网络只包含多房源房东及其真实房源关系，不包含单房源房东。\n"
        "5. 网络只描述平台公开房源关系，不等同于商业垄断关系。\n",
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
