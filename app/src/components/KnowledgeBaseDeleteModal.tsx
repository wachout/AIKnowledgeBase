import React, { useState } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import { deleteKnowledgeBase } from '../services/api';

interface KnowledgeBaseDeleteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  knowledgeBase: {
    knowledge_id: string;
    knowledge_name: string;
  } | null;
  user_name: string;
  password: string;
  user_id: string;
}

const KnowledgeBaseDeleteModal: React.FC<KnowledgeBaseDeleteModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  knowledgeBase,
  user_name,
  password,
  user_id,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen || !knowledgeBase) return null;

  const handleDelete = async () => {
    setError('');
    setLoading(true);

    try {
      const result = await deleteKnowledgeBase(
        user_name,
        password,
        user_id,
        knowledgeBase.knowledge_id,
        knowledgeBase.knowledge_name
      );

      if (result.success) {
        onSuccess();
        onClose();
      } else {
        setError(result.message || '删除知识库失败');
      }
    } catch (err) {
      setError('删除知识库时发生错误，请稍后重试');
      console.error('Error deleting knowledge base:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-800">删除知识库</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition"
            disabled={loading}
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="p-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}

          <div className="flex items-start gap-4 mb-6">
            <div className="flex-shrink-0">
              <AlertTriangle className="w-8 h-8 text-yellow-500" />
            </div>
            <div className="flex-1">
              <p className="text-gray-800 font-medium mb-2">
                确定要删除知识库 "{knowledgeBase.knowledge_name}" 吗？
              </p>
              <p className="text-sm text-gray-600">
                此操作不可恢复，删除后将无法访问该知识库及其所有文件。
              </p>
            </div>
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
              type="button"
              onClick={handleDelete}
              disabled={loading}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? '删除中...' : '确认删除'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBaseDeleteModal;

