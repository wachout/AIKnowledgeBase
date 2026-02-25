import React, { useState, useEffect } from 'react';
import { ChevronRight, ChevronLeft, FileText, Download, Copy, X } from 'lucide-react';
import './FileSidebar.css';

// API基础URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:6199/api';

const FileSidebar = ({ isOpen, onToggle, fileContent, fileName, filePath, onClose }) => {
  const [content, setContent] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (fileContent) {
      setContent(fileContent);
      setError(null);
    } else if ((filePath || fileName) && isOpen) {
      // 优先使用filePath，如果没有则使用fileName
      const pathToLoad = filePath || fileName;
      fetchFileContent(pathToLoad);
    }
  }, [fileContent, fileName, filePath, isOpen]);

  const fetchFileContent = async (filePath) => {
    setIsLoading(true);
    setError(null);
    
    if (!filePath) {
      setError('文件路径不能为空');
      setIsLoading(false);
      return;
    }
    
    // 清理文件路径，移除可能的 [FILE] 标记和后续文本
    let cleanedFilePath = String(filePath).trim();
    const originalPath = cleanedFilePath;
    
    // 移除 [FILE]\n 前缀（如果存在）
    if (cleanedFilePath.startsWith('[FILE]\n')) {
      cleanedFilePath = cleanedFilePath.substring(7).trim();
    }
    
    // 移除 [FILE] 后缀（如果存在）
    if (cleanedFilePath.endsWith('[FILE]')) {
      cleanedFilePath = cleanedFilePath.substring(0, cleanedFilePath.length - 6).trim();
    }
    
    // 移除换行符和其他空白字符
    cleanedFilePath = cleanedFilePath.replace(/[\n\r]/g, '').trim();
    
    // 定义文件扩展名模式
    const fileExtensions = ['txt', 'md', 'json', 'py', 'js', 'ts', 'tsx', 'jsx', 'css', 'html', 'xml', 'yaml', 'yml', 'log', 'ini', 'conf', 'sh', 'bat', 'cmd', 'ps1'];
    const extensionPattern = fileExtensions.join('|');
    
    // 策略1：直接查找文件扩展名的位置
    const extensionRegex = new RegExp(`\\.(${extensionPattern})(?=\\s|$|[✅❌⚠️\\*\\u4e00-\\u9fa5])`, 'i');
    const extensionMatch = cleanedFilePath.search(extensionRegex);
    
    if (extensionMatch > 0) {
      // 找到扩展名位置，计算扩展名的结束位置
      const extensionEndMatch = cleanedFilePath.substring(extensionMatch).match(new RegExp(`\\.(${extensionPattern})`, 'i'));
      if (extensionEndMatch) {
        // 扩展名结束位置 = 扩展名开始位置 + 扩展名长度（如 .json = 5）
        const extensionEnd = extensionMatch + extensionEndMatch[0].length;
        cleanedFilePath = cleanedFilePath.substring(0, extensionEnd).trim();
        console.log('🧹 FileSidebar：通过扩展名位置截取，结果:', cleanedFilePath);
      }
    } else {
      // 策略2：如果没有找到扩展名，尝试找到第一个特殊标记或中文字符之前
      const markerRegex = /[✅❌⚠️\*\*]|[\u4e00-\u9fa5]/;
      const markerIndex = cleanedFilePath.search(markerRegex);
      
      if (markerIndex > 0) {
        // 检查标记之前的内容是否包含文件扩展名
        const beforeMarker = cleanedFilePath.substring(0, markerIndex).trim();
        const hasExtension = beforeMarker.match(new RegExp(`\\.(${extensionPattern})$`, 'i'));
        
        if (hasExtension) {
          // 标记之前有文件扩展名，使用这部分
          cleanedFilePath = beforeMarker;
          console.log('🧹 FileSidebar：通过标记位置截取，结果:', cleanedFilePath);
        } else {
          // 标记之前没有扩展名，尝试在整个字符串中查找文件扩展名
          const allExtensionMatches = [...cleanedFilePath.matchAll(new RegExp(`\\.(${extensionPattern})`, 'gi'))];
          if (allExtensionMatches.length > 0) {
            // 使用最后一个匹配的扩展名位置
            const lastMatch = allExtensionMatches[allExtensionMatches.length - 1];
            const extensionEnd = lastMatch.index + lastMatch[0].length;
            cleanedFilePath = cleanedFilePath.substring(0, extensionEnd).trim();
            console.log('🧹 FileSidebar：通过查找所有扩展名，结果:', cleanedFilePath);
          }
        }
      } else {
        // 没有找到标记，检查是否以文件扩展名结尾
        const endsWithExtension = cleanedFilePath.match(new RegExp(`\\.(${extensionPattern})$`, 'i'));
        if (!endsWithExtension) {
          // 不以扩展名结尾，尝试查找文件扩展名
          const extensionMatch2 = cleanedFilePath.match(new RegExp(`([\\s\\S]+?\\.(${extensionPattern}))`, 'i'));
          if (extensionMatch2 && extensionMatch2[1]) {
            cleanedFilePath = extensionMatch2[1].trim();
            console.log('🧹 FileSidebar：通过正则匹配，结果:', cleanedFilePath);
          }
        }
      }
    }
    
    // 进一步清理：移除可能的Markdown标记和特殊字符
    cleanedFilePath = cleanedFilePath.replace(/\*\*|✅|❌|⚠️/g, '').trim();
    
    // 移除路径末尾可能的空格和特殊字符
    cleanedFilePath = cleanedFilePath.replace(/\s+[✅❌⚠️\*\*].*$/, '').trim();
    
    // 最终验证：确保路径以文件扩展名结尾
    const finalExtensionCheck = cleanedFilePath.match(new RegExp(`\\.(${extensionPattern})$`, 'i'));
    if (!finalExtensionCheck && cleanedFilePath.length > 0) {
      // 如果不以扩展名结尾，尝试找到最后一个扩展名
      const lastExtensionMatch = cleanedFilePath.match(new RegExp(`([\\s\\S]*\\.(${extensionPattern}))`, 'i'));
      if (lastExtensionMatch && lastExtensionMatch[1]) {
        cleanedFilePath = lastExtensionMatch[1].trim();
      }
    }
    
    console.log('🧹 FileSidebar清理文件路径，原始:', originalPath.substring(0, 150), '清理后:', cleanedFilePath);
    
    if (!cleanedFilePath) {
      setError('文件路径无效');
      setIsLoading(false);
      return;
    }
    
    try {
      // 将 [FILE] 作为单独的查询参数传递，而不是附加在文件路径上
      const url = `${API_BASE_URL}/get_local_file_content?file_path=${encodeURIComponent(cleanedFilePath)}&file_type=file`;
      console.log('📁 请求文件内容，URL:', url);
      console.log('📁 原始文件路径:', filePath);
      console.log('📁 清理后的文件路径:', cleanedFilePath);
      
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      console.log('📁 响应状态:', response.status, response.statusText);
      
      if (!response.ok) {
        throw new Error(`HTTP错误: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log('📁 响应数据:', data);
      
      if (data.success) {
        setContent(data.content);
        setError(null);
      } else {
        const errorMsg = data.error || data.message || '无法加载文件内容';
        setError(errorMsg);
        setContent('');
        console.error('❌ 加载文件内容失败:', errorMsg);
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '网络错误：无法加载文件内容';
      setError(errorMsg);
      setContent('');
      console.error('❌ 加载文件内容异常:', err);
      console.error('❌ 错误详情:', {
        message: err.message,
        stack: err.stack,
        name: err.name,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = () => {
    if (fileName && content) {
      const blob = new Blob([content], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName.split('/').pop() || 'file.txt';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      alert('内容已复制到剪贴板');
    } catch (err) {
      alert('复制失败，请手动复制');
    }
  };

  // 处理点击遮罩层关闭侧边栏
  const handleOverlayClick = (e) => {
    // 如果点击的是遮罩层本身（不是侧边栏内容），则关闭
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  // 处理ESC键关闭侧边栏
  useEffect(() => {
    const handleEscapeKey = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscapeKey);
      // 防止背景滚动
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscapeKey);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen && !fileName && !filePath) return null;

  // 获取显示的文件名
  const displayFileName = () => {
    if (filePath) return filePath.split('/').pop();
    if (fileName) return fileName.split('/').pop();
    return '文件预览';
  };

  return (
    <>
      {/* 遮罩层 - 点击外部区域关闭 */}
      {isOpen && (
        <div 
          className="file-sidebar-overlay"
          onClick={handleOverlayClick}
          aria-hidden="true"
        />
      )}
      <div 
        className={`file-sidebar ${isOpen ? 'open' : 'closed'}`}
        onClick={(e) => e.stopPropagation()}  // 阻止点击事件冒泡到遮罩层
      >
      <div className="file-sidebar-header">
        <div className="file-sidebar-title">
          <FileText size={16} />
          <span>{displayFileName()}</span>
        </div>
        <div className="file-sidebar-actions">
          {fileName && (
            <>
              <button onClick={handleCopy} className="sidebar-btn" title="复制内容">
                <Copy size={16} />
              </button>
              <button onClick={handleDownload} className="sidebar-btn" title="下载文件">
                <Download size={16} />
              </button>
            </>
          )}
          <button onClick={onClose} className="sidebar-btn" title="关闭">
            <X size={16} />
          </button>
        </div>
      </div>

      <div className="file-sidebar-content">
        {isLoading && (
          <div className="loading-placeholder">
            <div className="loading-spinner"></div>
            <p>正在加载文件内容...</p>
          </div>
        )}

        {error && (
          <div className="error-message">
            <p style={{ marginBottom: '8px', fontWeight: 'bold' }}>❌ 错误</p>
            <p style={{ marginBottom: '8px', wordBreak: 'break-word' }}>{error}</p>
            {filePath && (
              <p style={{ marginBottom: '8px', fontSize: '12px', color: '#666', wordBreak: 'break-all' }}>
                文件路径: {filePath}
              </p>
            )}
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
              <button 
                onClick={() => {
                  setError(null);
                  if (filePath || fileName) {
                    fetchFileContent(filePath || fileName);
                  }
                }} 
                className="retry-btn"
              >
                重试
              </button>
              <button 
                onClick={() => {
                  setError(null);
                  setContent('');
                }} 
                className="retry-btn"
                style={{ background: '#6b7280' }}
              >
                关闭
              </button>
            </div>
          </div>
        )}

        {!isLoading && !error && content && (
          <div className="file-content-container">
            <pre className="file-content">
              <code>{content}</code>
            </pre>
          </div>
        )}

        {!isLoading && !error && !content && (
          <div className="empty-state">
            <FileText size={48} />
            <p>选择一个文件查看内容</p>
          </div>
        )}
      </div>
    </div>
    </>
  );
};

export default FileSidebar;