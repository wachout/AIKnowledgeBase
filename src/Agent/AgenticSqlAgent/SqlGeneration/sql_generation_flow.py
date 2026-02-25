# -*- coding:utf-8 -*-
"""
SQL生成智能体流程
协调SQL生成、检测、纠错、优化、再检测、核对等步骤
"""

from typing import Dict, Any, List, Optional
from Agent.AgenticSqlAgent.SqlGeneration.sql_generation_agent import SqlGenerationAgent
from Agent.AgenticSqlAgent.SqlGeneration.sql_check_run_agent import SqlCheckRunAgent
from Agent.AgenticSqlAgent.SqlGeneration.sql_correction_agent import SqlCorrectionAgent
from Agent.AgenticSqlAgent.SqlGeneration.sql_optimization_agent import SqlOptimizationAgent
from Agent.AgenticSqlAgent.SqlGeneration.sql_recheck_run_agent import SqlRecheckRunAgent
from Agent.AgenticSqlAgent.SqlGeneration.sql_verification_agent import SqlVerificationAgent
from Agent.AgenticSqlAgent.tools.database_tools import query_columns_by_table_id


class SqlGenerationFlow:
    """SQL生成智能体流程：协调SQL生成、检测、纠错、优化、再检测、核对等步骤"""
    
    def __init__(self, max_retries: int = 3):
        """
        初始化SQL生成流程
        
        Args:
            max_retries: 最大重试次数（用于纠错循环）
        """
        self.max_retries = max_retries
        self.generation_agent = SqlGenerationAgent()
        self.check_run_agent = SqlCheckRunAgent()
        self.correction_agent = SqlCorrectionAgent()
        self.optimization_agent = SqlOptimizationAgent()
        self.recheck_run_agent = SqlRecheckRunAgent()
        self.verification_agent = SqlVerificationAgent()
    
    def run_flow(self, query: str, intent_analysis: Dict[str, Any],
                relevant_tables: List[Dict[str, Any]], sql_id: str,
                database_info: Dict[str, Any], table_check_result: Dict[str, Any] = None,
                step_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        运行SQL生成流程
        
        流程：
        1. SQL生成智能体：生成初始SQL
        2. SQL检测运行智能体：检测SQL并尝试运行
        3. SQL纠错智能体：如果有错误，修正SQL（循环直到成功或达到最大重试次数）
        4. SQL优化智能体：优化SQL性能
        5. SQL再检测运行：再次检测和运行优化后的SQL
        6. SQL核对输出：核对执行结果是否满足用户需求
        
        Args:
            query: 用户查询问题
            intent_analysis: 意图分析结果
            relevant_tables: 相关表列表
            sql_id: 数据库ID
            database_info: 数据库信息
            table_check_result: 表核对结果
            step_callback: 步骤回调函数，用于流式返回步骤信息
            
        Returns:
            完整的SQL生成流程结果
        """
        def _notify_step(step_name: str, step_data: Dict[str, Any]):
            """通知步骤完成"""
            if step_callback:
                try:
                    step_callback(step_name, step_data)
                except Exception as e:
                    print(f"⚠️ 步骤回调失败 ({step_name}): {e}")
        
        try:
            # 准备表结构信息
            tables_info_for_check = []
            for table_info in relevant_tables:
                table_id = table_info.get("table_id", "")
                table_name = table_info.get("table_name", "")
                
                columns = query_columns_by_table_id(table_id)
                columns_detail = []
                for col in columns:
                    col_info = col.get("col_info", {})
                    if isinstance(col_info, str):
                        try:
                            import json
                            col_info = json.loads(col_info)
                        except:
                            col_info = {}
                    
                    columns_detail.append({
                        "col_name": col.get("col_name", ""),
                        "col_type": col.get("col_type", ""),
                        "col_comment": col_info.get("comment", "") if isinstance(col_info, dict) else ""
                    })
                
                tables_info_for_check.append({
                    "table_name": table_name,
                    "columns": columns_detail
                })
            
            # 步骤1: SQL生成
            print("\n📝 步骤1: SQL生成...")
            _notify_step("sql_flow_step_1_generation", {"status": "start"})
            
            generation_result = self.generation_agent.generate_sql(
                query, intent_analysis, relevant_tables, sql_id, database_info, table_check_result
            )
            
            if not generation_result.get("success"):
                error_msg = f"SQL生成失败: {generation_result.get('error', '未知错误')}"
                _notify_step("sql_flow_step_1_generation", {
                    "status": "failed",
                    "error": error_msg
                })
                return {
                    "success": False,
                    "error": error_msg,
                    "step": "generation"
                }
            
            current_sql = generation_result.get("sql", "")
            generation_columns_used = generation_result.get("columns_used", [])  # 智能体返回的列信息
            print(f"   ✅ 生成的SQL: {current_sql}")
            
            _notify_step("sql_flow_step_1_generation", {
                "status": "completed",
                "sql": current_sql,
                "explanation": generation_result.get("explanation", ""),
                "columns_used": generation_columns_used  # 传递列信息
            })
            
            # 步骤2: SQL检测运行
            print("\n🔍 步骤2: SQL检测运行...")
            _notify_step("sql_flow_step_2_check_run", {"status": "start"})
            
            check_run_result = self.check_run_agent.check_and_run_sql(
                current_sql, query, sql_id, database_info.get("sql_type", "mysql"), tables_info_for_check
            )
            
            is_valid = check_run_result.get("is_valid", False)
            is_safe = check_run_result.get("is_safe", True)
            execution_result = check_run_result.get("execution_result", {})
            
            print(f"   ✅ 检测结果: 语法{'正确' if is_valid else '错误'}, 安全性{'安全' if is_safe else '不安全'}")
            
            _notify_step("sql_flow_step_2_check_run", {
                "status": "completed",
                "is_valid": is_valid,
                "is_safe": is_safe,
                "errors": check_run_result.get("errors", []),
                "warnings": check_run_result.get("warnings", []),
                "execution_result": execution_result
            })
            
            # 步骤3: SQL纠错（如果有错误，循环纠错）
            if not is_valid or not is_safe or not execution_result.get("executed", False):
                print("\n🔧 步骤3: SQL纠错...")
                _notify_step("sql_flow_step_3_correction", {"status": "start"})
                
                errors = check_run_result.get("errors", [])
                warnings = check_run_result.get("warnings", [])
                execution_error = execution_result.get("error") if execution_result else None
                
                for retry in range(self.max_retries):
                    print(f"   🔄 纠错尝试 {retry + 1}/{self.max_retries}...")
                    
                    correction_result = self.correction_agent.correct_sql(
                        current_sql, query, database_info.get("sql_type", "mysql"),
                        errors, warnings, tables_info_for_check, execution_error, execution_result
                    )
                    
                    if not correction_result.get("success"):
                        print(f"   ⚠️ 纠错失败: {correction_result.get('error', '未知错误')}")
                        break
                    
                    corrected_sql = correction_result.get("corrected_sql", current_sql)
                    
                    if corrected_sql == current_sql:
                        print(f"   ℹ️ SQL未发生变化，跳过后续纠错")
                        break
                    
                    current_sql = corrected_sql
                    print(f"   ✅ 修正后的SQL: {corrected_sql}")
                    
                    # 再次检测运行
                    check_run_result = self.check_run_agent.check_and_run_sql(
                        current_sql, query, sql_id, database_info.get("sql_type", "mysql"), tables_info_for_check
                    )
                    
                    is_valid = check_run_result.get("is_valid", False)
                    is_safe = check_run_result.get("is_safe", True)
                    execution_result = check_run_result.get("execution_result", {})
                    
                    if is_valid and is_safe and execution_result.get("executed", False):
                        print(f"   ✅ 纠错成功，SQL可以正常执行")
                        break
                    else:
                        errors = check_run_result.get("errors", [])
                        warnings = check_run_result.get("warnings", [])
                        execution_error = execution_result.get("error") if execution_result else None
                
                _notify_step("sql_flow_step_3_correction", {
                    "status": "completed",
                    "corrected_sql": current_sql,
                    "corrections": correction_result.get("corrections", []) if 'correction_result' in locals() else [],
                    "is_valid": is_valid,
                    "is_safe": is_safe,
                    "execution_result": execution_result
                })
            
            # 如果仍然有错误，返回错误
            if not is_valid or not is_safe:
                return {
                    "success": False,
                    "error": "SQL纠错后仍然存在错误",
                    "sql": current_sql,
                    "errors": check_run_result.get("errors", []),
                    "warnings": check_run_result.get("warnings", []),
                    "step": "correction"
                }
            
            # # 步骤4: SQL优化
            # print("\n⚡ 步骤4: SQL优化...")
            # _notify_step("sql_flow_step_4_optimization", {"status": "start"})
            
            # 保存优化前的SQL和执行结果
            sql_before_optimization = current_sql
            execution_result_before_optimization = execution_result
            
            optimization_result = self.optimization_agent.optimize_sql(
                current_sql, query, database_info.get("sql_type", "mysql"),
                tables_info_for_check, execution_result
            )
            
            if optimization_result.get("success"):
                optimized_sql = optimization_result.get("optimized_sql", current_sql)
                if optimized_sql != current_sql:
                    current_sql = optimized_sql
                    print(f"   ✅ 优化后的SQL: {optimized_sql}")
                else:
                    print(f"   ℹ️ SQL未优化")
            else:
                print(f"   ⚠️ 优化失败，使用原始SQL")
                optimized_sql = current_sql
            
            _notify_step("sql_flow_step_4_optimization", {
                "status": "completed",
                "optimized_sql": optimized_sql,
                "optimizations": optimization_result.get("optimizations", []) if optimization_result.get("success") else [],
                "performance_improvements": optimization_result.get("performance_improvements", "") if optimization_result.get("success") else ""
            })
            
            # 步骤5: SQL再检测运行（仅当SQL被优化时才执行）
            if optimized_sql != sql_before_optimization:
                print("\n🔍 步骤5: SQL再检测运行...")
                _notify_step("sql_flow_step_5_recheck_run", {"status": "start"})
                
                recheck_run_result = self.recheck_run_agent.recheck_and_run_sql(
                    optimized_sql, query, sql_id, database_info.get("sql_type", "mysql"),
                    tables_info_for_check, optimization_result if optimization_result.get("success") else None
                )
                
                is_valid = recheck_run_result.get("is_valid", False)
                is_safe = recheck_run_result.get("is_safe", True)
                final_execution_result = recheck_run_result.get("execution_result", {})
                
                print(f"   ✅ 再检测结果: 语法{'正确' if is_valid else '错误'}, 安全性{'安全' if is_safe else '不安全'}")
                
                _notify_step("sql_flow_step_5_recheck_run", {
                    "status": "completed",
                    "is_valid": is_valid,
                    "is_safe": is_safe,
                    "errors": recheck_run_result.get("errors", []),
                    "warnings": recheck_run_result.get("warnings", []),
                    "execution_result": final_execution_result
                })
                
                # 如果优化后的SQL有问题，回退到优化前的SQL
                if not is_valid or not is_safe or not final_execution_result.get("executed", False):
                    print(f"   ⚠️ 优化后的SQL有问题，回退到优化前的SQL")
                    current_sql = sql_before_optimization
                    final_execution_result = execution_result_before_optimization
                else:
                    current_sql = optimized_sql
            else:
                # SQL未优化，跳过再检测运行，直接使用之前的执行结果
                print(f"   ℹ️ SQL未优化，跳过再检测运行")
                final_execution_result = execution_result_before_optimization
                _notify_step("sql_flow_step_5_recheck_run", {
                    "status": "skipped",
                    "reason": "SQL未优化，无需再检测运行",
                    "execution_result": final_execution_result
                })
            
            # 步骤6: SQL核对输出
            print("\n✔️ 步骤6: SQL核对输出...")
            _notify_step("sql_flow_step_6_verification", {"status": "start"})
            
            verification_result = self.verification_agent.verify_output(
                current_sql, query, final_execution_result, intent_analysis
            )
            
            is_satisfied = verification_result.get("is_satisfied", True)
            satisfaction_score = verification_result.get("satisfaction_score", 1.0)
            
            print(f"   ✅ 核对结果: 满足度 {satisfaction_score:.2f}, {'满足' if is_satisfied else '不满足'}用户需求")
            
            _notify_step("sql_flow_step_6_verification", {
                "status": "completed",
                "is_satisfied": is_satisfied,
                "satisfaction_score": satisfaction_score,
                "verification_reason": verification_result.get("verification_reason", ""),
                "missing_info": verification_result.get("missing_info", []),
                "suggestions": verification_result.get("suggestions", [])
            })
            
            # 返回最终结果（不包含中间步骤的详细信息）
            return {
                "success": True,
                "sql": current_sql,
                "sql_type": database_info.get("sql_type", "mysql"),
                "final_execution_result": final_execution_result,
                "is_satisfied": is_satisfied,
                "satisfaction_score": satisfaction_score,
                "generation_columns_used": generation_columns_used  # SQL生成智能体返回的列信息
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"SQL生成流程失败: {str(e)}",
                "step": "unknown"
            }
