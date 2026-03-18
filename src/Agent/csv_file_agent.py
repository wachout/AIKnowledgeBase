from __future__ import annotations

import os
import csv
import json
from typing import List, Dict, Any


class CsvFileAgent:
    """
    CSV 文件解析智能体

    目标：
    - 针对由 Excel 拆分得到的 CSV 文件，自动生成可用于 RAG 的结构化元数据与自然语言描述。
    - 结合列名、列示例值以及 sheet 级描述（如存在 .meta.json）构建「文件描述」。
    """

    def __init__(self):
        pass

    def _load_sheet_meta(self, csv_path: str) -> Dict[str, Any]:
        """
        尝试读取由 split_excel_to_csv 生成的 .meta.json 元数据（若存在）。
        """
        meta_path = csv_path + ".meta.json"
        if not os.path.isfile(meta_path):
            return {}
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _read_csv_preview(self, csv_path: str, max_rows: int = 20) -> Dict[str, Any]:
        """
        读取 CSV 的头部几行，推断列名与示例值。
        """
        if not os.path.isfile(csv_path):
            return {"header": [], "rows": []}

        header: List[str] = []
        rows: List[List[str]] = []

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for idx, row in enumerate(reader):
                if idx == 0:
                    header = [str(c) for c in row]
                else:
                    rows.append([str(c) for c in row])
                if idx >= max_rows:
                    break
        return {"header": header, "rows": rows}

    def parse_csv_file(self, csv_path: str) -> Dict[str, Any]:
        """
        解析单个 CSV，输出：
        - sheet_name / sheet_description（来自 .meta.json 或文件名）
        - columns: 每列的 name / description / sample_values
        - text_summary: 可直接用于 RAG 的自然语言描述
        """
        meta = self._load_sheet_meta(csv_path)
        preview = self._read_csv_preview(csv_path)

        header = preview.get("header") or meta.get("header") or []
        rows = preview.get("rows") or []

        # 推断 sheet 名：优先 .meta.json，其次从文件名中拆分
        sheet_name = meta.get("sheet_name")
        if not sheet_name:
            base = os.path.basename(csv_path)
            name_without_ext = os.path.splitext(base)[0]
            # 约定：{excel_base}__{sheet_name}.csv
            if "__" in name_without_ext:
                _, sheet_part = name_without_ext.split("__", 1)
                sheet_name = sheet_part
            else:
                sheet_name = name_without_ext

        sheet_desc = meta.get("sheet_description") or f"来自工作表「{sheet_name}」的 CSV 数据。"

        # 构造列元数据
        columns_meta: List[Dict[str, Any]] = []
        for col_idx, col_name in enumerate(header):
            samples: List[str] = []
            for r in rows:
                if col_idx < len(r) and r[col_idx] not in ("", None):
                    samples.append(str(r[col_idx]))
                if len(samples) >= 5:
                    break
            col_desc = ""
            if meta.get("columns") and col_idx < len(meta["columns"]):
                # 若 .meta.json 中已有列描述，优先使用
                col_info = meta["columns"][col_idx]
                col_desc = col_info.get("description", "")
                if not samples and col_info.get("sample_values"):
                    samples = [str(v) for v in col_info.get("sample_values") or []]
            if not col_desc:
                if samples:
                    col_desc = f"列「{col_name}」，示例值: {', '.join(samples[:3])}。"
                else:
                    col_desc = f"列「{col_name}」。"
            columns_meta.append(
                {
                    "name": col_name,
                    "description": col_desc,
                    "sample_values": samples,
                }
            )

        # 生成适合写入向量库/ES 的自然语言描述
        col_desc_lines = []
        for c in columns_meta:
            sample_part = ""
            if c["sample_values"]:
                sample_part = f" 示例值: {', '.join(c['sample_values'][:3])}"
            col_line = f"- {c['name']}: {c['description'].rstrip('。')}{sample_part}"
            col_desc_lines.append(col_line)

        text_summary = (
            f"该 CSV 文件来源于 Excel 工作表「{sheet_name}」。\n\n"
            f"工作表描述：{sheet_desc}\n\n"
            f"包含 {len(columns_meta)} 列，列信息如下：\n"
            + "\n".join(col_desc_lines)
        )

        return {
            "csv_path": os.path.abspath(csv_path),
            "sheet_name": sheet_name,
            "sheet_description": sheet_desc,
            "columns": columns_meta,
            "text_summary": text_summary,
        }


def parse_csv_files(csv_paths: List[str]) -> List[Dict[str, Any]]:
    """
    批量解析 CSV 文件，返回包含描述信息的列表。
    """
    agent = CsvFileAgent()
    results: List[Dict[str, Any]] = []
    for p in csv_paths or []:
        try:
            results.append(agent.parse_csv_file(p))
        except Exception:
            continue
    return results

