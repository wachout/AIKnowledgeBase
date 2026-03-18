"""
网络搜索工具

用于在互联网上搜索最新信息和资源。

智能体使用说明（按需选择，不必全部搜索）：
- 只需概念/定义/术语解释 → 用 wikipedia_search（百科，快速且权威）。
- 只需学术论文/文献/研究 → 用 academic_paper_search 或 arxiv_search / semantic_scholar_search（不必用通用网页搜索）。
- 需最新动态、新闻、教程、任意网页、或百科与论文都没有的内容 → 用 web_search（通用网页搜索）。
- 可组合：例如先 wikipedia_search 查定义，再 web_search 查最新案例；或先 academic_paper_search 查文献，再按需 web_search 补全。

工具列表：
- WebSearchTool (web_search): 通用网页搜索，适合最新动态、新闻、教程、任意网站。
- WikipediaSearchTool (wikipedia_search): 百科搜索，适合概念、定义、术语、人物事件。
- SemanticScholarSearchTool (semantic_scholar_search): 学术论文（Semantic Scholar）。
- ArxivSearchTool (arxiv_search): 学术论文（arXiv），预印本与 PDF。
- AcademicPaperSearchTool (academic_paper_search): 多源学术（arXiv + Semantic Scholar），可下载 PDF。
"""

from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime
import logging
import os
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlencode, quote_plus, quote
from .base_tool import (
    BaseTool, ToolResult, QualityAssessment,
    ParameterSchema, ParameterDefinition, ParameterType
)

if TYPE_CHECKING:
    from .tool_evaluator import SearchResultEvaluator

logger = logging.getLogger(__name__)

# Semantic Scholar API 基址（公开接口，无需 API Key 也可使用，有速率限制）
SEMANTIC_SCHOLAR_API_BASE = "https://api.semanticscholar.org/graph/v1"
# arXiv API（Atom 1.0 XML）
ARXIV_API_BASE = "http://export.arxiv.org/api/query"
# 常见 arXiv 分类（用于分类搜索）
ARXIV_CATEGORIES = [
    "cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.NE", "cs.RO", "stat.ML",
    "physics", "math", "q-bio", "q-fin", "eess",
]


class WebSearchTool(BaseTool):
    """
    通用网页搜索工具。

    用于在互联网上搜索最新信息，支持结果质量评估和来源可信度分析。
    适用：需要最新动态、新闻、教程、博客、官方文档、任意网页时使用；
    若仅需概念定义或学术论文，请优先用 wikipedia_search 或 academic_paper_search，不必用本工具。
    """

    # 已知可信来源及其可信度评分
    TRUSTED_SOURCES = {
        "wikipedia.org": 0.85,
        "github.com": 0.80,
        "stackoverflow.com": 0.80,
        "docs.python.org": 0.90,
        "developer.mozilla.org": 0.90,
        "arxiv.org": 0.85,
        "ieee.org": 0.90,
        "nature.com": 0.90,
        "science.org": 0.90,
    }

    def __init__(
        self,
        search_engine_interface=None,
        evaluator: 'SearchResultEvaluator' = None,
        version: str = "1.0.0"
    ):
        # 定义参数模式
        schema = ParameterSchema(version="1.0.0")
        schema.add_parameter(ParameterDefinition(
            name="query",
            param_type=ParameterType.STRING,
            description="搜索查询字符串",
            required=True
        ))
        schema.add_parameter(ParameterDefinition(
            name="limit",
            param_type=ParameterType.INTEGER,
            description="返回结果数量限制",
            required=False,
            default=5,
            constraints={"min": 1, "max": 50}
        ))
        schema.add_parameter(ParameterDefinition(
            name="time_range",
            param_type=ParameterType.STRING,
            description="时间范围: day, week, month, year, all",
            required=False,
            default="month",
            constraints={"enum": ["day", "week", "month", "year", "all"]}
        ))
        schema.add_parameter(ParameterDefinition(
            name="language",
            param_type=ParameterType.STRING,
            description="搜索语言",
            required=False,
            default="zh"
        ))
        schema.add_parameter(ParameterDefinition(
            name="safe_search",
            param_type=ParameterType.BOOLEAN,
            description="是否启用安全搜索",
            required=False,
            default=True
        ))

        super().__init__(
            name="web_search",
            description="通用网页搜索：适合查最新动态、新闻、教程、任意网站。仅需概念定义时用 wikipedia_search，仅需论文时用 academic_paper_search，不必用本工具。",
            tool_type="search",
            version=version,
            parameter_schema=schema
        )

        self.search_engine = search_engine_interface
        self._evaluator = evaluator

    def set_evaluator(self, evaluator: 'SearchResultEvaluator'):
        """设置结果评估器"""
        self._evaluator = evaluator

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行网络搜索

        Args:
            parameters: 搜索参数
                - query: 搜索查询
                - limit: 返回结果数量限制 (默认5)
                - time_range: 时间范围 (day, week, month, year, all)
                - language: 搜索语言
                - safe_search: 是否启用安全搜索

        Returns:
            搜索结果
        """
        self._record_usage()

        if not self.validate_parameters(parameters, ["query"]):
            return self.create_error_result("Missing required parameter: query")

        query = parameters["query"]
        limit = parameters.get("limit", 5)
        time_range = parameters.get("time_range", "month")
        language = parameters.get("language", "zh")
        safe_search = parameters.get("safe_search", True)

        try:
            # 如果有实际的搜索引擎接口，调用它
            if self.search_engine is not None:
                search_results = self._execute_real_search(
                    query, limit, time_range, language, safe_search
                )
            else:
                # 返回模拟结果
                search_results = self._execute_mock_search(query, limit, time_range)

            # 评估结果质量和可信度
            quality_assessment = self._assess_quality(query, search_results)

            return self.create_success_result(
                search_results,
                metadata={
                    "query": query,
                    "time_range": time_range,
                    "language": language,
                    "safe_search": safe_search
                },
                quality_assessment=quality_assessment
            )

        except Exception as e:
            logger.warning(f"网络搜索失败，返回空结果以保证智能体继续运行: {e}")
            # 搜索失败时不抛错，返回空结果以便第一层、第二层智能体继续运行
            return self.create_success_result(
                {"query": query, "total_results": 0, "results": []},
                metadata={"query": query, "error": str(e), "degraded": True},
                quality_assessment=QualityAssessment(
                    relevance_score=0.0,
                    confidence_score=0.0,
                    completeness_score=0.0,
                    quality_level="LOW",
                    assessment_details={"reason": "web_search_failed", "error": str(e)},
                ),
            )

    def _execute_real_search(
        self,
        query: str,
        limit: int,
        time_range: str,
        language: str,
        safe_search: bool
    ) -> Dict[str, Any]:
        """执行实际搜索"""
        if hasattr(self.search_engine, 'search'):
            results = self.search_engine.search(
                query=query,
                limit=limit,
                time_range=time_range,
                language=language,
                safe_search=safe_search
            )
            return results

        return self._execute_mock_search(query, limit, time_range)

    def _execute_mock_search(
        self,
        query: str,
        limit: int,
        time_range: str
    ) -> Dict[str, Any]:
        """执行模拟搜索"""
        mock_domains = [
            "example.com", "docs.example.org", "blog.example.net",
            "news.example.io", "research.example.edu"
        ]

        return {
            "query": query,
            "time_range": time_range,
            "total_results": 10,
            "results": [
                {
                    "id": f"web_{i+1}",
                    "title": f"网络搜索结果 {i+1}",
                    "url": f"https://{mock_domains[i % len(mock_domains)]}/result{i+1}",
                    "snippet": f"这是关于 '{query}' 的网络搜索摘要 {i+1}",
                    "source": mock_domains[i % len(mock_domains)],
                    "published_date": f"2024-01-{(i+1):02d}",
                    "relevance_score": 0.85 - i * 0.08
                }
                for i in range(min(limit, 10))
            ]
        }

    def _assess_quality(
        self,
        query: str,
        search_results: Dict[str, Any]
    ) -> QualityAssessment:
        """评估搜索结果质量"""
        results = search_results.get("results", [])

        if not results:
            return QualityAssessment(
                relevance_score=0.0,
                confidence_score=0.0,
                completeness_score=0.0,
                quality_level="LOW",
                assessment_details={"reason": "No results found"}
            )

        # 如果有评估器，使用评估器
        if self._evaluator:
            try:
                return self._evaluator.evaluate(query, results)
            except Exception:
                pass

        # 计算平均相关性
        relevance_scores = [
            r.get("relevance_score", 0.5) for r in results
        ]
        avg_relevance = sum(relevance_scores) / len(relevance_scores)

        # 计算来源可信度
        source_scores = []
        for result in results:
            url = result.get("url", "")
            source = result.get("source", "")
            trust_score = self._get_source_trust_score(url, source)
            source_scores.append(trust_score)

        avg_trust = sum(source_scores) / len(source_scores) if source_scores else 0.5

        # 计算时效性 (基于发布日期)
        freshness_scores = []
        now = datetime.now()
        for result in results:
            pub_date = result.get("published_date", "")
            freshness = self._calculate_freshness(pub_date, now)
            freshness_scores.append(freshness)

        avg_freshness = sum(freshness_scores) / len(freshness_scores) if freshness_scores else 0.5

        # 综合置信度 = 来源可信度 * 0.6 + 时效性 * 0.4
        confidence = avg_trust * 0.6 + avg_freshness * 0.4

        # 完整性 = 结果数量 / 期望数量
        completeness = min(len(results) / 5.0, 1.0)

        assessment = QualityAssessment(
            relevance_score=avg_relevance,
            confidence_score=confidence,
            completeness_score=completeness,
            assessment_details={
                "results_count": len(results),
                "avg_relevance": avg_relevance,
                "avg_source_trust": avg_trust,
                "avg_freshness": avg_freshness,
                "trusted_sources_count": sum(1 for s in source_scores if s >= 0.8)
            }
        )
        assessment.determine_quality_level()

        return assessment

    def _get_source_trust_score(self, url: str, source: str) -> float:
        """获取来源可信度评分"""
        # 从URL中提取域名
        domain = ""
        if url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
                # 移除 www. 前缀
                if domain.startswith("www."):
                    domain = domain[4:]
            except Exception:
                domain = source.lower() if source else ""

        # 检查是否为已知可信来源
        for trusted_domain, score in self.TRUSTED_SOURCES.items():
            if trusted_domain in domain:
                return score

        # 默认可信度
        return 0.5

    def _calculate_freshness(self, pub_date: str, now: datetime) -> float:
        """计算内容时效性评分"""
        if not pub_date:
            return 0.5

        try:
            # 尝试解析日期
            if isinstance(pub_date, str):
                # 支持多种日期格式
                for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        pub_datetime = datetime.strptime(pub_date[:len(fmt)], fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return 0.5

            days_old = (now - pub_datetime).days

            # 时效性评分: 越新越高
            if days_old <= 7:
                return 1.0
            elif days_old <= 30:
                return 0.9
            elif days_old <= 90:
                return 0.7
            elif days_old <= 365:
                return 0.5
            else:
                return 0.3

        except Exception:
            return 0.5

    def add_trusted_source(self, domain: str, trust_score: float):
        """添加可信来源"""
        self.TRUSTED_SOURCES[domain.lower()] = min(max(trust_score, 0.0), 1.0)


# ---------------------------------------------------------------------------
# Semantic Scholar 学术论文搜索（与通用网络搜索区分，单独能力）
# 参考: https://api.semanticscholar.org/
# ---------------------------------------------------------------------------

class SemanticScholarSearchTool(BaseTool):
    """
    基于 Semantic Scholar API 的学术论文搜索工具。

    适用：需要学术论文、文献、研究引用时使用；若只需概念定义请用 wikipedia_search，只需通用网页请用 web_search。
    功能：按题目/关键词搜索、按时间查最新论文；返回标题、作者、年份、引用数、发表场所、研究领域、摘要、论文ID。
    阅读与下载：可选 paper_id + save_path + download_pdf 下载 PDF。
    """

    def __init__(self, api_key: Optional[str] = None, version: str = "1.0.0"):
        schema = ParameterSchema(version="1.0.0")
        schema.add_parameter(ParameterDefinition(
            name="query",
            param_type=ParameterType.STRING,
            description="搜索查询：论文题目、关键词或主题",
            required=True
        ))
        schema.add_parameter(ParameterDefinition(
            name="limit",
            param_type=ParameterType.INTEGER,
            description="返回结果数量",
            required=False,
            default=10,
            constraints={"min": 1, "max": 100}
        ))
        schema.add_parameter(ParameterDefinition(
            name="sort_by_year",
            param_type=ParameterType.BOOLEAN,
            description="是否按发表年份降序排列（最新优先）",
            required=False,
            default=True
        ))
        schema.add_parameter(ParameterDefinition(
            name="year_min",
            param_type=ParameterType.INTEGER,
            description="仅返回该年及之后的论文（可选）",
            required=False
        ))
        schema.add_parameter(ParameterDefinition(
            name="paper_id",
            param_type=ParameterType.STRING,
            description="若填写则直接获取该论文ID的详细信息（与 query 二选一）",
            required=False
        ))
        schema.add_parameter(ParameterDefinition(
            name="save_path",
            param_type=ParameterType.STRING,
            description="保存路径：下载 PDF 时使用。可为目录（则保存为 目录/标题.pdf）或单个文件的完整路径",
            required=False
        ))
        schema.add_parameter(ParameterDefinition(
            name="download_pdf",
            param_type=ParameterType.BOOLEAN,
            description="是否下载论文 PDF（需同时提供 paper_id 与 save_path；仅当论文有开放获取 PDF 时有效）",
            required=False,
            default=False
        ))

        super().__init__(
            name="semantic_scholar_search",
            description="学术论文搜索（Semantic Scholar）：适用需文献/研究时。仅需概念定义用 wikipedia_search，仅需网页用 web_search。返回标题、作者、年份、引用数、摘要等。",
            tool_type="search",
            version=version,
            parameter_schema=schema
        )
        self._api_key = api_key

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行论文搜索或单篇论文详情获取。

        - 若提供 paper_id：获取该论文的基本信息、摘要、作者、引用数等
        - 若提供 query：搜索相关论文，可选按年份排序与年份过滤
        """
        self._record_usage()

        paper_id = parameters.get("paper_id") or ""
        query = parameters.get("query", "").strip()

        # 单篇论文详情（可选下载 PDF 到 save_path）
        if paper_id:
            save_path = (parameters.get("save_path") or "").strip()
            download_pdf = parameters.get("download_pdf", False)
            need_pdf_url = download_pdf and save_path
            data = self._get_paper_by_id(paper_id, with_pdf_url=need_pdf_url)
            if data is None:
                return self.create_error_result(f"未找到论文或请求失败: paper_id={paper_id}")
            metadata = {"paper_id": paper_id}
            if download_pdf and save_path:
                saved_path = self._download_paper_pdf(paper_id, save_path, data)
                if saved_path:
                    metadata["pdf_download_path"] = saved_path
                    if isinstance(data, dict):
                        data["pdf_local_path"] = saved_path
                else:
                    metadata["pdf_download"] = "未找到开放获取 PDF 或下载失败"
            return self.create_success_result(
                data,
                metadata=metadata,
                quality_assessment=QualityAssessment(
                    relevance_score=0.9,
                    confidence_score=0.9,
                    completeness_score=1.0,
                    quality_level="HIGH",
                    assessment_details={"source": "Semantic Scholar API"}
                )
            )

        # 搜索
        if not query:
            return self.create_error_result("缺少参数: 请提供 query（搜索词）或 paper_id（论文ID）")
        limit = max(1, min(parameters.get("limit", 10), 100))
        sort_by_year = parameters.get("sort_by_year", True)
        year_min = parameters.get("year_min")

        try:
            papers = self._search_papers(query, limit, sort_by_year, year_min)
            # 固定：每次搜索都额外按最新时间取最新 10 篇论文（不受用户 limit/query 影响）
            latest_10_papers = self._search_latest_papers(limit=10)
            payload = {
                "papers": papers,
                "latest_10_papers": latest_10_papers,
            }
            if not papers and not latest_10_papers:
                return self.create_success_result(
                    payload,
                    metadata={"query": query, "total": 0, "latest_10_count": 0},
                    quality_assessment=QualityAssessment(
                        relevance_score=0.0,
                        confidence_score=0.5,
                        completeness_score=0.0,
                        quality_level="LOW",
                        assessment_details={"reason": "No papers found"}
                    )
                )
            qa = QualityAssessment(
                relevance_score=0.8,
                confidence_score=0.85,
                completeness_score=min((len(papers) + len(latest_10_papers)) / 20.0, 1.0),
                assessment_details={
                    "source": "Semantic Scholar API",
                    "results_count": len(papers),
                    "latest_10_count": len(latest_10_papers),
                }
            )
            qa.determine_quality_level()
            return self.create_success_result(
                payload,
                metadata={"query": query, "total": len(papers), "latest_10_count": len(latest_10_papers)},
                quality_assessment=qa,
            )
        except Exception as e:
            logger.exception("Semantic Scholar 搜索失败")
            return self.create_error_result(f"Semantic Scholar 搜索失败: {str(e)}")

    def _request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """发送 GET 请求到 Semantic Scholar API"""
        try:
            import requests
            url = f"{SEMANTIC_SCHOLAR_API_BASE.rstrip('/')}/{path.lstrip('/')}"
            headers = {}
            if self._api_key:
                headers["x-api-key"] = self._api_key
            r = requests.get(url, params=params or {}, headers=headers, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Semantic Scholar API 请求失败: {e}")
            return None

    def _normalize_paper(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """将 API 返回的单条论文转为统一结构"""
        authors_raw = item.get("authors") or []
        authors = [
            a.get("name", "") if isinstance(a, dict) else str(a)
            for a in authors_raw
        ]
        venue = item.get("venue") or ""
        if isinstance(venue, dict):
            venue = venue.get("name") or (venue.get("alternate_names") or [""])[0]
        return {
            "paper_id": item.get("paperId", ""),
            "title": item.get("title", ""),
            "authors": authors,
            "year": item.get("year"),
            "citation_count": item.get("citationCount"),
            "venue": venue,
            "fields_of_study": item.get("fieldsOfStudy") or [],
            "abstract": item.get("abstract") or "",
            "url": item.get("url", ""),
        }

    def _search_papers(
        self,
        query: str,
        limit: int,
        sort_by_year: bool,
        year_min: Optional[int],
    ) -> List[Dict[str, Any]]:
        """根据关键词搜索论文，可选按年份排序与过滤"""
        params = {
            "query": query,
            "limit": min(limit * 2, 100),  # 多取一些以便按年过滤后仍有足够数量
            "offset": 0,
            "fields": "paperId,title,authors,year,citationCount,venue,fieldsOfStudy,abstract,url",
        }
        data = self._request("paper/search", params)
        if not data or "data" not in data:
            return []
        raw = data.get("data", [])
        out = []
        for p in raw:
            norm = self._normalize_paper(p)
            if year_min is not None and norm.get("year") is not None and norm["year"] < year_min:
                continue
            out.append(norm)
            if len(out) >= limit:
                break
        if sort_by_year:
            out.sort(key=lambda x: (x.get("year") or 0), reverse=True)
        return out[:limit]

    def _search_latest_papers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """固定按最新时间搜索最新 N 篇论文（每次搜索都会调用，不受用户条件影响）。"""
        params = {
            "query": "research",  # 宽泛查询以获取近期论文
            "limit": limit,
            "offset": 0,
            "fields": "paperId,title,authors,year,citationCount,venue,fieldsOfStudy,abstract,url",
        }
        data = self._request("paper/search", params)
        if not data or "data" not in data:
            return []
        raw = data.get("data", [])
        out = [self._normalize_paper(p) for p in raw]
        out.sort(key=lambda x: (x.get("year") or 0), reverse=True)
        return out[:limit]

    def _get_paper_by_id(self, paper_id: str, with_pdf_url: bool = False) -> Optional[Dict[str, Any]]:
        """获取单篇论文的详细信息；with_pdf_url=True 时同时请求 openAccessPdf 用于下载"""
        fields = "paperId,title,authors,year,citationCount,venue,fieldsOfStudy,abstract,url"
        if with_pdf_url:
            fields += ",openAccessPdf"
        params = {"fields": fields}
        data = self._request(f"paper/{paper_id}", params)
        if not data:
            return None
        out = self._normalize_paper(data)
        if with_pdf_url:
            oa = data.get("openAccessPdf")
            out["open_access_pdf_url"] = oa.get("url") if isinstance(oa, dict) and oa.get("url") else None
        return out

    def _download_paper_pdf(
        self, paper_id: str, save_path: str, paper_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        将论文 PDF 保存到指定路径。
        save_path：可为目录（则保存为 目录/标题.pdf）或单个文件的完整路径。
        返回保存后的本地路径，失败返回 None。
        """
        url = paper_data.get("open_access_pdf_url") if isinstance(paper_data, dict) else None
        if not url or not url.strip():
            logger.debug("论文无开放获取 PDF 或未请求 openAccessPdf")
            return None
        save_path = (save_path or "").strip()
        if not save_path:
            return None
        title = (paper_data.get("title") or paper_id) if isinstance(paper_data, dict) else paper_id
        safe_name = re.sub(r'[^\w\u4e00-\u9fa5\-\.]', "_", title)[:80]
        if not safe_name:
            safe_name = paper_id
        # 若 save_path 以 .pdf 结尾视为完整文件路径；否则视为目录，保存为 目录/标题.pdf
        if save_path.endswith(".pdf"):
            path = save_path
            if os.path.isfile(path):
                logger.debug(f"论文已存在，跳过下载: {path}")
                return path
            try:
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            except OSError as e:
                logger.warning(f"创建目录失败: {e}")
                return None
        else:
            try:
                os.makedirs(save_path, exist_ok=True)
            except OSError as e:
                logger.warning(f"创建目录失败 {save_path}: {e}")
                return None
            path = os.path.join(save_path, f"{safe_name}.pdf")
        # 若阅读路径中已存在该论文，不再重复下载
        if os.path.isfile(path):
            logger.debug(f"论文已存在，跳过下载: {path}")
            return path
        try:
            import requests
            r = requests.get(url, timeout=60, stream=True)
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            logger.info(f"论文 PDF 已保存: {path}")
            return path
        except Exception as e:
            logger.warning(f"下载论文 PDF 失败: {e}")
            return None


# ---------------------------------------------------------------------------
# Wikipedia 百科搜索（独立工具）
# API: https://www.mediawiki.org/wiki/API:Search （无需 API Key）
# 做 web 工具搜索时可单独调用或与 web_search 配合使用。
# ---------------------------------------------------------------------------

# 各语言 Wikipedia API 前缀（path 为 /w/api.php）
WIKIPEDIA_API_BASES = {
    "zh": "https://zh.wikipedia.org",
    "en": "https://en.wikipedia.org",
}


class WikipediaSearchTool(BaseTool):
    """
    基于 Wikipedia API 的百科搜索工具（独立工具）。

    适用：需要概念解释、定义、术语、人物/事件背景时优先用本工具，不必用通用网页搜索。
    支持：关键词搜索、中/英文；返回标题、摘要、链接。无需 API Key。
    若需学术论文请用 academic_paper_search；若需最新动态或百科没有的内容再用 web_search。
    """

    def __init__(self, version: str = "1.0.0"):
        schema = ParameterSchema(version="1.0.0")
        schema.add_parameter(ParameterDefinition(
            name="query",
            param_type=ParameterType.STRING,
            description="搜索关键词（概念、术语、人物、事件等）",
            required=True,
        ))
        schema.add_parameter(ParameterDefinition(
            name="limit",
            param_type=ParameterType.INTEGER,
            description="返回结果数量",
            required=False,
            default=5,
            constraints={"min": 1, "max": 20},
        ))
        schema.add_parameter(ParameterDefinition(
            name="language",
            param_type=ParameterType.STRING,
            description="语言：zh 中文维基，en 英文维基",
            required=False,
            default="zh",
            constraints={"enum": ["zh", "en"]},
        ))
        super().__init__(
            name="wikipedia_search",
            description="百科搜索（Wikipedia）：适用查概念、定义、术语、人物事件时优先用本工具，不必全网搜。需论文用 academic_paper_search，需网页用 web_search。",
            tool_type="search",
            version=version,
            parameter_schema=schema,
        )

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        self._record_usage()
        query = (parameters.get("query") or "").strip()
        if not query:
            return self.create_error_result("缺少参数: query")
        limit = max(1, min(parameters.get("limit", 5), 20))
        language = parameters.get("language", "zh") or "zh"
        if language not in WIKIPEDIA_API_BASES:
            language = "zh"

        try:
            results = self._search_wikipedia(query, limit, language)
            if not results:
                return self.create_success_result(
                    {"query": query, "total_results": 0, "results": []},
                    metadata={"query": query, "language": language},
                    quality_assessment=QualityAssessment(
                        relevance_score=0.0,
                        confidence_score=0.5,
                        completeness_score=0.0,
                        quality_level="LOW",
                        assessment_details={"reason": "No Wikipedia results"},
                    ),
                )
            qa = QualityAssessment(
                relevance_score=0.85,
                confidence_score=0.9,
                completeness_score=min(len(results) / 5.0, 1.0),
                assessment_details={
                    "source": "Wikipedia API",
                    "language": language,
                    "results_count": len(results),
                },
            )
            qa.determine_quality_level()
            return self.create_success_result(
                {"query": query, "total_results": len(results), "results": results},
                metadata={"query": query, "language": language},
                quality_assessment=qa,
            )
        except Exception as e:
            logger.warning(f"Wikipedia 搜索失败: {e}")
            return self.create_success_result(
                {"query": query, "total_results": 0, "results": []},
                metadata={"query": query, "language": language, "error": str(e), "degraded": True},
                quality_assessment=QualityAssessment(
                    relevance_score=0.0,
                    confidence_score=0.0,
                    completeness_score=0.0,
                    quality_level="LOW",
                    assessment_details={"reason": "wikipedia_search_failed", "error": str(e)},
                ),
            )

    def _request_wikipedia(self, base: str, params: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """GET 请求 Wikipedia API（query list=search 或 query prop=extracts）。"""
        try:
            import requests
            url = f"{base.rstrip('/')}/w/api.php"
            r = requests.get(url, params={**params, "format": "json"}, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.debug(f"Wikipedia API 请求失败: {e}")
            return None

    def _search_wikipedia(self, query: str, limit: int, language: str) -> List[Dict[str, Any]]:
        """执行搜索，返回与 WebSearchTool 兼容的 results 结构（title, snippet, url, source, relevance_score）。"""
        base = WIKIPEDIA_API_BASES.get(language, WIKIPEDIA_API_BASES["zh"])
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": min(limit, 20),
            "srprop": "",
            "utf8": "1",
        }
        data = self._request_wikipedia(base, params)
        if not data or "query" not in data or "search" not in data.get("query", {}):
            return []

        search_list = data["query"]["search"]
        domain = "zh.wikipedia.org" if language == "zh" else "en.wikipedia.org"
        results = []
        for i, item in enumerate(search_list):
            title = item.get("title", "")
            page_id = item.get("pageid", "")
            snippet = (item.get("snippet") or "").strip()
            # 去除 HTML 标签
            if snippet:
                snippet = re.sub(r"<[^>]+>", "", snippet)
                snippet = snippet.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            # Wikipedia URL: 空格用下划线，其余字符 percent-encode
            url = f"{base}/wiki/{quote(title.replace(' ', '_'), safe='/')}" if title else ""
            results.append({
                "id": f"wiki_{language}_{page_id or i}",
                "title": title,
                "url": url,
                "snippet": snippet or title,
                "source": domain,
                "page_id": page_id,
                "relevance_score": 0.9 - i * 0.05,
            })
        return results[:limit]


# ---------------------------------------------------------------------------
# arXiv 论文搜索（独立工具）
# API: http://export.arxiv.org/api/query (Atom 1.0 XML)
# ---------------------------------------------------------------------------

# Atom / arXiv 命名空间
ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"


def _arxiv_extract_id(entry_id: str) -> str:
    """从 Atom entry 的 id (e.g. http://arxiv.org/abs/2301.12345v1) 提取 arXiv ID（含版本号则去掉）。"""
    if not entry_id:
        return ""
    s = entry_id.strip().rstrip("/")
    if "/abs/" in s:
        s = s.split("/abs/")[-1]
    if "v" in s and s[-1].isdigit():
        # 保留版本号如 2301.12345v2，或去掉得 2301.12345（API 常返回带 v1 的）
        pass
    return s


class ArxivSearchTool(BaseTool):
    """
    基于 arXiv API 的论文搜索工具。

    适用：需要预印本/学术论文（尤其 CS、物理、数学等）时使用；仅需概念定义用 wikipedia_search，仅需网页用 web_search。
    支持：关键词、分类(cs.LG 等)、最新论文、ID 查询；PDF 可通过链接下载。
    """

    def __init__(self, version: str = "1.0.0"):
        schema = ParameterSchema(version="1.0.0")
        schema.add_parameter(ParameterDefinition(
            name="query",
            param_type=ParameterType.STRING,
            description="搜索关键词（用于标题、摘要、作者等）；与 arxiv_id 二选一",
            required=False
        ))
        schema.add_parameter(ParameterDefinition(
            name="category",
            param_type=ParameterType.STRING,
            description="arXiv 分类，如 cs.LG, cs.CV, cs.AI, stat.ML（与 query 可同时使用）",
            required=False
        ))
        schema.add_parameter(ParameterDefinition(
            name="limit",
            param_type=ParameterType.INTEGER,
            description="返回结果数量",
            required=False,
            default=10,
            constraints={"min": 1, "max": 100}
        ))
        schema.add_parameter(ParameterDefinition(
            name="sort_by_submitted",
            param_type=ParameterType.BOOLEAN,
            description="是否按提交时间降序（最新优先）",
            required=False,
            default=True
        ))
        schema.add_parameter(ParameterDefinition(
            name="arxiv_id",
            param_type=ParameterType.STRING,
            description="arXiv 论文 ID，填写则直接获取该篇详情（与 query 二选一）",
            required=False
        ))
        super().__init__(
            name="arxiv_search",
            description="学术论文搜索（arXiv）：适用需预印本/论文时。仅需概念用 wikipedia_search，仅需网页用 web_search。支持关键词、分类、最新论文、ID、PDF 链接。",
            tool_type="search",
            version=version,
            parameter_schema=schema
        )

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        self._record_usage()
        arxiv_id = (parameters.get("arxiv_id") or "").strip()
        query = (parameters.get("query") or "").strip()
        category = (parameters.get("category") or "").strip()
        limit = max(1, min(parameters.get("limit", 10), 100))
        sort_by_submitted = parameters.get("sort_by_submitted", True)

        # 单篇 ID 查询
        if arxiv_id:
            papers = self._fetch_by_id(arxiv_id)
            if not papers:
                return self.create_error_result(f"未找到 arXiv 论文: {arxiv_id}")
            return self.create_success_result(
                {"papers": papers, "latest_10_papers": papers},
                metadata={"arxiv_id": arxiv_id},
                quality_assessment=QualityAssessment(
                    relevance_score=0.95,
                    confidence_score=0.95,
                    completeness_score=1.0,
                    quality_level="HIGH",
                    assessment_details={"source": "arXiv API"}
                )
            )

        if not query and not category:
            return self.create_error_result("请提供 query（关键词）或 category（分类）或 arxiv_id")

        try:
            papers = self._search_arxiv(query, category, limit, sort_by_submitted)
            latest = self._search_latest_arxiv(10)
            payload = {"papers": papers, "latest_10_papers": latest}
            qa = QualityAssessment(
                relevance_score=0.8,
                confidence_score=0.85,
                completeness_score=min((len(papers) + len(latest)) / 20.0, 1.0),
                assessment_details={"source": "arXiv API", "results_count": len(papers), "latest_10_count": len(latest)},
            )
            qa.determine_quality_level()
            return self.create_success_result(
                payload,
                metadata={"query": query, "category": category, "total": len(papers), "latest_10_count": len(latest)},
                quality_assessment=qa,
            )
        except Exception as e:
            logger.exception("arXiv 搜索失败")
            return self.create_error_result(f"arXiv 搜索失败: {str(e)}")

    def _request_arxiv(self, params: Dict[str, str]) -> Optional[bytes]:
        """GET arXiv API，返回 XML 字节或 None。"""
        try:
            import requests
            url = ARXIV_API_BASE
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.content
        except Exception as e:
            logger.warning(f"arXiv API 请求失败: {e}")
            return None

    def _parse_atom_entries(self, xml_bytes: Optional[bytes]) -> List[Dict[str, Any]]:
        """解析 Atom feed，返回标准化论文列表（含 pdf_url）。"""
        if not xml_bytes:
            return []
        try:
            root = ET.fromstring(xml_bytes)
            # 带命名空间查找
            ns = {"atom": ATOM_NS, "arxiv": ARXIV_NS}
            entries = root.findall(".//atom:entry", ns)
            if not entries:
                entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            out = []
            for entry in entries:
                # id -> arxiv id
                eid = entry.find("atom:id", ns) or entry.find("{http://www.w3.org/2005/Atom}id")
                id_text = (eid.text or "").strip() if eid is not None else ""
                arxiv_id = _arxiv_extract_id(id_text)
                title_el = entry.find("atom:title", ns) or entry.find("{http://www.w3.org/2005/Atom}title")
                title = (title_el.text or "").strip() if title_el is not None else ""
                summary_el = entry.find("atom:summary", ns) or entry.find("{http://www.w3.org/2005/Atom}summary")
                abstract = (summary_el.text or "").strip() if summary_el is not None else ""
                published_el = entry.find("atom:published", ns) or entry.find("{http://www.w3.org/2005/Atom}published")
                pub_date = (published_el.text or "").strip() if published_el is not None else ""
                year = None
                if pub_date:
                    try:
                        # ISO 格式如 2007-02-27T16:02:02-05:00 或 2007-02-27
                        dt_str = pub_date.replace("Z", "+00:00")[:19]
                        if "T" in dt_str:
                            dt = datetime.fromisoformat(dt_str)
                        else:
                            dt = datetime.strptime(pub_date[:10], "%Y-%m-%d")
                        year = dt.year
                    except Exception:
                        if len(pub_date) >= 4 and pub_date[:4].isdigit():
                            year = int(pub_date[:4])
                authors = []
                for a in entry.findall("atom:author", ns) or entry.findall("{http://www.w3.org/2005/Atom}author"):
                    n = a.find("atom:name", ns) or a.find("{http://www.w3.org/2005/Atom}name")
                    if n is not None and n.text:
                        authors.append(n.text.strip())
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                for link in entry.findall("atom:link", ns) or entry.findall("{http://www.w3.org/2005/Atom}link"):
                    href = link.get("href") or ""
                    if "pdf" in (link.get("title") or "").lower() or "pdf" in href:
                        pdf_url = href
                        break
                primary_cat = ""
                pc = entry.find("arxiv:primary_category", ns) or entry.find("{http://arxiv.org/schemas/atom}primary_category")
                if pc is not None and pc.get("term"):
                    primary_cat = pc.get("term", "")
                out.append({
                    "paper_id": arxiv_id,
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "abstract": abstract,
                    "url": id_text or f"https://arxiv.org/abs/{arxiv_id}",
                    "pdf_url": pdf_url,
                    "primary_category": primary_cat,
                    "published": pub_date,
                    "source": "arxiv",
                })
            return out
        except ET.ParseError as e:
            logger.warning(f"arXiv Atom 解析失败: {e}")
            return []

    def _build_search_query(self, query: str, category: str) -> str:
        """构建 API search_query 字符串。"""
        parts = []
        if query:
            parts.append(f"all:{quote_plus(query)}")
        if category:
            parts.append(f"cat:{quote_plus(category)}")
        return " AND ".join(parts) if parts else "all:"

    def _search_arxiv(
        self, query: str, category: str, limit: int, sort_by_submitted: bool
    ) -> List[Dict[str, Any]]:
        search_query = self._build_search_query(query, category)
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": min(limit * 2, 200),
        }
        if sort_by_submitted:
            params["sortBy"] = "submittedDate"
            params["sortOrder"] = "descending"
        raw = self._request_arxiv(params)
        papers = self._parse_atom_entries(raw)
        return papers[:limit]

    def _search_latest_arxiv(self, limit: int) -> List[Dict[str, Any]]:
        # arXiv 要求 search_query 非空，用宽泛查询获取近期论文
        params = {
            "search_query": "all:the",  # 宽泛词以获取最新收录
            "start": 0,
            "max_results": limit,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        raw = self._request_arxiv(params)
        return self._parse_atom_entries(raw)[:limit]

    def _fetch_by_id(self, arxiv_id: str) -> List[Dict[str, Any]]:
        """通过 arXiv ID 获取单篇论文（可能带版本号如 2301.12345v1）。"""
        params = {"id_list": arxiv_id.replace(" ", ""), "max_results": 1}
        raw = self._request_arxiv(params)
        return self._parse_atom_entries(raw)


# ---------------------------------------------------------------------------
# 多源学术搜索：arXiv + Semantic Scholar，合并后取最新 10 篇并下载到指定保存路径（目录）
# ---------------------------------------------------------------------------

def _normalize_paper_date(p: Dict[str, Any]) -> datetime:
    """用于排序：从论文 dict 得到可比较的日期（优先 published/year）。"""
    pub = p.get("published") or p.get("updated")
    if isinstance(pub, str) and pub:
        try:
            s = pub.replace("Z", "+00:00")[:19]
            if "T" in s:
                return datetime.fromisoformat(s)
            if len(pub) >= 10:
                return datetime.strptime(pub[:10], "%Y-%m-%d")
        except Exception:
            pass
    y = p.get("year")
    if y is not None:
        try:
            return datetime(int(y), 1, 1)
        except Exception:
            pass
    return datetime.min


class AcademicPaperSearchTool(BaseTool):
    """
    多源学术论文搜索：同时查 arXiv 与 Semantic Scholar，按时间取最新 10 篇，可下载 PDF 到指定目录。

    适用：需要学术文献、研究综述、论文引用时使用；仅需概念定义用 wikipedia_search，仅需普通网页用 web_search，不必用本工具。
    """

    def __init__(
        self,
        semantic_scholar_api_key: Optional[str] = None,
        version: str = "1.0.0"
    ):
        schema = ParameterSchema(version="1.0.0")
        schema.add_parameter(ParameterDefinition(
            name="query",
            param_type=ParameterType.STRING,
            description="搜索关键词（同时用于 arXiv 与 Semantic Scholar）",
            required=True
        ))
        schema.add_parameter(ParameterDefinition(
            name="save_path",
            param_type=ParameterType.STRING,
            description="保存路径（目录）：最新 10 篇 PDF 将保存到该目录下",
            required=False
        ))
        schema.add_parameter(ParameterDefinition(
            name="limit_per_source",
            param_type=ParameterType.INTEGER,
            description="每个源返回的最大条数（合并前）",
            required=False,
            default=20,
            constraints={"min": 1, "max": 100}
        ))
        super().__init__(
            name="academic_paper_search",
            description="多源学术搜索（arXiv + Semantic Scholar）：适用需文献/论文时。仅需概念用 wikipedia_search，仅需网页用 web_search。按时间取最新 10 篇，可下载 PDF。",
            tool_type="search",
            version=version,
            parameter_schema=schema
        )
        self._ss_api_key = semantic_scholar_api_key
        self._arxiv = ArxivSearchTool()
        self._ss = SemanticScholarSearchTool(api_key=semantic_scholar_api_key)

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        self._record_usage()
        query = (parameters.get("query") or "").strip()
        if not query:
            return self.create_error_result("缺少参数: query")
        save_path = (parameters.get("save_path") or "").strip()
        limit_per = max(1, min(parameters.get("limit_per_source", 20), 100))

        try:
            # 1) arXiv 与 Semantic Scholar 各搜一批（单源失败不影响另一源，下载失败不中断）
            arxiv_result = None
            ss_result = None
            try:
                arxiv_result = self._arxiv.execute({
                    "query": query,
                    "limit": limit_per,
                    "sort_by_submitted": True,
                })
            except Exception as e:
                logger.warning(f"arXiv 检索失败，继续使用其他源: {e}")
            try:
                ss_result = self._ss.execute({
                    "query": query,
                    "limit": limit_per,
                    "sort_by_year": True,
                })
            except Exception as e:
                logger.warning(f"Semantic Scholar 检索失败，继续使用其他源: {e}")
            combined: List[Dict[str, Any]] = []
            if arxiv_result and arxiv_result.success and arxiv_result.data:
                papers = arxiv_result.data.get("papers") or arxiv_result.data.get("latest_10_papers") or []
                for p in papers:
                    p = dict(p)
                    p.setdefault("source", "arxiv")
                    p.setdefault("pdf_url", p.get("pdf_url") or (f"https://arxiv.org/pdf/{p.get('paper_id', '')}.pdf" if p.get("paper_id") else ""))
                    combined.append(p)
            if ss_result and ss_result.success and ss_result.data:
                for key in ("papers", "latest_10_papers"):
                    for p in (ss_result.data.get(key) or []):
                        p = dict(p)
                        p.setdefault("source", "semantic_scholar")
                        p.setdefault("pdf_url", p.get("open_access_pdf_url") or "")
                        combined.append(p)
            # 2) 按时间排序，取最新 10 篇
            combined.sort(key=_normalize_paper_date, reverse=True)
            latest_10 = combined[:10]
            # 3) 若提供 save_path（目录路径），下载 PDF 到该目录
            if save_path:
                try:
                    os.makedirs(save_path, exist_ok=True)
                except OSError as e:
                    logger.warning(f"创建目录失败 {save_path}: {e}")
                for p in latest_10:
                    pdf_url = p.get("pdf_url") or p.get("open_access_pdf_url") or ""
                    if (not pdf_url or not pdf_url.strip()) and p.get("source") == "semantic_scholar" and p.get("paper_id"):
                        detail = self._ss._get_paper_by_id(p["paper_id"], with_pdf_url=True)
                        if detail and detail.get("open_access_pdf_url"):
                            pdf_url = detail["open_access_pdf_url"]
                            p["pdf_url"] = pdf_url
                    if not pdf_url or not pdf_url.strip():
                        continue
                    pid = p.get("paper_id") or p.get("title") or "unknown"
                    safe_name = re.sub(r'[^\w\u4e00-\u9fa5\-\.]', "_", (p.get("title") or pid))[:80] or pid
                    path = os.path.join(save_path, f"{safe_name}.pdf")
                    # 若阅读路径中已存在该论文，不再重复下载
                    if os.path.isfile(path):
                        p["pdf_local_path"] = path
                        logger.debug(f"论文已存在，跳过下载: {path}")
                        continue
                    try:
                        import requests
                        r = requests.get(pdf_url, timeout=60, stream=True)
                        r.raise_for_status()
                        with open(path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        p["pdf_local_path"] = path
                        logger.info(f"已保存 PDF: {path}")
                    except Exception as e:
                        logger.warning(f"下载 PDF 失败 {pdf_url}: {e}")

            payload = {
                "papers": combined,
                "latest_10_papers": latest_10,
                "downloaded_to": save_path if save_path else None,
            }
            qa = QualityAssessment(
                relevance_score=0.85,
                confidence_score=0.85,
                completeness_score=min(len(combined) / 20.0, 1.0),
                assessment_details={
                    "sources": ["arxiv", "semantic_scholar"],
                    "total_combined": len(combined),
                    "latest_10_count": len(latest_10),
                },
            )
            qa.determine_quality_level()
            return self.create_success_result(
                payload,
                metadata={"query": query, "save_path": save_path or None, "latest_10": len(latest_10)},
                quality_assessment=qa,
            )
        except Exception as e:
            logger.warning(f"多源学术搜索异常，返回空结果以保证智能体继续运行: {e}")
            # 下载/检索失败时不抛错，返回空结果以便第一层、第二层智能体继续运行
            return self.create_success_result(
                {"papers": [], "latest_10_papers": [], "downloaded_to": None},
                metadata={"query": query, "save_path": (parameters.get("save_path") or "").strip() or None, "error": str(e), "degraded": True},
                quality_assessment=QualityAssessment(
                    relevance_score=0.0,
                    confidence_score=0.0,
                    completeness_score=0.0,
                    quality_level="LOW",
                    assessment_details={"reason": "search_or_download_failed", "error": str(e)},
                ),
            )
