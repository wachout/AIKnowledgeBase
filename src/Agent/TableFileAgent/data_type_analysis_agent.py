# -*- coding:utf-8 -*-
"""
数据类型分析智能体
了解列的数据类型、数据量
"""

import logging
from typing import Dict, Any, List
import pandas as pd
import numpy as np
from Config.llm_config import get_chat_tongyi

logger = logging.getLogger(__name__)


class DataTypeAnalysisAgent:
    """数据类型分析智能体：分析列的数据类型和数据量"""
    
    def __init__(self):
        self.llm = get_chat_tongyi(temperature=0.3, enable_thinking=False)
    
    def analyze(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析数据类型和数据量
        
        Args:
            file_info: 文件信息字典，包含 data 字段（DataFrame字典）
            
        Returns:
            分析结果字典
        """
        try:
            result = {
                "sheets_analysis": []
            }
            
            for sheet_name, df in file_info.get("data", {}).items():
                sheet_analysis = {
                    "sheet_name": sheet_name,
                    "total_rows": len(df),
                    "total_columns": len(df.columns),
                    "columns_analysis": []
                }
                
                # 分析每一列
                for col_name in df.columns:
                    col_data = df[col_name]
                    col_analysis = self._analyze_column(col_name, col_data)
                    sheet_analysis["columns_analysis"].append(col_analysis)
                
                result["sheets_analysis"].append(sheet_analysis)
            
            logger.info(f"✅ 数据类型分析完成，共分析 {len(result['sheets_analysis'])} 个工作表")
            return result
            
        except Exception as e:
            logger.error(f"❌ 数据类型分析失败: {e}")
            raise
    
    def _analyze_column(self, col_name: str, col_data: pd.Series) -> Dict[str, Any]:
        """
        分析单个列的数据类型和数据量
        
        Args:
            col_name: 列名
            col_data: 列数据（pandas Series）
            
        Returns:
            列分析结果
        """
        # 基本统计
        total_count = int(len(col_data))
        non_null_count = int(col_data.notna().sum())
        null_count = int(total_count - non_null_count)
        null_percentage = float((null_count / total_count * 100) if total_count > 0 else 0)
        
        # 数据类型判断
        dtype = str(col_data.dtype)
        
        # 根据数据类型进行详细分析
        unique_count = int(col_data.nunique())
        analysis = {
            "column_name": col_name,
            "dtype": dtype,
            "total_count": total_count,
            "non_null_count": non_null_count,
            "null_count": null_count,
            "null_percentage": round(null_percentage, 2),
            "data_category": self._categorize_data_type(col_data, dtype),
            "unique_count": unique_count,
            "unique_percentage": round((unique_count / non_null_count * 100) if non_null_count > 0 else 0, 2)
        }
        
        # 数值型数据额外统计
        if pd.api.types.is_numeric_dtype(col_data):
            analysis["numeric_stats"] = {
                "min": float(col_data.min()) if non_null_count > 0 else None,
                "max": float(col_data.max()) if non_null_count > 0 else None,
                "mean": float(col_data.mean()) if non_null_count > 0 else None,
                "median": float(col_data.median()) if non_null_count > 0 else None,
                "std": float(col_data.std()) if non_null_count > 0 else None
            }
        
        # 文本型数据额外统计
        if pd.api.types.is_string_dtype(col_data) or pd.api.types.is_object_dtype(col_data):
            non_null_data = col_data.dropna()
            if len(non_null_data) > 0:
                # 计算平均长度
                lengths = non_null_data.astype(str).str.len()
                analysis["text_stats"] = {
                    "avg_length": float(lengths.mean()),
                    "min_length": int(lengths.min()),
                    "max_length": int(lengths.max()),
                    "most_common": col_data.mode().tolist()[:5] if len(col_data.mode()) > 0 else []
                }
        
        # 日期时间型数据
        if pd.api.types.is_datetime64_any_dtype(col_data):
            non_null_data = col_data.dropna()
            if len(non_null_data) > 0:
                analysis["datetime_stats"] = {
                    "min_date": str(non_null_data.min()),
                    "max_date": str(non_null_data.max()),
                    "date_range_days": (non_null_data.max() - non_null_data.min()).days
                }
        
        return analysis
    
    def _categorize_data_type(self, col_data: pd.Series, dtype: str) -> str:
        """
        对数据类型进行分类
        
        Args:
            col_data: 列数据
            dtype: 数据类型字符串
            
        Returns:
            数据类别：numeric/text/datetime/boolean/categorical
        """
        if pd.api.types.is_numeric_dtype(col_data):
            # 检查是否是整数
            if pd.api.types.is_integer_dtype(col_data):
                # 检查是否是分类数据（唯一值数量少）
                if col_data.nunique() / len(col_data.dropna()) < 0.1:
                    return "categorical_numeric"
                return "integer"
            return "float"
        elif pd.api.types.is_datetime64_any_dtype(col_data):
            return "datetime"
        elif pd.api.types.is_bool_dtype(col_data):
            return "boolean"
        elif pd.api.types.is_string_dtype(col_data) or pd.api.types.is_object_dtype(col_data):
            # 检查是否是分类数据
            unique_ratio = col_data.nunique() / len(col_data.dropna()) if len(col_data.dropna()) > 0 else 0
            if unique_ratio < 0.1:
                return "categorical_text"
            return "text"
        else:
            return "unknown"
