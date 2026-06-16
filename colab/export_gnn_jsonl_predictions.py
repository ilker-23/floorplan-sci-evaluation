#!/usr/bin/env python3
"""Export notebook GNN checkpoints to the SCI prediction JSONL schema.

This adapter is for the `GNN_GAN.ipynb` models. It evaluates a saved GNN
checkpoint on the frozen test JSONL records and writes:

  outputs/model_predictions.jsonl

The script does not use target center coordinates. By default it uses room
types and target room sizes as conditioning because the notebook models were
trained with `[one-hot room type, width, height]` node features. Report this as
a size-conditioned model, not as unconditional generation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOM_TYPE_TO_ID = {
    "LivingRoom": 0,
    "MasterRoom": 1,
    "Kitchen": 2,
    "Bathroom": 3,
    "DiningRoom": 4,
    "ChildRoom": 5,
    "StudyRoom": 6,
    "SecondRoom": 7,
    "GuestRoom": 8,
    "Balcony": 9,
    "Storage": 10,
    "WC": 11,
    "Corridor": 12,
    "Other": 13,
}


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row.get("plan_id"), str):
                raise SystemExit(f"{path}:{line_no}: missing string plan_id")
            rows.append(row)
    return rows


def room_type_id(room: dict, num_types: int, type_source: str) -> int:
    if type_source == "order":
        raw = room.get("order")
    elif type_source == "type_id":
        raw = room.get("type_id")
    elif type_source == "type_name":
        raw = ROOM_TYPE_TO_ID.get(str(room.get("type", "Other")), num_types - 1)
    else:
        raise ValueError(f"Unsupported type_source: {type_source}")
    if raw is None:
        raw = ROOM_TYPE_TO_ID.get(str(room.get("type", "Other")), num_types - 1)
    try:
        tid = int(raw)
    except Exception:
        tid = num_types - 1
    return min(max(tid, 0), num_types - 1)


def xyxy_to_cxcywh(box: list[float]) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = map(float, box)
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    w = max(1e-6, x2 - x1)
    h = max(1e-6, y2 - y1)
    return x1 + w / 2.0, y1 + h / 2.0, w, h


def cxcywh_to_xyxy(box) -> list[float]:
    cx, cy, w, h = [float(v) for v in box]
    x1 = cx - w / 2.0
    y1 = cy - h / 2.0
    x2 = cx + w / 2.0
    y2 = cy + h / 2.0
    x1 = min(1.0, max(0.0, x1))
    y1 = min(1.0, max(0.0, y1))
    x2 = min(1.0, max(0.0, x2))
    y2 = min(1.0, max(0.0, y2))
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return [x1, y1, x2, y2]


def spatial_relation(a_box: list[float], b_box: list[float]) -> int:
    ax, ay, _, _ = xyxy_to_cxcywh(a_box)
    bx, by, _, _ = xyxy_to_cxcywh(b_box)
    dx, dy = bx - ax, by - ay
    import math

    angle = math.degrees(math.atan2(dy, dx))
    if 45 <= angle < 135:
        return 1
    if -135 <= angle < -45:
        return 2
    if 135 <= angle or angle < -135:
        return 3
    if -45 <= angle < 45:
        return 4
    return 0


def make_legacy_graph(record: dict, torch, Data, num_types: int, edge_mode: str, size_source: str, type_source: str):
    rooms = record.get("rooms", [])
    if not rooms:
        raise ValueError(f"{record.get('plan_id')}: no rooms")

    type_ids = [room_type_id(room, num_types, type_source) for room in rooms]
    feats = []
    for room, tid in zip(rooms, type_ids):
        onehot = [0.0] * num_types
        onehot[tid] = 1.0
        if size_source == "gt":
            _, _, w, h = xyxy_to_cxcywh(room["box"])
        elif size_source == "constant":
            w, h = 0.2, 0.2
        else:
            raise ValueError(f"Unsupported size_source: {size_source}")
        feats.append(onehot + [float(w), float(h)])

    src, dst, attrs = [], [], []
    if edge_mode == "program_edges":
        id_to_idx = {str(room["id"]): idx for idx, room in enumerate(rooms)}
        for edge in record.get("edges", []):
            if len(edge) < 2:
                continue
            a = id_to_idx.get(str(edge[0]))
            b = id_to_idx.get(str(edge[1]))
            if a is None or b is None or a == b:
                continue
            src.extend([a, b])
            dst.extend([b, a])
            attrs.extend([1, 1])
    elif edge_mode == "complete_constant":
        for i in range(len(rooms)):
            for j in range(len(rooms)):
                if i == j:
                    continue
                src.append(i)
                dst.append(j)
                attrs.append(1)
    elif edge_mode == "spatial_from_gt":
        for i, room_i in enumerate(rooms):
            for j, room_j in enumerate(rooms):
                if i == j:
                    continue
                rel = spatial_relation(room_i["box"], room_j["box"])
                if rel != 0:
                    src.append(i)
                    dst.append(j)
                    attrs.append(rel)
    else:
        raise ValueError(f"Unsupported legacy edge_mode: {edge_mode}")
    if not src:
        src, dst, attrs = [0], [0], [0]

    return Data(
        x=torch.tensor(feats, dtype=torch.float32),
        edge_index=torch.tensor([src, dst], dtype=torch.long),
        edge_attr=torch.tensor(attrs, dtype=torch.long),
    )


def make_v2_graph(record: dict, torch, Data, num_types: int, size_source: str, type_source: str):
    rooms = record.get("rooms", [])
    if not rooms:
        raise ValueError(f"{record.get('plan_id')}: no rooms")

    type_ids = [room_type_id(room, num_types, type_source) for room in rooms]
    feats = []
    for room, tid in zip(rooms, type_ids):
        onehot = [0.0] * num_types
        onehot[tid] = 1.0
        if size_source == "gt":
            _, _, w, h = xyxy_to_cxcywh(room["box"])
            feats.append(onehot + [float(w), float(h)])
        elif size_source == "constant":
            feats.append(onehot + [0.2, 0.2])
        else:
            raise ValueError(f"Unsupported size_source: {size_source}")

    src, dst, attrs = [], [], []
    for i, ti in enumerate(type_ids):
        for j, tj in enumerate(type_ids):
            if i == j:
                continue
            src.append(i)
            dst.append(j)
            attrs.append(ti * num_types + tj)
    if not src:
        src, dst, attrs = [0], [0], [0]

    return Data(
        x=torch.tensor(feats, dtype=torch.float32),
        edge_index=torch.tensor([src, dst], dtype=torch.long),
        edge_attr=torch.tensor(attrs, dtype=torch.long),
    )


def import_torch_modules():
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric.data import Batch, Data
    from torch_geometric.nn import GATv2Conv, global_mean_pool

    return torch, nn, F, Batch, Data, GATv2Conv, global_mean_pool


def build_legacy_model(nn, F, GATv2Conv, num_types: int):
    class RelationalFloorPlanGNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.edge_embedding = nn.Embedding(7, 16)
            self.conv1 = GATv2Conv(num_types + 2, 128, heads=4, edge_dim=16, concat=True)
            self.conv2 = GATv2Conv(512, 128, heads=4, edge_dim=16, concat=True)
            self.regressor = nn.Sequential(nn.Linear(512, 256), nn.ReLU(), nn.Linear(256, 4), nn.Sigmoid())

        def forward(self, data):
            x, edge_index, edge_attr = data.x, data.edge_index, data.edge_attr.clamp(min=0, max=6)
            edge_emb = self.edge_embedding(edge_attr)
            x = self.conv1(x, edge_index, edge_attr=edge_emb)
            x = F.elu(x)
            x = self.conv2(x, edge_index, edge_attr=edge_emb)
            x = F.elu(x)
            return self.regressor(x)

    return RelationalFloorPlanGNN()


def build_v2_model(torch, nn, F, GATv2Conv, global_mean_pool, num_types: int):
    class RelationalGNNv2(nn.Module):
        def __init__(self):
            super().__init__()
            self.edge_emb = nn.Embedding(num_types * num_types + 1, 32)
            self.node_mlp = nn.Sequential(nn.Linear(num_types + 2, 128), nn.ReLU(), nn.Linear(128, 128))
            self.conv1 = GATv2Conv(128, 128, heads=4, concat=True, edge_dim=32)
            self.norm1 = nn.LayerNorm(128 * 4)
            self.conv2 = GATv2Conv(128 * 4, 128, heads=4, concat=True, edge_dim=32)
            self.norm2 = nn.LayerNorm(128 * 4)
            self.conv3 = GATv2Conv(128 * 4, 128, heads=4, concat=True, edge_dim=32)
            self.norm3 = nn.LayerNorm(128 * 4)
            self.g_proj = nn.Linear(128 * 4, 128 * 4)
            self.head = nn.Sequential(nn.Linear(128 * 4, 256), nn.ReLU(), nn.Linear(256, 4))
            self.min_w = 0.02
            self.min_h = 0.02
            self.max_w = 0.95
            self.max_h = 0.95

        def forward(self, batch):
            x = self.node_mlp(batch.x)
            e = self.edge_emb(batch.edge_attr.clamp(min=0, max=num_types * num_types))
            x1 = self.conv1(x, batch.edge_index, edge_attr=e)
            x1 = F.elu(self.norm1(x1))
            x2 = self.conv2(x1, batch.edge_index, edge_attr=e)
            x2 = F.elu(self.norm2(x2)) + x1
            x3 = self.conv3(x2, batch.edge_index, edge_attr=e)
            x3 = F.elu(self.norm3(x3)) + x2
            g = global_mean_pool(x3, batch.batch)
            g = self.g_proj(g)
            x3 = x3 + g[batch.batch]
            raw = self.head(x3)
            cx = torch.sigmoid(raw[:, 0])
            cy = torch.sigmoid(raw[:, 1])
            w = torch.sigmoid(raw[:, 2]) * (self.max_w - self.min_w) + self.min_w
            h = torch.sigmoid(raw[:, 3]) * (self.max_h - self.min_h) + self.min_h
            return torch.stack([cx, cy, w, h], dim=-1)

    return RelationalGNNv2()


def load_state_dict(torch, checkpoint_path: Path):
    obj = torch.load(checkpoint_path, map_location="cpu")
    if isinstance(obj, dict) and "model" in obj:
        return obj["model"], {"checkpoint_format": "dict_with_model", "epoch": obj.get("epoch"), "best_val": obj.get("best_val")}
    if isinstance(obj, dict):
        return obj, {"checkpoint_format": "raw_state_dict"}
    raise SystemExit(f"Unsupported checkpoint object type: {type(obj).__name__}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ground-truth", required=True, type=Path, help="Frozen test_ground_truth.jsonl")
    ap.add_argument("--checkpoint", required=True, type=Path)
    ap.add_argument("--output-jsonl", required=True, type=Path)
    ap.add_argument("--output-summary", type=Path)
    ap.add_argument("--architecture", choices=["legacy_gat10", "v2_gat"], default="legacy_gat10")
    ap.add_argument(
        "--legacy-edge-mode",
        choices=["program_edges", "complete_constant", "spatial_from_gt"],
        default="program_edges",
    )
    ap.add_argument("--size-source", choices=["gt", "constant"], default="gt")
    ap.add_argument("--type-source", choices=["order", "type_id", "type_name"], default="type_id")
    ap.add_argument("--num-types", type=int, default=8)
    ap.add_argument("--batch-size", type=int, default=64)
    args = ap.parse_args()

    torch, nn, F, Batch, Data, GATv2Conv, global_mean_pool = import_torch_modules()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    records = read_jsonl(args.ground_truth)
    if args.architecture == "legacy_gat10":
        model = build_legacy_model(nn, F, GATv2Conv, args.num_types)
    else:
        model = build_v2_model(torch, nn, F, GATv2Conv, global_mean_pool, args.num_types)
    state, ck_meta = load_state_dict(torch, args.checkpoint)
    model.load_state_dict(state)
    model.to(device)
    model.eval()

    graphs = []
    for record in records:
        if args.architecture == "legacy_gat10":
            graph = make_legacy_graph(
                record,
                torch,
                Data,
                args.num_types,
                args.legacy_edge_mode,
                args.size_source,
                args.type_source,
            )
        else:
            graph = make_v2_graph(record, torch, Data, args.num_types, args.size_source, args.type_source)
        graphs.append(graph)

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    predictions = []
    with torch.no_grad():
        for start in range(0, len(records), args.batch_size):
            batch_records = records[start : start + args.batch_size]
            batch_graphs = graphs[start : start + args.batch_size]
            batch = Batch.from_data_list(batch_graphs).to(device)
            pred = model(batch).detach().cpu().numpy()
            node_offset = 0
            for record in batch_records:
                rooms = record.get("rooms", [])
                room_preds = pred[node_offset : node_offset + len(rooms)]
                node_offset += len(rooms)
                out_rooms = []
                for room, box_cxcywh in zip(rooms, room_preds):
                    out_rooms.append(
                        {
                            "id": str(room["id"]),
                            "type": room.get("type"),
                            "box": cxcywh_to_xyxy(box_cxcywh),
                        }
                    )
                predictions.append(
                    {
                        "plan_id": record["plan_id"],
                        "family_id": record.get("family_id"),
                        "model_method": f"notebook_gnn_{args.architecture}",
                        "rooms": out_rooms,
                        "edges": record.get("edges", []),
                    }
                )

    with args.output_jsonl.open("w", encoding="utf-8") as f:
        for row in predictions:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "method": f"notebook_gnn_{args.architecture}",
        "ground_truth": str(args.ground_truth),
        "checkpoint": str(args.checkpoint),
        "output_jsonl": str(args.output_jsonl),
        "num_predictions": len(predictions),
        "num_rooms": sum(len(r.get("rooms", [])) for r in predictions),
        "architecture": args.architecture,
        "legacy_edge_mode": args.legacy_edge_mode if args.architecture == "legacy_gat10" else None,
        "size_source": args.size_source,
        "type_source": args.type_source,
        "conditioning_warning": (
            "Uses target room sizes as conditioning. Report as room-size-conditioned; "
            "do not call this unconditional generation."
            if args.size_source == "gt"
            else "Uses constant room sizes; likely out of distribution for checkpoints trained with GT sizes."
        ),
        "leakage_warning": (
            "Uses GT box centers to construct spatial edge attributes, matching the legacy notebook training path. "
            "This is not leakage-free and must not be used as the final SCI model claim."
            if args.legacy_edge_mode == "spatial_from_gt"
            else None
        ),
        "checkpoint_meta": ck_meta,
    }
    if args.output_summary:
        args.output_summary.parent.mkdir(parents=True, exist_ok=True)
        args.output_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
