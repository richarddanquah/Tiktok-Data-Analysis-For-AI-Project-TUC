import csv
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

try:
    from openpyxl import Workbook
except Exception:  # pragma: no cover
    Workbook = None


DATASET_CSV = os.path.join("data", "tiktok_travel_visa_dataset.csv")
OUTPUT_DIR = os.path.join("finalreport", "summary_tables")
OUTPUT_XLSX = os.path.join(OUTPUT_DIR, "reproducible_summary_tables.xlsx")


@dataclass
class Row:
    niche_category: str
    hook_style: str
    trending_sound_used: int
    video_duration_seconds: float
    views: int
    likes: int
    comments: int
    shares: int
    saves_or_favorites: int


def _to_int(value: str) -> int:
    s = (value or "").strip().replace(",", "")
    if not s:
        return 0
    return int(float(s))


def _to_float(value: str) -> float:
    s = (value or "").strip().replace(",", "")
    if not s:
        return 0.0
    return float(s)


def load_rows(csv_path: str) -> List[Row]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows: List[Row] = []
        for r in reader:
            rows.append(
                Row(
                    niche_category=(r.get("niche_category") or "").strip(),
                    hook_style=(r.get("hook_style") or "").strip(),
                    trending_sound_used=_to_int(r.get("trending_sound_used") or "0"),
                    video_duration_seconds=_to_float(r.get("video_duration_seconds") or "0"),
                    views=_to_int(r.get("views") or "0"),
                    likes=_to_int(r.get("likes") or "0"),
                    comments=_to_int(r.get("comments") or "0"),
                    shares=_to_int(r.get("shares") or "0"),
                    saves_or_favorites=_to_int(r.get("saves_or_favorites") or "0"),
                )
            )
    return rows


def er_with_saves(row: Row) -> float:
    if row.views <= 0:
        return 0.0
    return (row.likes + row.comments + row.shares + row.saves_or_favorites) / row.views


def er_no_saves(row: Row) -> float:
    if row.views <= 0:
        return 0.0
    return (row.likes + row.comments + row.shares) / row.views


def duration_band(seconds: float) -> str:
    if seconds < 15:
        return "under_15"
    if seconds < 30:
        return "15_30"
    if seconds <= 45:
        return "30_45"
    if seconds <= 60:
        return "45_60"
    return "over_60"


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def grouped_counts(rows: List[Row], key_fn) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    for r in rows:
        out[key_fn(r)] += 1
    return dict(out)


def grouped_means(rows: List[Row], group_key_fn, value_fn) -> Dict[str, float]:
    buckets: Dict[str, List[float]] = defaultdict(list)
    for r in rows:
        buckets[group_key_fn(r)].append(value_fn(r))
    return {k: mean(v) for k, v in buckets.items()}


def write_csv(path: str, header: List[str], data: List[List[object]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(data)


def write_xlsx(path: str, sheets: Dict[str, Tuple[List[str], List[List[object]]]]) -> None:
    if Workbook is None:
        raise RuntimeError(
            "openpyxl is not installed, so .xlsx export is unavailable. "
            "Install it with: python3 -m pip install openpyxl"
        )
    wb = Workbook()
    first = True
    for name, (header, data) in sheets.items():
        if first:
            ws = wb.active
            ws.title = name
            first = False
        else:
            ws = wb.create_sheet(title=name)
        ws.append(header)
        for row in data:
            ws.append(row)
    wb.save(path)


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    rows = load_rows(DATASET_CSV)
    n = len(rows)

    hook_counts = grouped_counts(rows, lambda r: r.hook_style)
    hook_table: List[List[object]] = []
    for k in sorted(hook_counts.keys()):
        c = hook_counts[k]
        hook_table.append([k, c, round((c / n) * 100, 2)])

    hook_er_no = grouped_means(rows, lambda r: r.hook_style, er_no_saves)
    hook_er_w = grouped_means(rows, lambda r: r.hook_style, er_with_saves)
    hook_er_table: List[List[object]] = []
    for k in sorted(set(hook_er_no.keys()) | set(hook_er_w.keys())):
        hook_er_table.append([k, round(hook_er_no.get(k, 0.0) * 100, 2), round(hook_er_w.get(k, 0.0) * 100, 2)])

    band_counts = grouped_counts(rows, lambda r: duration_band(r.video_duration_seconds))
    band_avg_views = grouped_means(rows, lambda r: duration_band(r.video_duration_seconds), lambda r: float(r.views))
    band_avg_er_no = grouped_means(rows, lambda r: duration_band(r.video_duration_seconds), er_no_saves)
    band_avg_er_w = grouped_means(rows, lambda r: duration_band(r.video_duration_seconds), er_with_saves)

    band_order = ["under_15", "15_30", "30_45", "45_60", "over_60"]
    duration_table: List[List[object]] = []
    for b in band_order:
        duration_table.append(
            [
                b,
                band_counts.get(b, 0),
                round(band_avg_views.get(b, 0.0), 0),
                round(band_avg_er_no.get(b, 0.0) * 100, 2),
                round(band_avg_er_w.get(b, 0.0) * 100, 2),
            ]
        )

    cat_avg_er_no = grouped_means(rows, lambda r: r.niche_category, er_no_saves)
    cat_avg_er_w = grouped_means(rows, lambda r: r.niche_category, er_with_saves)
    category_table: List[List[object]] = []
    for c in sorted(set(cat_avg_er_no.keys()) | set(cat_avg_er_w.keys())):
        category_table.append([c, round(cat_avg_er_no.get(c, 0.0) * 100, 2), round(cat_avg_er_w.get(c, 0.0) * 100, 2)])

    trend_views = [r.views for r in rows if r.trending_sound_used == 1]
    nontrend_views = [r.views for r in rows if r.trending_sound_used == 0]
    avg_trend = mean([float(v) for v in trend_views])
    avg_non = mean([float(v) for v in nontrend_views])
    lift = ((avg_trend / avg_non) - 1.0) * 100 if avg_non else 0.0
    trending_table = [
        ["trending_sound_used=1", len(trend_views), round(avg_trend, 0)],
        ["trending_sound_used=0", len(nontrend_views), round(avg_non, 0)],
        ["lift_percent", "", round(lift, 2)],
    ]

    write_csv(os.path.join(OUTPUT_DIR, "hook_distribution.csv"), ["hook_style", "count", "percent"], hook_table)
    write_csv(
        os.path.join(OUTPUT_DIR, "engagement_by_hook.csv"),
        ["hook_style", "avg_engagement_rate_no_saves_percent", "avg_engagement_rate_with_saves_percent"],
        hook_er_table,
    )
    write_csv(
        os.path.join(OUTPUT_DIR, "duration_band_performance.csv"),
        ["duration_band", "count", "avg_views", "avg_engagement_rate_no_saves_percent", "avg_engagement_rate_with_saves_percent"],
        duration_table,
    )
    write_csv(
        os.path.join(OUTPUT_DIR, "category_engagement.csv"),
        ["niche_category", "avg_engagement_rate_no_saves_percent", "avg_engagement_rate_with_saves_percent"],
        category_table,
    )
    write_csv(
        os.path.join(OUTPUT_DIR, "trending_sound_lift.csv"),
        ["group", "count", "avg_views"],
        trending_table,
    )

    if Workbook is not None:
        write_xlsx(
            OUTPUT_XLSX,
            {
                "hook_distribution": (["hook_style", "count", "percent"], hook_table),
                "engagement_by_hook": (
                    ["hook_style", "avg_er_no_saves_percent", "avg_er_with_saves_percent"],
                    hook_er_table,
                ),
                "duration_band_perf": (
                    ["duration_band", "count", "avg_views", "avg_er_no_saves_percent", "avg_er_with_saves_percent"],
                    duration_table,
                ),
                "category_engagement": (
                    ["niche_category", "avg_engagement_rate_no_saves_percent", "avg_engagement_rate_with_saves_percent"],
                    category_table,
                ),
                "trending_sound_lift": (["group", "count", "avg_views"], trending_table),
            },
        )

    print(f"Loaded {n} rows from {DATASET_CSV}")
    print(f"Wrote summary tables to: {OUTPUT_DIR}")
    if Workbook is not None:
        print(f"Wrote Excel workbook to: {OUTPUT_XLSX}")
    else:
        print("Skipped Excel export (openpyxl not installed).")


if __name__ == "__main__":
    main()
