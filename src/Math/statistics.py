# -*- coding:utf-8 -*-
"""
统计分析模块
提供各种统计计算功能，包括描述性统计、分布分析、相关性分析等
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import logging
from collections import Counter
import re
from datetime import datetime

# 尝试导入 scipy，如果没有则使用替代方案
try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ scipy 未安装，部分统计功能可能受限")

logger = logging.getLogger(__name__)


class StatisticsCalculator:
    """统计分析计算器"""
    
    def __init__(self, csv_file_path: str):
        """
        初始化统计计算器
        
        Args:
            csv_file_path: CSV文件路径
        """
        self.csv_file_path = csv_file_path
        self.df = None
        self._load_data()
    
    def _load_data(self):
        """加载CSV数据"""
        try:
            self.df = pd.read_csv(self.csv_file_path, encoding='utf-8')
            logger.info(f"✅ 成功加载CSV文件: {self.csv_file_path}, 共 {len(self.df)} 行")
        except Exception as e:
            logger.error(f"❌ 加载CSV文件失败: {e}")
            self.df = pd.DataFrame()
    
    def calculate_all_statistics(self, columns_types: List[str] = None) -> Dict[str, Any]:
        """
        计算所有统计指标
        
        Args:
            columns_types: 列类型列表，用于识别数值型、字符串型等
        
        Returns:
            包含所有统计结果的字典
        """
        if self.df is None or self.df.empty:
            logger.warning("⚠️ 数据为空，无法进行统计分析")
            return {}
        
        result = {}
        
        # 识别数值型列和字符串型列
        # columns_types 包含 SQL 数据类型（如 varchar(64), int, datetime 等）
        numeric_cols = []
        string_cols = []
        datetime_cols = []
        
        if columns_types:
            for i, col_type in enumerate(columns_types):
                if i < len(self.df.columns):
                    col_name = self.df.columns[i]
                    col_type_str = str(col_type).lower().strip()
                    
                    # SQL 数值型数据类型
                    numeric_keywords = [
                        'int', 'integer', 'bigint', 'smallint', 'tinyint', 'mediumint',
                        'float', 'double', 'decimal', 'numeric', 'number', 'real',
                        'money', 'smallmoney', 'bit', 'serial', 'bigserial'
                    ]
                    
                    # SQL 日期时间型数据类型
                    datetime_keywords = [
                        'date', 'time', 'datetime', 'timestamp', 'year',
                        'datetime2', 'datetimeoffset', 'smalldatetime'
                    ]
                    
                    # SQL 字符串型数据类型
                    string_keywords = [
                        'varchar', 'char', 'text', 'nvarchar', 'nchar', 'ntext',
                        'string', 'clob', 'blob', 'binary', 'varbinary'
                    ]
                    
                    # 检查是否为数值型（匹配完整的 SQL 类型名，如 "int", "varchar(64)" 中的 "varchar"）
                    is_numeric = any(keyword in col_type_str for keyword in numeric_keywords)
                    is_datetime = any(keyword in col_type_str for keyword in datetime_keywords)
                    is_string = any(keyword in col_type_str for keyword in string_keywords)
                    
                    if is_datetime:
                        datetime_cols.append(col_name)
                    elif is_numeric:
                        numeric_cols.append(col_name)
                    elif is_string:
                        string_cols.append(col_name)
                    else:
                        # 如果无法识别，尝试根据实际数据推断
                        # 优先检查是否为数值型
                        if pd.api.types.is_numeric_dtype(self.df[col_name]):
                            numeric_cols.append(col_name)
                        elif pd.api.types.is_datetime64_any_dtype(self.df[col_name]):
                            datetime_cols.append(col_name)
                        else:
                            string_cols.append(col_name)
        else:
            # 如果没有提供 columns_types，自动识别
            numeric_cols = list(self.df.select_dtypes(include=[np.number]).columns)
            string_cols = list(self.df.select_dtypes(include=['object']).columns)
            datetime_cols = []
            for col in self.df.columns:
                if pd.api.types.is_datetime64_any_dtype(self.df[col]):
                    datetime_cols.append(col)
        
        # 数值类列：进行数理统计
        if numeric_cols:
            # 1. 描述性统计
            result['descriptive_statistics'] = self.descriptive_statistics(numeric_cols)
            
            # 2. 分布分析
            result['distribution_analysis'] = self.distribution_analysis(numeric_cols)
            
            # 3. 相关性分析（需要至少2个数值列）
            if len(numeric_cols) > 1:
                result['correlation_analysis'] = self.correlation_analysis(numeric_cols)
        
        # 文本类列：进行文本分析统计
        if string_cols:
            # 1. 频率分析
            result['frequency_analysis'] = self.frequency_analysis(string_cols)
            
            # # 2. 文本分析
            # result['text_analysis'] = self.text_analysis(string_cols)
            
            # # 3. 字符串分析
            # result['string_analysis'] = self.string_analysis(string_cols)
        
        # 日期时间列：进行时间序列分析
        if datetime_cols:
            # 1. 趋势分析（时间序列）
            if numeric_cols:
                result['trend_analysis'] = self.trend_analysis(datetime_cols, numeric_cols)
            
            # 2. 时间序列分析
            if numeric_cols:
                result['time_series_analysis'] = self.time_series_analysis(datetime_cols, numeric_cols)
        
        # 混合分析（涉及文本和数值的关联）
        if string_cols and numeric_cols:
            # 分组统计（按文本列分组，统计数值列）
            result['grouped_statistics'] = self.grouped_statistics(string_cols, numeric_cols)
            
            # 两列相关匹配（文本列与数值列的关联）
            result['column_correlation'] = self.column_correlation_matching(string_cols, numeric_cols)
        
        # # 两列联合分析（所有列之间的联合分析）
        # all_cols = numeric_cols + string_cols + datetime_cols
        # if len(all_cols) >= 2:
        #     result['column_joint_analysis'] = self.column_joint_analysis(all_cols)
        
        return result
    
    def descriptive_statistics(self, numeric_cols: List[str]) -> Dict[str, Any]:
        """
        描述性统计：总数、均值、中位数、众数、方差、标准差、四分位数、极值等
        
        Args:
            numeric_cols: 数值型列名列表
        
        Returns:
            描述性统计结果
        """
        result = {}
        
        for col in numeric_cols:
            if col not in self.df.columns:
                continue
            
            series = self.df[col].dropna()
            if len(series) == 0:
                continue
            
            result[col] = {
                'count': int(series.count()),
                'mean': float(series.mean()) if pd.api.types.is_numeric_dtype(series) else None,
                'median': float(series.median()) if pd.api.types.is_numeric_dtype(series) else None,
                'mode': series.mode().tolist() if len(series.mode()) > 0 else None,
                'variance': float(series.var()) if pd.api.types.is_numeric_dtype(series) else None,
                'std': float(series.std()) if pd.api.types.is_numeric_dtype(series) else None,
                'min': float(series.min()) if pd.api.types.is_numeric_dtype(series) else None,
                'max': float(series.max()) if pd.api.types.is_numeric_dtype(series) else None,
                'q25': float(series.quantile(0.25)) if pd.api.types.is_numeric_dtype(series) else None,
                'q50': float(series.quantile(0.50)) if pd.api.types.is_numeric_dtype(series) else None,
                'q75': float(series.quantile(0.75)) if pd.api.types.is_numeric_dtype(series) else None,
                'range': float(series.max() - series.min()) if pd.api.types.is_numeric_dtype(series) else None,
            }
        
        return result
    
    def distribution_analysis(self, numeric_cols: List[str]) -> Dict[str, Any]:
        """
        分布分析：数据分布特征、偏度、峰度等
        
        Args:
            numeric_cols: 数值型列名列表
        
        Returns:
            分布分析结果
        """
        result = {}
        
        for col in numeric_cols:
            if col not in self.df.columns:
                continue
            
            series = self.df[col].dropna()
            if len(series) == 0 or not pd.api.types.is_numeric_dtype(series):
                continue
            
            try:
                result[col] = {
                    'skewness': float(stats.skew(series)),  # 偏度
                    'kurtosis': float(stats.kurtosis(series)),  # 峰度
                    'distribution_type': self._identify_distribution(series),
                }
            except Exception as e:
                logger.warning(f"⚠️ 计算 {col} 的分布特征失败: {e}")
        
        return result
    
    def _identify_distribution(self, series: pd.Series) -> str:
        """识别数据分布类型"""
        try:
            # 简单的分布识别逻辑
            if HAS_SCIPY:
                skew = stats.skew(series)
            else:
                skew = series.skew()
            
            if abs(skew) < 0.5:
                return "近似正态分布"
            elif skew > 0.5:
                return "右偏分布"
            else:
                return "左偏分布"
        except:
            return "未知分布"
    
    def correlation_analysis(self, numeric_cols: List[str]) -> Dict[str, Any]:
        """
        相关性分析：变量间的相关关系
        
        Args:
            numeric_cols: 数值型列名列表
        
        Returns:
            相关性分析结果
        """
        if len(numeric_cols) < 2:
            return {}
        
        try:
            # 计算相关系数矩阵
            corr_matrix = self.df[numeric_cols].corr()
            
            # 转换为字典格式
            result = {
                'correlation_matrix': corr_matrix.to_dict(),
                'strong_correlations': []
            }
            
            # 找出强相关关系（|r| > 0.7）
            for i, col1 in enumerate(numeric_cols):
                for col2 in numeric_cols[i+1:]:
                    corr_value = corr_matrix.loc[col1, col2]
                    if abs(corr_value) > 0.7:
                        result['strong_correlations'].append({
                            'column1': col1,
                            'column2': col2,
                            'correlation': float(corr_value)
                        })
            
            return result
        except Exception as e:
            logger.warning(f"⚠️ 相关性分析失败: {e}")
            return {}
    
    def grouped_statistics(self, group_cols: List[str], numeric_cols: List[str]) -> Dict[str, Any]:
        """
        分组统计：按不同维度进行分组统计
        
        Args:
            group_cols: 分组列名列表
            numeric_cols: 数值型列名列表
        
        Returns:
            分组统计结果
        """
        result = {}
        
        for group_col in group_cols:
            if group_col not in self.df.columns:
                continue
            
            try:
                grouped = self.df.groupby(group_col)
                
                group_stats = {}
                for num_col in numeric_cols:
                    if num_col not in self.df.columns:
                        continue
                    
                    if pd.api.types.is_numeric_dtype(self.df[num_col]):
                        group_stats[num_col] = {
                            'count': grouped[num_col].count().to_dict(),
                            'mean': grouped[num_col].mean().to_dict(),
                            'median': grouped[num_col].median().to_dict(),
                            'std': grouped[num_col].std().to_dict(),
                            'min': grouped[num_col].min().to_dict(),
                            'max': grouped[num_col].max().to_dict(),
                        }
                
                result[group_col] = {
                    'group_count': int(grouped.size().sum()),
                    'unique_groups': int(grouped.ngroups),
                    'group_sizes': grouped.size().to_dict(),
                    'statistics': group_stats
                }
            except Exception as e:
                logger.warning(f"⚠️ 分组统计失败 ({group_col}): {e}")
        
        return result
    
    def trend_analysis(self, datetime_cols: List[str], numeric_cols: List[str]) -> Dict[str, Any]:
        """
        趋势分析：时间序列趋势、变化率等
        
        Args:
            datetime_cols: 日期时间列名列表
            numeric_cols: 数值型列名列表
        
        Returns:
            趋势分析结果
        """
        result = {}
        
        for dt_col in datetime_cols:
            if dt_col not in self.df.columns:
                continue
            
            try:
                # 转换为日期时间类型
                df_copy = self.df.copy()
                df_copy[dt_col] = pd.to_datetime(df_copy[dt_col], errors='coerce')
                df_copy = df_copy.dropna(subset=[dt_col])
                
                if len(df_copy) == 0:
                    continue
                
                # 按时间排序
                df_copy = df_copy.sort_values(by=dt_col)
                
                trend_result = {}
                for num_col in numeric_cols:
                    if num_col not in df_copy.columns or not pd.api.types.is_numeric_dtype(df_copy[num_col]):
                        continue
                    
                    # 计算变化率
                    values = df_copy[num_col].dropna()
                    if len(values) > 1:
                        change_rate = ((values.iloc[-1] - values.iloc[0]) / values.iloc[0]) * 100 if values.iloc[0] != 0 else 0
                        
                        trend_result[num_col] = {
                            'trend': 'increasing' if change_rate > 0 else 'decreasing' if change_rate < 0 else 'stable',
                            'change_rate': float(change_rate),
                            'first_value': float(values.iloc[0]),
                            'last_value': float(values.iloc[-1]),
                        }
                
                if trend_result:
                    result[dt_col] = trend_result
            except Exception as e:
                logger.warning(f"⚠️ 趋势分析失败 ({dt_col}): {e}")
        
        return result
    
    def frequency_analysis(self, string_cols: List[str]) -> Dict[str, Any]:
        """
        频率分析：类别频率、出现次数等
        
        Args:
            string_cols: 字符串型列名列表
        
        Returns:
            频率分析结果
        """
        result = {}
        
        for col in string_cols:
            if col not in self.df.columns:
                continue
            
            try:
                value_counts = self.df[col].value_counts()
                result[col] = {
                    'unique_count': int(self.df[col].nunique()),
                    'total_count': int(len(self.df[col])),
                    'frequency': value_counts.to_dict(),
                    'top_10': value_counts.head(10).to_dict(),
                }
            except Exception as e:
                logger.warning(f"⚠️ 频率分析失败 ({col}): {e}")
        
        return result
    
    def text_analysis(self, string_cols: List[str]) -> Dict[str, Any]:
        """
        文本分析：关键词提取、情感分析等
        
        Args:
            string_cols: 字符串型列名列表
        
        Returns:
            文本分析结果
        """
        result = {}
        
        for col in string_cols:
            if col not in self.df.columns:
                continue
            
            try:
                # 合并所有文本
                texts = self.df[col].dropna().astype(str)
                if len(texts) == 0:
                    continue
                
                all_text = ' '.join(texts.str.lower())
                
                # 提取关键词（简单的词频统计）
                words = re.findall(r'\b\w+\b', all_text)
                word_freq = Counter(words)
                
                result[col] = {
                    'total_words': len(words),
                    'unique_words': len(word_freq),
                    'top_keywords': dict(word_freq.most_common(20)),
                    'avg_text_length': float(texts.str.len().mean()),
                }
            except Exception as e:
                logger.warning(f"⚠️ 文本分析失败 ({col}): {e}")
        
        return result
    
    def column_correlation_matching(self, string_cols: List[str], numeric_cols: List[str]) -> Dict[str, Any]:
        """
        两列相关匹配分析
        
        Args:
            string_cols: 字符串型列名列表
            numeric_cols: 数值型列名列表
        
        Returns:
            列相关匹配结果
        """
        result = {}
        
        # 字符串列之间的匹配
        for i, col1 in enumerate(string_cols):
            for col2 in string_cols[i+1:]:
                if col1 not in self.df.columns or col2 not in self.df.columns:
                    continue
                
                try:
                    # 计算匹配度（相同值的比例）
                    matches = (self.df[col1] == self.df[col2]).sum()
                    total = len(self.df)
                    match_rate = matches / total if total > 0 else 0
                    
                    result[f"{col1}_vs_{col2}"] = {
                        'match_count': int(matches),
                        'match_rate': float(match_rate),
                        'total_count': int(total)
                    }
                except Exception as e:
                    logger.warning(f"⚠️ 列匹配分析失败 ({col1} vs {col2}): {e}")
        
        # 字符串列与数值列的关联分析
        for str_col in string_cols:
            for num_col in numeric_cols:
                if str_col not in self.df.columns or num_col not in self.df.columns:
                    continue
                
                try:
                    # 按字符串列分组，计算数值列的统计
                    grouped_stats = self.df.groupby(str_col)[num_col].agg(['mean', 'count', 'std']).to_dict('index')
                    result[f"{str_col}_group_{num_col}"] = grouped_stats
                except Exception as e:
                    logger.warning(f"⚠️ 列关联分析失败 ({str_col} vs {num_col}): {e}")
        
        return result
    
    def time_series_analysis(self, datetime_cols: List[str], numeric_cols: List[str]) -> Dict[str, Any]:
        """
        时间序列分析：周期性、季节性等
        
        Args:
            datetime_cols: 日期时间列名列表
            numeric_cols: 数值型列名列表
        
        Returns:
            时间序列分析结果
        """
        result = {}
        
        for dt_col in datetime_cols:
            if dt_col not in self.df.columns:
                continue
            
            try:
                df_copy = self.df.copy()
                df_copy[dt_col] = pd.to_datetime(df_copy[dt_col], errors='coerce')
                df_copy = df_copy.dropna(subset=[dt_col])
                
                if len(df_copy) == 0:
                    continue
                
                df_copy = df_copy.sort_values(by=dt_col)
                
                # 提取时间特征
                df_copy['year'] = df_copy[dt_col].dt.year
                df_copy['month'] = df_copy[dt_col].dt.month
                df_copy['day'] = df_copy[dt_col].dt.day
                df_copy['day_of_week'] = df_copy[dt_col].dt.dayofweek
                
                ts_result = {}
                for num_col in numeric_cols:
                    if num_col not in df_copy.columns or not pd.api.types.is_numeric_dtype(df_copy[num_col]):
                        continue
                    
                    # 按月份统计（季节性）
                    monthly_stats = df_copy.groupby('month')[num_col].agg(['mean', 'count']).to_dict('index')
                    
                    # 按星期统计（周期性）
                    weekly_stats = df_copy.groupby('day_of_week')[num_col].agg(['mean', 'count']).to_dict('index')
                    
                    ts_result[num_col] = {
                        'monthly_pattern': monthly_stats,
                        'weekly_pattern': weekly_stats,
                        'time_range': {
                            'start': str(df_copy[dt_col].min()),
                            'end': str(df_copy[dt_col].max()),
                            'span_days': int((df_copy[dt_col].max() - df_copy[dt_col].min()).days)
                        }
                    }
                
                if ts_result:
                    result[dt_col] = ts_result
            except Exception as e:
                logger.warning(f"⚠️ 时间序列分析失败 ({dt_col}): {e}")
        
        return result
    
    def string_analysis(self, string_cols: List[str]) -> Dict[str, Any]:
        """
        字符串分析：频次统计、模式识别等
        
        Args:
            string_cols: 字符串型列名列表
        
        Returns:
            字符串分析结果
        """
        result = {}
        
        for col in string_cols:
            if col not in self.df.columns:
                continue
            
            try:
                series = self.df[col].dropna().astype(str)
                if len(series) == 0:
                    continue
                
                # 字符串长度统计
                lengths = series.str.len()
                
                # 模式识别（简单模式）
                patterns = {
                    'email_pattern': series.str.contains(r'@', regex=True, na=False).sum(),
                    'numeric_pattern': series.str.contains(r'^\d+$', regex=True, na=False).sum(),
                    'mixed_pattern': series.str.contains(r'[A-Za-z].*\d|\d.*[A-Za-z]', regex=True, na=False).sum(),
                }
                
                result[col] = {
                    'length_stats': {
                        'mean': float(lengths.mean()),
                        'min': int(lengths.min()),
                        'max': int(lengths.max()),
                        'std': float(lengths.std())
                    },
                    'patterns': patterns,
                    'unique_ratio': float(series.nunique() / len(series)) if len(series) > 0 else 0,
                }
            except Exception as e:
                logger.warning(f"⚠️ 字符串分析失败 ({col}): {e}")
        
        return result
    
    def column_joint_analysis(self, all_cols: List[str]) -> Dict[str, Any]:
        """
        两列数据联合分析：相关度、交叉分析等
        
        Args:
            all_cols: 所有列名列表（包括数值型、字符串型、日期时间型）
        
        Returns:
            两列联合分析结果
        """
        result = {
            'pairwise_correlation': {},  # 两列相关度
            'cross_analysis': {},  # 交叉分析
            'joint_frequency': {},  # 联合频率分析
            'conditional_statistics': {}  # 条件统计
        }
        
        # 数值列之间的相关度分析
        numeric_cols = [col for col in all_cols if col in self.df.columns and pd.api.types.is_numeric_dtype(self.df[col])]
        if len(numeric_cols) >= 2:
            result['pairwise_correlation'] = self._pairwise_correlation_analysis(numeric_cols)
        
        # 文本列之间的交叉分析
        string_cols = [col for col in all_cols if col in self.df.columns and not pd.api.types.is_numeric_dtype(self.df[col])]
        if len(string_cols) >= 2:
            result['cross_analysis'] = self._cross_tabulation_analysis(string_cols)
            result['joint_frequency'] = self._joint_frequency_analysis(string_cols)
        
        # 文本列与数值列的联合分析（条件统计）
        if string_cols and numeric_cols:
            result['conditional_statistics'] = self._conditional_statistics_analysis(string_cols, numeric_cols)
        
        return result
    
    def _pairwise_correlation_analysis(self, numeric_cols: List[str]) -> Dict[str, Any]:
        """
        两两相关度分析
        
        Args:
            numeric_cols: 数值型列名列表
        
        Returns:
            两两相关度分析结果
        """
        result = {}
        
        for i, col1 in enumerate(numeric_cols):
            for col2 in numeric_cols[i+1:]:
                if col1 not in self.df.columns or col2 not in self.df.columns:
                    continue
                
                try:
                    # 计算皮尔逊相关系数
                    series1 = self.df[col1].dropna()
                    series2 = self.df[col2].dropna()
                    
                    # 对齐索引
                    common_index = series1.index.intersection(series2.index)
                    if len(common_index) < 2:
                        continue
                    
                    aligned_series1 = series1.loc[common_index]
                    aligned_series2 = series2.loc[common_index]
                    
                    # 计算相关系数
                    pearson_corr = aligned_series1.corr(aligned_series2)
                    
                    # 计算斯皮尔曼秩相关系数（非线性相关）
                    spearman_corr = aligned_series1.corr(aligned_series2, method='spearman')
                    
                    result[f"{col1}_vs_{col2}"] = {
                        'pearson_correlation': float(pearson_corr) if not pd.isna(pearson_corr) else None,
                        'spearman_correlation': float(spearman_corr) if not pd.isna(spearman_corr) else None,
                        'sample_size': int(len(common_index)),
                        'correlation_strength': self._interpret_correlation(abs(pearson_corr) if not pd.isna(pearson_corr) else 0),
                        'correlation_direction': 'positive' if pearson_corr > 0 else 'negative' if pearson_corr < 0 else 'none'
                    }
                except Exception as e:
                    logger.warning(f"⚠️ 两列相关度分析失败 ({col1} vs {col2}): {e}")
        
        return result
    
    def _interpret_correlation(self, abs_corr: float) -> str:
        """解释相关系数强度"""
        if abs_corr >= 0.9:
            return "极强相关"
        elif abs_corr >= 0.7:
            return "强相关"
        elif abs_corr >= 0.5:
            return "中等相关"
        elif abs_corr >= 0.3:
            return "弱相关"
        else:
            return "几乎不相关"
    
    def _cross_tabulation_analysis(self, string_cols: List[str]) -> Dict[str, Any]:
        """
        交叉表分析（列联表）
        
        Args:
            string_cols: 字符串型列名列表
        
        Returns:
            交叉表分析结果
        """
        result = {}
        
        for i, col1 in enumerate(string_cols):
            for col2 in string_cols[i+1:]:
                if col1 not in self.df.columns or col2 not in self.df.columns:
                    continue
                
                try:
                    # 创建交叉表
                    cross_tab = pd.crosstab(self.df[col1], self.df[col2], margins=True)
                    
                    # 计算卡方统计量（检验独立性）
                    try:
                        if HAS_SCIPY:
                            from scipy.stats import chi2_contingency
                            contingency_table = pd.crosstab(self.df[col1], self.df[col2])
                            chi2, p_value, dof, expected = chi2_contingency(contingency_table)
                            
                            result[f"{col1}_vs_{col2}"] = {
                                'cross_table': cross_tab.to_dict(),
                                'chi_square': float(chi2),
                                'p_value': float(p_value),
                                'degrees_of_freedom': int(dof),
                                'is_independent': p_value > 0.05,  # 如果p值>0.05，认为两列独立
                                'cramers_v': self._calculate_cramers_v(contingency_table, chi2)  # Cramer's V 系数
                            }
                        else:
                            # 如果没有scipy，只返回交叉表
                            result[f"{col1}_vs_{col2}"] = {
                                'cross_table': cross_tab.to_dict(),
                                'note': '需要scipy库进行卡方检验'
                            }
                    except Exception as e:
                        logger.warning(f"⚠️ 卡方检验失败: {e}")
                        result[f"{col1}_vs_{col2}"] = {
                            'cross_table': cross_tab.to_dict(),
                            'note': f'卡方检验失败: {str(e)}'
                        }
                except Exception as e:
                    logger.warning(f"⚠️ 交叉表分析失败 ({col1} vs {col2}): {e}")
        
        return result
    
    def _calculate_cramers_v(self, contingency_table: pd.DataFrame, chi2: float) -> float:
        """计算Cramer's V系数（用于衡量分类变量之间的关联强度）"""
        try:
            n = contingency_table.sum().sum()
            min_dim = min(contingency_table.shape) - 1
            if min_dim == 0:
                return 0.0
            cramers_v = np.sqrt(chi2 / (n * min_dim))
            return float(cramers_v)
        except:
            return 0.0
    
    def _joint_frequency_analysis(self, string_cols: List[str]) -> Dict[str, Any]:
        """
        联合频率分析（两列组合的频率）
        
        Args:
            string_cols: 字符串型列名列表
        
        Returns:
            联合频率分析结果
        """
        result = {}
        
        for i, col1 in enumerate(string_cols):
            for col2 in string_cols[i+1:]:
                if col1 not in self.df.columns or col2 not in self.df.columns:
                    continue
                
                try:
                    # 计算两列组合的频率
                    joint_counts = self.df.groupby([col1, col2]).size().reset_index(name='frequency')
                    joint_counts = joint_counts.sort_values('frequency', ascending=False)
                    
                    # 计算条件频率（给定col1，col2的分布）
                    conditional_freq = {}
                    for val1 in self.df[col1].unique():
                        subset = self.df[self.df[col1] == val1]
                        conditional_freq[str(val1)] = subset[col2].value_counts().to_dict()
                    
                    result[f"{col1}_vs_{col2}"] = {
                        'joint_frequency': joint_counts.head(20).to_dict('records'),  # 前20个最常见的组合
                        'total_combinations': int(joint_counts.shape[0]),
                        'conditional_frequency': conditional_freq,
                        'most_common_combination': joint_counts.iloc[0].to_dict() if len(joint_counts) > 0 else None
                    }
                except Exception as e:
                    logger.warning(f"⚠️ 联合频率分析失败 ({col1} vs {col2}): {e}")
        
        return result
    
    def _conditional_statistics_analysis(self, string_cols: List[str], numeric_cols: List[str]) -> Dict[str, Any]:
        """
        条件统计分析（给定文本列的值，数值列的统计特征）
        
        Args:
            string_cols: 字符串型列名列表
            numeric_cols: 数值型列名列表
        
        Returns:
            条件统计分析结果
        """
        result = {}
        
        for str_col in string_cols:
            if str_col not in self.df.columns:
                continue
            
            for num_col in numeric_cols:
                if num_col not in self.df.columns or not pd.api.types.is_numeric_dtype(self.df[num_col]):
                    continue
                
                try:
                    # 按文本列分组，计算数值列的统计
                    grouped = self.df.groupby(str_col)[num_col]
                    
                    conditional_stats = {}
                    for group_name, group_data in grouped:
                        group_data_clean = group_data.dropna()
                        if len(group_data_clean) > 0:
                            conditional_stats[str(group_name)] = {
                                'count': int(len(group_data_clean)),
                                'mean': float(group_data_clean.mean()),
                                'median': float(group_data_clean.median()),
                                'std': float(group_data_clean.std()),
                                'min': float(group_data_clean.min()),
                                'max': float(group_data_clean.max()),
                                'sum': float(group_data_clean.sum())
                            }
                    
                    # 计算不同组之间的差异
                    group_means = grouped.mean()
                    if len(group_means) > 1:
                        mean_diff = float(group_means.max() - group_means.min())
                        mean_ratio = float(group_means.max() / group_means.min()) if group_means.min() != 0 else None
                    else:
                        mean_diff = None
                        mean_ratio = None
                    
                    result[f"{str_col}_condition_{num_col}"] = {
                        'conditional_statistics': conditional_stats,
                        'group_comparison': {
                            'mean_difference': mean_diff,
                            'mean_ratio': mean_ratio,
                            'groups_count': int(len(group_means))
                        }
                    }
                except Exception as e:
                    logger.warning(f"⚠️ 条件统计分析失败 ({str_col} condition {num_col}): {e}")
        
        return result


def calculate_statistics(csv_file_path: str, columns_types: List[str] = None) -> Dict[str, Any]:
    """
    计算CSV文件的统计指标
    
    Args:
        csv_file_path: CSV文件路径
        columns_types: 列类型列表（可选）
    
    Returns:
        包含所有统计结果的字典
    """
    try:
        calculator = StatisticsCalculator(csv_file_path)
        return calculator.calculate_all_statistics(columns_types)
    except Exception as e:
        logger.error(f"❌ 统计计算失败: {e}")
        return {}
