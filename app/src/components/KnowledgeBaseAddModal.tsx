import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { createKnowledgeBase } from '../services/api';

interface KnowledgeBaseAddModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  user_name: string;
  password: string;
}

// 格式化日期为 datetime-local 输入框需要的格式 (YYYY-MM-DDTHH:mm)
const formatDateTimeLocal = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
};

// 获取默认的有效开始时间（当天）
const getDefaultStartTime = (): string => {
  const today = new Date();
  // 设置为当天的 00:00
  today.setHours(0, 0, 0, 0);
  return formatDateTimeLocal(today);
};

// 获取默认的有效结束时间（当前时间往后推50年）
const getDefaultEndTime = (): string => {
  const futureDate = new Date();
  futureDate.setFullYear(futureDate.getFullYear() + 50);
  // 设置为当天的 23:59
  futureDate.setHours(23, 59, 0, 0);
  return formatDateTimeLocal(futureDate);
};

const KnowledgeBaseAddModal: React.FC<KnowledgeBaseAddModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  user_name,
  password,
}) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    valid_start_time: '',
    valid_end_time: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // 当弹窗打开时，设置默认的有效开始时间和结束时间
  useEffect(() => {
    if (isOpen) {
      setFormData({
        name: '',
        description: '',
        valid_start_time: getDefaultStartTime(),
        valid_end_time: getDefaultEndTime(),
      });
      setError('');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // 验证必填字段
    if (!formData.name.trim()) {
      setError('请输入知识库名称');
      return;
    }

    setLoading(true);

    try {
      const result = await createKnowledgeBase(
        user_name,
        password,
        formData.name.trim(),
        formData.description.trim(),
        formData.valid_start_time || undefined,
        formData.valid_end_time || undefined
      );

      if (result.success) {
        // 重置表单
        setFormData({
          name: '',
          description: '',
          valid_start_time: '',
          valid_end_time: '',
        });
        onSuccess();
        onClose();
      } else {
        setError(result.message || '创建知识库失败');
      }
    } catch (err) {
      setError('创建知识库时发生错误，请稍后重试');
      console.error('Error creating knowledge base:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-800">创建知识库</h2>
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

          {/* 第一行：知识库名称 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              知识库名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              placeholder="输入知识库名称"
              disabled={loading}
            />
          </div>

          {/* 第二行：知识库描述 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              知识库描述
            </label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-none"
              placeholder="输入知识库描述"
              disabled={loading}
            />
          </div>

          {/* 可选：有效开始时间 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              有效开始时间
            </label>
            <input
              type="datetime-local"
              name="valid_start_time"
              value={formData.valid_start_time}
              onChange={handleInputChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              disabled={loading}
            />
          </div>

          {/* 可选：有效结束时间 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              有效结束时间
            </label>
            <input
              type="datetime-local"
              name="valid_end_time"
              value={formData.valid_end_time}
              onChange={handleInputChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              disabled={loading}
            />
          </div>

          {/* 底部按钮 */}
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition disabled:opacity-50"
            >
              关闭
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

export default KnowledgeBaseAddModal;

