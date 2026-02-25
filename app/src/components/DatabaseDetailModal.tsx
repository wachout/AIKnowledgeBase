import React, { useState, useEffect } from 'react';
import { X, Plus, Trash2 } from 'lucide-react';
import { Database, TableInfo, ColumnInfo, SqlItem } from '../types';
import { getTableInfo, updateSqlInfo, deleteSqlInfo } from '../services/api';

interface DatabaseDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  database: Database | null;
  user_name: string;
  password: string;
  user_id: string;
}

interface RelationRow {
  id: string;
  from_table: string;
  from_col: string;
  to_table: string;
  to_col: string;
}

interface ColumnDescription {
  [tableName: string]: {
    [columnName: string]: string;
  };
}

const DatabaseDetailModal: React.FC<DatabaseDetailModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  database,
  user_name,
  password,
  user_id,
}) => {
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [selectedTable, setSelectedTable] = useState<string>('');
  const [tableDescription, setTableDescription] = useState<{ [key: string]: string }>({});
  const [columnDescriptions, setColumnDescriptions] = useState<ColumnDescription>({});
  const [relations, setRelations] = useState<RelationRow[]>([]);
  const [sqlList, setSqlList] = useState<SqlItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [_error, setError] = useState('');
  const [_loadingTables, setLoadingTables] = useState(false);

  // 数据库描述编辑状态
  const [databaseDescription, setDatabaseDescription] = useState('');

  // 关联关系添加状态
  const [newRelation, setNewRelation] = useState({
    from_table: '',
    from_col: '',
    to_table: '',
    to_col: '',
  });

  useEffect(() => {
    if (isOpen && database) {
      // 初始化数据库描述
      setDatabaseDescription(database.sql_description || '');
      loadTableInfo();
    }
  }, [isOpen, database]);

  const loadTableInfo = async () => {
    if (!database) return;
    setLoadingTables(true);
    setError('');

    try {
      const result = await getTableInfo(
        database.ip,
        database.port,
        database.sql_type,
        database.sql_name,
        user_id,
        database.sql_id
      );

      if (result.success && result.table_list) {
        setTables(result.table_list);
        // 初始化表描述
        const descriptions: { [key: string]: string } = {};
        result.table_list.forEach((table) => {
          if (table.table_description) {
            descriptions[table.table_name] = table.table_description;
          }
        });
        setTableDescription(descriptions);

        // 初始化列描述
        const colDescriptions: ColumnDescription = {};
        result.table_list.forEach((table) => {
          if (table.columns) {
            colDescriptions[table.table_name] = {};
            table.columns.forEach((col) => {
              // 从col_info中提取comment，如果没有则为空
              const colInfo = typeof col.col_info === 'string' ? JSON.parse(col.col_info || '{}') : (col.col_info || {});
              colDescriptions[table.table_name][col.col_name] = colInfo.comment || '';
            });
          }
        });
        setColumnDescriptions(colDescriptions);

        // 加载关联关系（如果API返回）
        const resultWithRelations = result as any;
        if (resultWithRelations.relations && Array.isArray(resultWithRelations.relations)) {
          const loadedRelations: RelationRow[] = resultWithRelations.relations.map((rel: any, index: number) => ({
            id: rel.rel_id || `rel_loaded_${Date.now()}_${index}`,
            from_table: rel.from_table,
            from_col: rel.from_col,
            to_table: rel.to_table,
            to_col: rel.to_col,
          }));
          setRelations(loadedRelations);
        }

        // 加载SQL列表（如果API返回）
        const resultWithSqlList = result as any;
        if (resultWithSqlList.sql_list && Array.isArray(resultWithSqlList.sql_list)) {
          const loadedSqlList: SqlItem[] = resultWithSqlList.sql_list.map((sqlItem: any) => ({
            sql: sqlItem.sql || '',
            des: sqlItem.des || '',
          }));
          setSqlList(loadedSqlList);
        }

        // 如果第一个表存在，默认选中
        if (result.table_list.length > 0 && !selectedTable) {
          setSelectedTable(result.table_list[0].table_name);
        }
      } else {
        setError(result.message || '加载表信息失败');
      }
    } catch (err) {
      setError('加载表信息时发生错误');
      console.error('Error loading table info:', err);
    } finally {
      setLoadingTables(false);
    }
  };

  const handleTableSelect = (tableName: string) => {
    setSelectedTable(tableName);
  };

  const handleColumnDescriptionChange = (tableName: string, columnName: string, description: string) => {
    setColumnDescriptions(prev => ({
      ...prev,
      [tableName]: {
        ...prev[tableName],
        [columnName]: description,
      },
    }));
  };

  const handleAddRelation = () => {
    if (!newRelation.from_table || !newRelation.from_col || !newRelation.to_table || !newRelation.to_col) {
      return;
    }

    const newRelationRow: RelationRow = {
      id: `rel_${Date.now()}`,
      from_table: newRelation.from_table,
      from_col: newRelation.from_col,
      to_table: newRelation.to_table,
      to_col: newRelation.to_col,
    };

    setRelations(prev => [...prev, newRelationRow]);
    setNewRelation({
      from_table: '',
      from_col: '',
      to_table: '',
      to_col: '',
    });
  };

  const handleRemoveRelation = (relationId: string) => {
    setRelations(prev => prev.filter(rel => rel.id !== relationId));
  };

  const handleAddSqlItem = () => {
    const newSqlItem: SqlItem = {
      sql: '',
      des: '',
    };
    setSqlList(prev => [...prev, newSqlItem]);
  };

  const handleRemoveSqlItem = (index: number) => {
    setSqlList(prev => prev.filter((_, i) => i !== index));
  };

  const handleSqlItemChange = (index: number, field: 'sql' | 'des', value: string) => {
    setSqlList(prev => prev.map((item, i) =>
      i === index ? { ...item, [field]: value } : item
    ));
  };

  const getTableColumns = (tableName: string): ColumnInfo[] => {
    const table = tables.find(t => t.table_name === tableName);
    return table?.columns || [];
  };

  const handleConfirm = async () => {
    if (!database) return;
    setLoading(true);
    setError('');

    try {
      // 准备数据 - 所有表的描述信息，格式: {"tables":[{"table_description":"表格描述","table_name":"表格名称"}]}
      const tablesData = tables.map(table => ({
        table_name: table.table_name,
        table_description: tableDescription[table.table_name] || '',
      }));

      // 准备列描述信息
      const columnDescriptionsData: any[] = [];
      Object.entries(columnDescriptions).forEach(([tableName, columns]) => {
        Object.entries(columns).forEach(([columnName, description]) => {
          if (description.trim()) {
            // 找到对应的列信息
            const table = tables.find(t => t.table_name === tableName);
            const column = table?.columns?.find(c => c.col_name === columnName);
            if (column) {
              columnDescriptionsData.push({
                table_name: tableName,
                column_name: columnName,
                comment: description.trim(),
              });
            }
          }
        });
      });

      // 准备关联关系数据 - 包含所有表的关联关系
      const relationsData = relations
        .filter(r => r.from_table && r.from_col && r.to_table && r.to_col)
        .map(r => ({
          from_table: r.from_table,
          from_col: r.from_col,
          to_table: r.to_table,
          to_col: r.to_col,
        }));

      // 准备SQL列表数据
      const sqlListData = sqlList
        .filter(sqlItem => sqlItem.sql.trim() && sqlItem.des.trim())
        .map(sqlItem => ({
          sql: sqlItem.sql.trim(),
          des: sqlItem.des.trim(),
        }));

      const result = await updateSqlInfo(
        user_id,
        database.sql_id,
        {
          tables: tablesData,
          columns: columnDescriptionsData,
          relations: relationsData,
          sql_description: databaseDescription.trim(),
          sql_list: sqlListData,
        }
      );

      if (result.success) {
        onSuccess();
        onClose();
      } else {
        setError(result.message || '更新数据库信息失败');
      }
    } catch (err) {
      setError('更新数据库信息时发生错误');
      console.error('Error updating database:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!database) return;

    if (window.confirm(`确定要删除数据库 "${database.sql_name}" 吗？此操作不可恢复。`)) {
      setLoading(true);
      try {
        const result = await deleteSqlInfo(user_name, password, database.sql_id);
        if (result.success) {
          onSuccess();
          onClose();
        } else {
          setError(result.message || '删除数据库失败');
        }
      } catch (err) {
        setError('删除数据库时发生错误');
        console.error('Error deleting database:', err);
      } finally {
        setLoading(false);
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-7xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* 头部 */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">
            数据库详情: {database?.sql_name}
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-full transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 主体内容 */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* 顶部：表格描述 */}
          <div className="p-4 border-b border-gray-200">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              数据库描述
            </label>
            <textarea
              value={databaseDescription}
              onChange={(e) => setDatabaseDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows={3}
              placeholder="请输入数据库描述信息..."
            />
          </div>

          {/* 中间：表格、表格描述、列、列描述 */}
          <div className="flex-1 overflow-hidden flex" style={{ height: '50vh' }}>
            {/* 表格列表 (1/6) */}
            <div className="w-1/6 border-r border-gray-200 flex flex-col">
              <h3 className="px-4 py-3 text-sm font-medium text-gray-900 bg-gray-50 border-b border-gray-200">
                表格列表
              </h3>
              <div className="flex-1 overflow-y-auto">
                {tables.map((table) => (
                  <button
                    key={table.table_name}
                    onClick={() => handleTableSelect(table.table_name)}
                    className={`w-full px-4 py-2 text-left text-sm hover:bg-gray-100 transition ${
                      selectedTable === table.table_name
                        ? 'bg-blue-100 text-blue-900 border-r-2 border-blue-500'
                        : 'text-gray-700'
                    }`}
                  >
                    {table.table_name}
                  </button>
                ))}
              </div>
            </div>

            {/* 表格描述 (1/6) */}
            <div className="w-1/6 border-r border-gray-200 flex flex-col">
              <h3 className="px-4 py-3 text-sm font-medium text-gray-900 bg-gray-50 border-b border-gray-200">
                表格描述
              </h3>
              <div className="flex-1 overflow-y-auto p-4">
                {selectedTable ? (
                  <textarea
                    value={tableDescription[selectedTable] || ''}
                    onChange={(e) => {
                      setTableDescription(prev => ({
                        ...prev,
                        [selectedTable]: e.target.value
                      }));
                    }}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    rows={8}
                    placeholder="输入表格详细描述..."
                  />
                ) : (
                  <div className="text-sm text-gray-500 text-center py-4">
                    请先选择表格
                  </div>
                )}
              </div>
            </div>

            {/* 列列表 (2/6) */}
            <div className="w-2/6 border-r border-gray-200 flex flex-col">
              <h3 className="px-4 py-3 text-sm font-medium text-gray-900 bg-gray-50 border-b border-gray-200">
                列表 ({selectedTable || '请选择表格'}) 的列
              </h3>
              <div className="flex-1 overflow-y-auto">
                {selectedTable && getTableColumns(selectedTable).map((column) => (
                  <div key={column.col_name} className="px-4 py-2 border-b border-gray-100">
                    <div className="text-sm font-medium text-gray-900">{column.col_name}</div>
                    <div className="text-xs text-gray-500">{column.col_type}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* 列描述 (2/6) */}
            <div className="w-2/6 flex flex-col">
              <h3 className="px-4 py-3 text-sm font-medium text-gray-900 bg-gray-50 border-b border-gray-200">
                列描述
              </h3>
              <div className="flex-1 overflow-y-auto">
                {selectedTable && getTableColumns(selectedTable).map((column) => (
                  <div key={column.col_name} className="px-4 py-2 border-b border-gray-100">
                    <div className="text-sm font-medium text-gray-900 mb-1">{column.col_name}</div>
                    <textarea
                      value={columnDescriptions[selectedTable]?.[column.col_name] || ''}
                      onChange={(e) => handleColumnDescriptionChange(selectedTable, column.col_name, e.target.value)}
                      className="w-full px-2 py-1 text-xs border border-gray-300 rounded resize-none focus:ring-1 focus:ring-blue-500 focus:border-transparent"
                      rows={2}
                      placeholder="输入列描述..."
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 底部：关联关系管理 */}
          <div className="border-t border-gray-200 p-4">
            <h3 className="text-sm font-medium text-gray-900 mb-3">列关联关系</h3>

            {/* 现有关联关系 */}
            {relations.length > 0 && (
              <div className="mb-4">
                <h4 className="text-xs font-medium text-gray-700 mb-2">现有关联关系</h4>
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {relations.map((relation) => (
                    <div key={relation.id} className="flex items-center gap-2 p-2 bg-gray-50 rounded text-sm">
                      <span className="text-blue-600 font-medium">
                        {relation.from_table}.{relation.from_col}
                      </span>
                      <span className="text-gray-500">→</span>
                      <span className="text-green-600 font-medium">
                        {relation.to_table}.{relation.to_col}
                      </span>
                      <button
                        onClick={() => handleRemoveRelation(relation.id)}
                        className="ml-auto p-1 text-red-500 hover:bg-red-100 rounded"
                        disabled={loading}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 添加新关联关系 */}
            <div className="grid grid-cols-9 gap-2 items-end">
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">源表</label>
                <select
                  value={newRelation.from_table}
                  onChange={(e) => {
                    setNewRelation(prev => ({ ...prev, from_table: e.target.value, from_col: '' }));
                  }}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">选择表</option>
                  {tables.map((table) => (
                    <option key={table.table_name} value={table.table_name}>
                      {table.table_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">源列</label>
                <select
                  value={newRelation.from_col}
                  onChange={(e) => setNewRelation(prev => ({ ...prev, from_col: e.target.value }))}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                  disabled={!newRelation.from_table}
                >
                  <option value="">选择列</option>
                  {newRelation.from_table && getTableColumns(newRelation.from_table).map((col) => (
                    <option key={col.col_name} value={col.col_name}>
                      {col.col_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">目标表</label>
                <select
                  value={newRelation.to_table}
                  onChange={(e) => {
                    setNewRelation(prev => ({ ...prev, to_table: e.target.value, to_col: '' }));
                  }}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">选择表</option>
                  {tables.map((table) => (
                    <option key={table.table_name} value={table.table_name}>
                      {table.table_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">目标列</label>
                <select
                  value={newRelation.to_col}
                  onChange={(e) => setNewRelation(prev => ({ ...prev, to_col: e.target.value }))}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                  disabled={!newRelation.to_table}
                >
                  <option value="">选择列</option>
                  {newRelation.to_table && getTableColumns(newRelation.to_table).map((col) => (
                    <option key={col.col_name} value={col.col_name}>
                      {col.col_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="col-span-1">
                <button
                  onClick={handleAddRelation}
                  disabled={!newRelation.from_table || !newRelation.from_col || !newRelation.to_table || !newRelation.to_col}
                  className="w-full px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* SQL描述管理 */}
          <div className="border-t border-gray-200 p-4">
            <h3 className="text-sm font-medium text-gray-900 mb-3">SQL描述</h3>

            {/* SQL描述列表 - 最多显示两行，超出滚动 */}
            <div className="max-h-32 overflow-y-auto">
              {sqlList.length > 0 ? (
                <div className="space-y-2">
                  {sqlList.map((sqlItem, index) => (
                    <div key={index} className="border border-gray-200 rounded p-3 bg-gray-50">
                      <div className="grid grid-cols-3 gap-2">
                        {/* 第一列：SQL语句 */}
                        <div className="col-span-1">
                          <label className="block text-xs font-medium text-gray-700 mb-1">SQL语句</label>
                          <textarea
                            value={sqlItem.sql}
                            onChange={(e) => handleSqlItemChange(index, 'sql', e.target.value)}
                            className="w-full px-2 py-1 text-xs border border-gray-300 rounded resize-none focus:ring-1 focus:ring-blue-500 focus:border-transparent"
                            rows={2}
                            placeholder="输入SQL语句..."
                          />
                        </div>

                        {/* 第二列：问题描述 */}
                        <div className="col-span-1">
                          <label className="block text-xs font-medium text-gray-700 mb-1">问题描述</label>
                          <textarea
                            value={sqlItem.des}
                            onChange={(e) => handleSqlItemChange(index, 'des', e.target.value)}
                            className="w-full px-2 py-1 text-xs border border-gray-300 rounded resize-none focus:ring-1 focus:ring-blue-500 focus:border-transparent"
                            rows={2}
                            placeholder="输入问题描述..."
                          />
                        </div>

                        {/* 第三列：删除按钮 */}
                        <div className="col-span-1 flex flex-col justify-start">
                          <button
                            onClick={() => handleRemoveSqlItem(index)}
                            className="flex items-center gap-1 px-2 py-1 text-xs text-red-600 hover:bg-red-50 rounded self-start"
                            disabled={loading}
                          >
                            <Trash2 className="w-3 h-3" />
                            删除
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}

                  {/* 在有项目时，添加按钮显示在列表底部 */}
                  <div className="flex justify-end pt-2">
                    <button
                      onClick={handleAddSqlItem}
                      disabled={loading}
                      className="flex items-center gap-2 px-3 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
                    >
                      <Plus className="w-4 h-4" />
                      添加SQL描述
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-center py-4">
                  <div className="text-gray-500 text-sm mb-3">
                    暂无SQL描述，点击下方按钮添加
                  </div>
                  <button
                    onClick={handleAddSqlItem}
                    disabled={loading}
                    className="flex items-center gap-2 px-3 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition mx-auto"
                  >
                    <Plus className="w-4 h-4" />
                    添加SQL描述
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 底部按钮 */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button
            onClick={handleDelete}
            disabled={loading}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition disabled:opacity-50"
          >
            删除
          </button>
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={handleConfirm}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '保存中...' : '确认'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DatabaseDetailModal;