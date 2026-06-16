#!/usr/bin/env python3
"""Train a leakage-free program-edge GNN on canonical SCI JSONL splits.

This is the corrective training path after `GNN_GAN.ipynb` diagnostics showed
that legacy checkpoints depend on GT-derived spatial edge attributes.

Default task:
  room-size-conditioned layout placement

Inputs:
  - room type / order feature
  - target room size (w,h), treated as supplied program information
  - program edges from canonical JSONL

Not used:
  - GT room centers as input
  - GT-derived spatial edge directions/relations

Outputs:
  - checkpoint
  - validation metrics during training
  - test prediction JSONL compatible with scripts/evaluate_layout_metrics.py
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from statistics import mean


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


def import_torch_modules():
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    from torch_geometric.data import Batch, Data
    from torch_geometric.nn import GATv2Conv, global_mean_pool

    return torch, nn, F, Dataset, DataLoader, Batch, Data, GATv2Conv, global_mean_pool


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


def type_id(room: dict, num_types: int, type_source: str) -> int:
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
        value = int(raw)
    except Exception:
        value = num_types - 1
    return min(max(value, 0), num_types - 1)


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
    x1 = min(1.0, max(0.0, cx - w / 2.0))
    y1 = min(1.0, max(0.0, cy - h / 2.0))
    x2 = min(1.0, max(0.0, cx + w / 2.0))
    y2 = min(1.0, max(0.0, cy + h / 2.0))
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return [x1, y1, x2, y2]


def box_iou_cxcywh(torch, a, b, eps: float = 1e-7):
    ax1, ay1 = a[:, 0] - a[:, 2] / 2, a[:, 1] - a[:, 3] / 2
    ax2, ay2 = a[:, 0] + a[:, 2] / 2, a[:, 1] + a[:, 3] / 2
    bx1, by1 = b[:, 0] - b[:, 2] / 2, b[:, 1] - b[:, 3] / 2
    bx2, by2 = b[:, 0] + b[:, 2] / 2, b[:, 1] + b[:, 3] / 2
    ix1, iy1 = torch.maximum(ax1, bx1), torch.maximum(ay1, by1)
    ix2, iy2 = torch.minimum(ax2, bx2), torch.minimum(ay2, by2)
    inter = torch.clamp(ix2 - ix1, min=0) * torch.clamp(iy2 - iy1, min=0)
    area_a = torch.clamp(ax2 - ax1, min=0) * torch.clamp(ay2 - ay1, min=0)
    area_b = torch.clamp(bx2 - bx1, min=0) * torch.clamp(by2 - by1, min=0)
    return inter / (area_a + area_b - inter + eps)


def overlap_loss(torch, boxes, batch_idx):
    loss = boxes.new_tensor(0.0)
    groups = 0
    for gid in batch_idx.unique():
        idx = (batch_idx == gid).nonzero(as_tuple=False).flatten()
        if idx.numel() < 2:
            continue
        b = boxes[idx]
        x1, y1 = b[:, 0] - b[:, 2] / 2, b[:, 1] - b[:, 3] / 2
        x2, y2 = b[:, 0] + b[:, 2] / 2, b[:, 1] + b[:, 3] / 2
        for i in range(idx.numel()):
            ix1 = torch.maximum(x1[i], x1[i + 1 :])
            iy1 = torch.maximum(y1[i], y1[i + 1 :])
            ix2 = torch.minimum(x2[i], x2[i + 1 :])
            iy2 = torch.minimum(y2[i], y2[i + 1 :])
            inter = torch.clamp(ix2 - ix1, min=0) * torch.clamp(iy2 - iy1, min=0)
            if inter.numel():
                loss = loss + inter.mean()
        groups += 1
    return loss / max(groups, 1)


def oob_loss(torch, boxes):
    x1, y1 = boxes[:, 0] - boxes[:, 2] / 2, boxes[:, 1] - boxes[:, 3] / 2
    x2, y2 = boxes[:, 0] + boxes[:, 2] / 2, boxes[:, 1] + boxes[:, 3] / 2
    return (
        torch.relu(-x1).mean()
        + torch.relu(-y1).mean()
        + torch.relu(x2 - 1).mean()
        + torch.relu(y2 - 1).mean()
    )


def adjacency_gap_loss(torch, boxes, edge_index):
    if edge_index.numel() == 0:
        return boxes.new_tensor(0.0)
    src, dst = edge_index
    b1, b2 = boxes[src], boxes[dst]
    dx = torch.abs(b1[:, 0] - b2[:, 0])
    dy = torch.abs(b1[:, 1] - b2[:, 1])
    target_dx = (b1[:, 2] + b2[:, 2]) / 2
    target_dy = (b1[:, 3] + b2[:, 3]) / 2
    gap_x = torch.relu(dx - target_dx)
    gap_y = torch.relu(dy - target_dy)
    return (gap_x + gap_y).mean()


def make_graph(record: dict, torch, Data, num_types: int, type_source: str, copy_input_size: bool):
    rooms = record.get("rooms", [])
    if not rooms:
        raise ValueError(f"{record.get('plan_id')}: no rooms")

    x = []
    y = []
    input_sizes = []
    for idx, room in enumerate(rooms):
        tid = type_id(room, num_types, type_source)
        onehot = [0.0] * num_types
        onehot[tid] = 1.0
        cx, cy, w, h = xyxy_to_cxcywh(room["box"])
        pos = idx / max(len(rooms) - 1, 1)
        x.append(onehot + [w, h, pos, len(rooms) / 10.0])
        y.append([cx, cy, w, h])
        input_sizes.append([w, h])

    id_to_idx = {str(room["id"]): i for i, room in enumerate(rooms)}
    src, dst = [], []
    for edge in record.get("edges", []):
        if len(edge) < 2:
            continue
        a, b = id_to_idx.get(str(edge[0])), id_to_idx.get(str(edge[1]))
        if a is None or b is None or a == b:
            continue
        src.extend([a, b])
        dst.extend([b, a])
    if not src:
        src, dst = [0], [0]

    data = Data(
        x=torch.tensor(x, dtype=torch.float32),
        y=torch.tensor(y, dtype=torch.float32),
        input_sizes=torch.tensor(input_sizes, dtype=torch.float32),
        edge_index=torch.tensor([src, dst], dtype=torch.long),
        edge_attr=torch.ones(len(src), dtype=torch.long),
    )
    data.plan_id = record["plan_id"]
    data.record = record
    data.copy_input_size = copy_input_size
    return data


def build_model(torch, nn, F, GATv2Conv, global_mean_pool, in_dim: int, copy_input_size: bool):
    class ProgramGNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.copy_input_size = copy_input_size
            self.edge_emb = nn.Embedding(2, 24)
            self.node = nn.Sequential(nn.Linear(in_dim, 128), nn.ReLU(), nn.Linear(128, 128))
            self.conv1 = GATv2Conv(128, 128, heads=4, concat=True, edge_dim=24)
            self.norm1 = nn.LayerNorm(512)
            self.conv2 = GATv2Conv(512, 128, heads=4, concat=True, edge_dim=24)
            self.norm2 = nn.LayerNorm(512)
            self.g = nn.Linear(512, 512)
            self.head = nn.Sequential(nn.Linear(512, 256), nn.ReLU(), nn.Linear(256, 2 if copy_input_size else 4))

        def forward(self, batch):
            x = self.node(batch.x)
            e = self.edge_emb(batch.edge_attr.clamp(0, 1))
            h = F.elu(self.norm1(self.conv1(x, batch.edge_index, edge_attr=e)))
            h = F.elu(self.norm2(self.conv2(h, batch.edge_index, edge_attr=e))) + h
            g = self.g(global_mean_pool(h, batch.batch))
            h = h + g[batch.batch]
            raw = self.head(h)
            cx = torch.sigmoid(raw[:, 0])
            cy = torch.sigmoid(raw[:, 1])
            if self.copy_input_size:
                w, hgt = batch.input_sizes[:, 0], batch.input_sizes[:, 1]
            else:
                w = torch.sigmoid(raw[:, 2]) * 0.93 + 0.02
                hgt = torch.sigmoid(raw[:, 3]) * 0.93 + 0.02
            return torch.stack([cx, cy, w, hgt], dim=-1)

    return ProgramGNN()


def evaluate(torch, model, loader, device):
    model.eval()
    vals = []
    with torch.no_grad():
        for batch in loader:
            batch = batch.to(device)
            pred = model(batch)
            vals.extend(box_iou_cxcywh(torch, pred, batch.y).detach().cpu().tolist())
    return mean(vals) if vals else 0.0


def export_predictions(torch, model, records, graphs, Batch, device, output_jsonl: Path, batch_size: int):
    model.eval()
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with torch.no_grad():
        for start in range(0, len(records), batch_size):
            batch_records = records[start : start + batch_size]
            batch_graphs = graphs[start : start + batch_size]
            batch = Batch.from_data_list(batch_graphs).to(device)
            pred = model(batch).detach().cpu().numpy()
            offset = 0
            for record in batch_records:
                rooms = record["rooms"]
                pred_rooms = []
                for room, box in zip(rooms, pred[offset : offset + len(rooms)]):
                    pred_rooms.append({"id": room["id"], "type": room.get("type"), "box": cxcywh_to_xyxy(box)})
                offset += len(rooms)
                rows.append(
                    {
                        "plan_id": record["plan_id"],
                        "family_id": record.get("family_id"),
                        "model_method": "leakage_free_program_gnn",
                        "rooms": pred_rooms,
                        "edges": record.get("edges", []),
                    }
                )
    with output_jsonl.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-jsonl", required=True, type=Path)
    ap.add_argument("--val-jsonl", required=True, type=Path)
    ap.add_argument("--test-jsonl", required=True, type=Path)
    ap.add_argument("--output-jsonl", required=True, type=Path)
    ap.add_argument("--checkpoint-out", required=True, type=Path)
    ap.add_argument("--summary-json", type=Path)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--num-types", type=int, default=8)
    ap.add_argument("--type-source", choices=["order", "type_id", "type_name"], default="order")
    ap.add_argument("--copy-input-size", action="store_true", default=True)
    ap.add_argument("--predict-size", dest="copy_input_size", action="store_false")
    ap.add_argument("--lambda-iou", type=float, default=1.0)
    ap.add_argument("--lambda-overlap", type=float, default=0.5)
    ap.add_argument("--lambda-oob", type=float, default=1.0)
    ap.add_argument("--lambda-adj", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit-train", type=int)
    args = ap.parse_args()

    torch, nn, F, Dataset, DataLoader, Batch, Data, GATv2Conv, global_mean_pool = import_torch_modules()
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_records = read_jsonl(args.train_jsonl)
    val_records = read_jsonl(args.val_jsonl)
    test_records = read_jsonl(args.test_jsonl)
    if args.limit_train:
        train_records = train_records[: args.limit_train]

    train_graphs = [make_graph(r, torch, Data, args.num_types, args.type_source, args.copy_input_size) for r in train_records]
    val_graphs = [make_graph(r, torch, Data, args.num_types, args.type_source, args.copy_input_size) for r in val_records]
    test_graphs = [make_graph(r, torch, Data, args.num_types, args.type_source, args.copy_input_size) for r in test_records]

    in_dim = args.num_types + 4
    model = build_model(torch, nn, F, GATv2Conv, global_mean_pool, in_dim, args.copy_input_size).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)

    train_loader = DataLoader(train_graphs, batch_size=args.batch_size, shuffle=True, collate_fn=Batch.from_data_list)
    val_loader = DataLoader(val_graphs, batch_size=args.batch_size, shuffle=False, collate_fn=Batch.from_data_list)

    best_val = -1.0
    best_epoch = 0
    history = []
    args.checkpoint_out.parent.mkdir(parents=True, exist_ok=True)
    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        for batch in train_loader:
            batch = batch.to(device)
            opt.zero_grad(set_to_none=True)
            pred = model(batch)
            l1 = F.smooth_l1_loss(pred, batch.y)
            liou = 1.0 - box_iou_cxcywh(torch, pred, batch.y).mean()
            lov = overlap_loss(torch, pred, batch.batch)
            loob = oob_loss(torch, pred)
            ladj = adjacency_gap_loss(torch, pred, batch.edge_index)
            loss = l1 + args.lambda_iou * liou + args.lambda_overlap * lov + args.lambda_oob * loob + args.lambda_adj * ladj
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            losses.append(float(loss.detach().cpu()))
        val_iou = evaluate(torch, model, val_loader, device)
        history.append({"epoch": epoch, "train_loss": mean(losses), "val_miou": val_iou})
        print(json.dumps(history[-1]), flush=True)
        if val_iou > best_val:
            best_val = val_iou
            best_epoch = epoch
            torch.save(
                {
                    "epoch": epoch,
                    "model": model.state_dict(),
                    "best_val_miou": best_val,
                    "args": vars(args),
                    "method": "leakage_free_program_gnn",
                },
                args.checkpoint_out,
            )

    ck = torch.load(args.checkpoint_out, map_location=device)
    model.load_state_dict(ck["model"])
    export_predictions(torch, model, test_records, test_graphs, Batch, device, args.output_jsonl, args.batch_size)

    summary = {
        "method": "leakage_free_program_gnn",
        "train_jsonl": str(args.train_jsonl),
        "val_jsonl": str(args.val_jsonl),
        "test_jsonl": str(args.test_jsonl),
        "output_jsonl": str(args.output_jsonl),
        "checkpoint_out": str(args.checkpoint_out),
        "num_train": len(train_records),
        "num_val": len(val_records),
        "num_test": len(test_records),
        "best_epoch": best_epoch,
        "best_val_miou": best_val,
        "copy_input_size": args.copy_input_size,
        "type_source": args.type_source,
        "leakage_statement": "No GT centers or GT-derived spatial edge attributes are used as model inputs.",
        "conditioning_statement": "Uses room sizes as supplied program information." if args.copy_input_size else "Predicts room sizes.",
        "history": history,
    }
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
