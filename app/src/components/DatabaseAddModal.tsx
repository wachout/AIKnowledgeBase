import React, { useState } from 'react';
import { X } from 'lucide-react';
import { insertSqlInfo } from '../services/api';

interface DatabaseAddModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  user_name: string;
  password: string;
  user_id: string;
}

const DatabaseAddModal: React.FC<DatabaseAddModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  user_name,
  password,
  user_id,
}) => {
  const [formData, setFormData] = useState({
    ip: '',
    port: '',
    sql_type: 'mysql' as 'mysql' | 'postgresql',
    sql_name: '',
    sql_user_name: '',
    sql_user_password: '',
    sql_description: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    if (name === 'sql_description' && value.length > 500) {
      return; // 限制描述长度为500字符
    }
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await insertSqlInfo(
        user_name,
        password,
        formData.ip,
        formData.port,
        formData.sql_type,
        formData.sql_name,
        formData.sql_user_name,
        formData.sql_user_password,
        formData.sql_description,
        user_id
      );

      if (result.success) {
        // 重置表单
        setFormData({
          ip: '',
          port: '',
          sql_type: 'mysql',
          sql_name: '',
          sql_user_name: '',
          sql_user_password: '',
          sql_description: '',
        });
        onSuccess();
        onClose();
      } else {
        setError(result.message || '添加数据库失败');
      }
    } catch (err) {
      setError('添加数据库时发生错误，请稍后重试');
      console.error('Error adding database:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-800">添加数据库</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition"
            disabled={loading}
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                数据库IP <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="ip"
                value={formData.ip}
                onChange={handleInputChange}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                placeholder="例如: 127.0.0.1"
                disabled={loading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                数据库端口 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="port"
                value={formData.port}
                onChange={handleInputChange}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                placeholder="例如: 3306"
                disabled={loading}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              数据库类型 <span className="text-red-500">*</span>
            </label>
            <select
              name="sql_type"
              value={formData.sql_type}
              onChange={handleInputChange}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              disabled={loading}
            >
              <option value="mysql">MySQL</option>
              <option value="postgresql">PostgreSQL</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              数据库名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              name="sql_name"
              value={formData.sql_name}
              onChange={handleInputChange}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              placeholder="输入数据库名称"
              disabled={loading}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                用户名 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="sql_user_name"
                value={formData.sql_user_name}
                onChange={handleInputChange}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                placeholder="输入数据库用户名"
                disabled={loading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                密码 <span className="text-red-500">*</span>
              </label>
              <input
                type="password"
                name="sql_user_password"
                value={formData.sql_user_password}
                onChange={handleInputChange}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                placeholder="输入数据库密码"
                disabled={loading}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              数据库描述
              <span className="text-gray-500 text-xs ml-2">
                ({formData.sql_description.length}/500)
              </span>
            </label>
            <textarea
              name="sql_description"
              value={formData.sql_description}
              onChange={handleInputChange}
              maxLength={500}
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-none"
              placeholder="输入数据库描述（最多500字符）"
              disabled={loading}
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition disabled:opacity-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? '保存中...' : '保存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DatabaseAddModal;
