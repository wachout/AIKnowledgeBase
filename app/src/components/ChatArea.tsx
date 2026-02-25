import React, { useState, useRef, useEffect } from 'react';
import { ChatMessage } from '../types';
import { chatStream } from '../services/api';
import { Send, Paperclip, Loader2, User, Bot, Sparkles, Zap } from 'lucide-react';
import RichContent from './RichContent';
import FileSidebar from './FileSidebar';

interface ChatAreaProps {
  sessionId: string;
  chatHistory: ChatMessage[];
  setChatHistory: (messages: ChatMessage[]) => void;
  knowledgeId?: string;
  knowledgeName?: string;
  databaseName?: string;
  sqlId?: string;
}

const ChatArea: React.FC<ChatAreaProps> = ({
  sessionId,
  chatHistory,
  setChatHistory,
  knowledgeId,
  knowledgeName,
  databaseName,
  sqlId,
}) => {
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [choice, setChoice] = useState<'ask' | 'discussion'>('ask');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // FileSidebar相关状态
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);

  const username = localStorage.getItem('user_name') || '';
  const password = localStorage.getItem('password') || '';

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory, streamingContent]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;

    // 构建消息内容：如果有文件，先显示文件名，然后换行显示用户要求
    let messageContent = input;
    if (selectedFile) {
      messageContent = `${selectedFile.name}\n${input}`;
    }

    const userMessage: ChatMessage = {
      role: 'user',
      content: messageContent,
    };

    setChatHistory([...chatHistory, userMessage]);
    setInput('');
    setIsStreaming(true);
    setStreamingContent('');

    try {
      let accumulatedContent = '';
      let chunks: Array<{type: string; content: string}> = [];
      let pendingFileContent = ''; // 用于处理分块接收的文件路径

      await chatStream(
        username,
        password,
        input,
        sessionId,
        knowledgeName,
        knowledgeId,
        sqlId,
        selectedFile || undefined, // 传递文件到 chatStream
        choice, // 传递choice参数
        (content) => {
          // 只有当 content 不为空时才更新
          if (content && content.trim()) {
            console.log('📥 收到chunk内容:', content.substring(0, 100));
            // 检查是否是文件类型标记
            if (content.startsWith('[FILE]\n')) {
              // 完整的文件标记，提取文件路径
              let filePath = content.substring(7).trim(); // 移除[FILE]\n前缀
              // 清理文件路径，确保不包含后续文本
              filePath = cleanFilePath(filePath);
              console.log('📁 检测到文件路径，原始:', content.substring(7), '清理后:', filePath);
              if (filePath) {
                // 检查是否已经添加过这个文件（使用清理后的路径比较）
                const existingFile = chunks.find(c => c.type === 'file' && cleanFilePath(c.content) === filePath);
                if (!existingFile) {
                  chunks.push({ type: 'file', content: filePath });
                  console.log('✅ 添加文件chunk:', filePath);
                } else {
                  console.log('⚠️ 文件已存在，跳过:', filePath);
                }
                accumulatedContent += content;
                pendingFileContent = ''; // 重置待处理的文件内容
              } else {
                // 文件路径为空，可能是分块接收的开始
                pendingFileContent = '[FILE]\n';
                accumulatedContent += content;
              }
            } else if (pendingFileContent) {
              // 正在接收文件路径的后续部分
              pendingFileContent += content;
              accumulatedContent += content;
              
              // 检查是否接收到了完整的文件路径（以换行符或文件扩展名结尾）
              const fileMatch = pendingFileContent.match(/\[FILE\]\n([^\n]+)/);
              if (fileMatch && fileMatch[1].trim()) {
                let filePath = fileMatch[1].trim();
                // 清理文件路径
                filePath = cleanFilePath(filePath);
                // 检查文件路径是否完整（包含扩展名或看起来完整）
                if (filePath && (filePath.includes('.') || filePath.length > 50)) {
                  // 检查是否已经添加过这个文件（使用清理后的路径比较）
                  const existingFile = chunks.find(c => c.type === 'file' && cleanFilePath(c.content) === filePath);
                  if (!existingFile) {
                    chunks.push({ type: 'file', content: filePath });
                  }
                  pendingFileContent = ''; // 重置
                }
              }
            } else {
              // 检查是否包含文件标记（可能在累积内容中）
              const fileMatch = content.match(/\[FILE\]\n([^\n]+)/);
              if (fileMatch) {
                let filePath = fileMatch[1].trim();
                // 清理文件路径
                filePath = cleanFilePath(filePath);
                if (filePath) {
                  // 检查是否已经添加过这个文件（使用清理后的路径比较）
                  const existingFile = chunks.find(c => c.type === 'file' && cleanFilePath(c.content) === filePath);
                  if (!existingFile) {
                    chunks.push({ type: 'file', content: filePath });
                  }
                }
              }
              accumulatedContent += content;
            }
            setStreamingContent(accumulatedContent);
          }
          // 如果 content 为空，不更新 streamingContent，保持"正在思考中"状态
        },
        () => {
          // 构建最终的消息内容
          let finalContent: string | Array<{type: string; content: string}>;
          
          // 如果有chunks数组（包含file类型），使用数组格式
          if (chunks.length > 0) {
            // 去重文件chunk（保留第一次出现的）
            const uniqueFileChunks: Array<{type: string; content: string}> = [];
            const seenFiles = new Set<string>();
            for (const chunk of chunks) {
              if (chunk.type === 'file') {
                if (!seenFiles.has(chunk.content)) {
                  seenFiles.add(chunk.content);
                  uniqueFileChunks.push(chunk);
                }
              } else {
                uniqueFileChunks.push(chunk);
              }
            }
            
            // 解析累积内容，分离文本和文件
            const finalChunks: Array<{type: string; content: string}> = [];
            let remainingText = accumulatedContent;
            
            // 按顺序处理每个文件
            for (const fileChunk of uniqueFileChunks.filter(c => c.type === 'file')) {
              // 清理文件路径，确保不包含后续文本
              const cleanedFilePath = cleanFilePath(fileChunk.content);
              const fileMarker = `[FILE]\n${fileChunk.content}`;
              const fileIndex = remainingText.indexOf(fileMarker);
              
              if (fileIndex >= 0) {
                // 添加文件前的文本
                if (fileIndex > 0) {
                  const beforeText = remainingText.substring(0, fileIndex).trim();
                  if (beforeText) {
                    finalChunks.push({ type: 'text', content: beforeText });
                  }
                }
                // 添加文件chunk（使用清理后的文件路径）
                finalChunks.push({ type: 'file', content: cleanedFilePath });
                // 更新剩余文本
                remainingText = remainingText.substring(fileIndex + fileMarker.length);
              } else {
                // 如果找不到完整的标记，尝试使用清理后的路径
                // 添加文件chunk（使用清理后的文件路径）
                finalChunks.push({ type: 'file', content: cleanedFilePath });
              }
            }
            
            // 添加剩余的文本（移除所有文件标记）
            const cleanedRemainingText = remainingText.replace(/\[FILE\]\n[^\n]+/g, '').trim();
            if (cleanedRemainingText) {
              finalChunks.push({ type: 'text', content: cleanedRemainingText });
            }
            
            // 如果没有文本chunk，但累积内容中有文本（除了文件标记），添加文本chunk
            const hasTextChunk = finalChunks.some(c => c.type === 'text');
            if (!hasTextChunk) {
              const textOnly = accumulatedContent.replace(/\[FILE\]\n[^\n]+/g, '').trim();
              if (textOnly) {
                finalChunks.unshift({ type: 'text', content: textOnly });
              }
            }
            
            finalContent = finalChunks.length > 0 ? finalChunks : accumulatedContent;
          } else {
            finalContent = accumulatedContent;
          }
          
          const assistantMessage: ChatMessage = {
            role: 'assistant',
            content: finalContent,
          };
          setChatHistory([...chatHistory, userMessage, assistantMessage]);
          setStreamingContent('');
          setIsStreaming(false);
          
          // 重置文件状态
          setSelectedFile(null);
          if (fileInputRef.current) {
            fileInputRef.current.value = '';
          }
        },
        (error) => {
          console.error('聊天失败，详细错误信息:', {
            error,
            message: error instanceof Error ? error.message : 'Unknown error',
            name: error instanceof Error ? error.name : 'Unknown',
            stack: error instanceof Error ? error.stack : undefined
          });
          
          let errorContent = '抱歉，发生了错误，请稍后再试。';
          
          // 根据错误类型提供更具体的建议
          if (error instanceof Error) {
            if (error.message.includes('网络连接失败')) {
              errorContent = '⚠️ 网络连接错误，请检查：\n1) 后端服务是否启动（http://127.0.0.1:6199）\n2) CORS配置是否正确\n3) 防火墙或网络设置';
            } else if (error.message.includes('HTTP')) {
              errorContent = `⚠️ 服务器错误: ${error.message}`;
            } else if (error.message.includes('CORS')) {
              errorContent = '⚠️ 跨域请求被阻止，请检查后端的CORS配置';
            } else if (error.message.includes('fetch')) {
              errorContent = '⚠️ 无法连接到服务器，请确认后端服务已启动并监听正确端口';
            } else {
              errorContent = `⚠️ 错误: ${error.message}`;
            }
          }
          
          const errorMessage: ChatMessage = {
            role: 'assistant',
            content: errorContent,
          };
          setChatHistory([...chatHistory, userMessage, errorMessage]);
          setStreamingContent('');
          setIsStreaming(false);
          
          // 重置文件状态
          setSelectedFile(null);
          if (fileInputRef.current) {
            fileInputRef.current.value = '';
          }
        }
      );
    } catch (err) {
      console.error('发送消息失败', err);
      setIsStreaming(false);
      setStreamingContent('');
      
      // 重置文件状态
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 清理文件路径，移除可能的 [FILE] 标记和后续文本
  const cleanFilePath = (filePath: string): string => {
    if (!filePath) return '';
    
    let cleaned = String(filePath).trim();
    const originalPath = cleaned;
    
    // 移除 [FILE]\n 前缀（如果存在）
    if (cleaned.startsWith('[FILE]\n')) {
      cleaned = cleaned.substring(7).trim();
    }
    
    // 移除 [FILE] 后缀（如果存在）
    if (cleaned.endsWith('[FILE]')) {
      cleaned = cleaned.substring(0, cleaned.length - 6).trim();
    }
    
    // 移除换行符和其他空白字符
    cleaned = cleaned.replace(/[\n\r]/g, '').trim();
    
    // 定义文件扩展名模式
    const fileExtensions = ['txt', 'md', 'json', 'py', 'js', 'ts', 'tsx', 'jsx', 'css', 'html', 'xml', 'yaml', 'yml', 'log', 'ini', 'conf', 'sh', 'bat', 'cmd', 'ps1'];
    const extensionPattern = fileExtensions.join('|');
    
    // 策略1：直接查找文件扩展名的位置
    // 文件路径应该以文件扩展名结尾，如果后面有文本，需要截取
    const extensionRegex = new RegExp(`\\.(${extensionPattern})(?=\\s|$|[✅❌⚠️\\*\\u4e00-\\u9fa5])`, 'i');
    const extensionMatch = cleaned.search(extensionRegex);
    
    if (extensionMatch > 0) {
      // 找到扩展名位置，计算扩展名的结束位置
      const extensionEndMatch = cleaned.substring(extensionMatch).match(new RegExp(`\\.(${extensionPattern})`, 'i'));
      if (extensionEndMatch) {
        // 扩展名结束位置 = 扩展名开始位置 + 扩展名长度（如 .json = 5）
        const extensionEnd = extensionMatch + extensionEndMatch[0].length;
        cleaned = cleaned.substring(0, extensionEnd).trim();
        console.log('🧹 方法1：通过扩展名位置截取，结果:', cleaned);
      }
    } else {
      // 策略2：如果没有找到扩展名，尝试找到第一个特殊标记或中文字符之前
      // 但需要确保包含文件扩展名
      const markerRegex = /[✅❌⚠️\*\*]|[\u4e00-\u9fa5]/;
      const markerIndex = cleaned.search(markerRegex);
      
      if (markerIndex > 0) {
        // 检查标记之前的内容是否包含文件扩展名
        const beforeMarker = cleaned.substring(0, markerIndex).trim();
        const hasExtension = beforeMarker.match(new RegExp(`\\.(${extensionPattern})$`, 'i'));
        
        if (hasExtension) {
          // 标记之前有文件扩展名，使用这部分
          cleaned = beforeMarker;
          console.log('🧹 方法2：通过标记位置截取，结果:', cleaned);
        } else {
          // 标记之前没有扩展名，尝试在整个字符串中查找文件扩展名
          const allExtensionMatches = [...cleaned.matchAll(new RegExp(`\\.(${extensionPattern})`, 'gi'))];
          if (allExtensionMatches.length > 0) {
            // 使用最后一个匹配的扩展名位置
            const lastMatch = allExtensionMatches[allExtensionMatches.length - 1];
            const extensionEnd = lastMatch.index! + lastMatch[0].length;
            cleaned = cleaned.substring(0, extensionEnd).trim();
            console.log('🧹 方法3：通过查找所有扩展名，结果:', cleaned);
          }
        }
      } else {
        // 没有找到标记，检查是否以文件扩展名结尾
        const endsWithExtension = cleaned.match(new RegExp(`\\.(${extensionPattern})$`, 'i'));
        if (!endsWithExtension) {
          // 不以扩展名结尾，尝试查找文件扩展名
          const extensionMatch2 = cleaned.match(new RegExp(`([\\s\\S]+?\\.(${extensionPattern}))`, 'i'));
          if (extensionMatch2 && extensionMatch2[1]) {
            cleaned = extensionMatch2[1].trim();
            console.log('🧹 方法4：通过正则匹配，结果:', cleaned);
          }
        }
      }
    }
    
    // 进一步清理：移除可能的Markdown标记和特殊字符
    // 文件路径不应该包含 **、✅、❌ 等标记
    cleaned = cleaned.replace(/\*\*|✅|❌|⚠️/g, '').trim();
    
    // 移除路径末尾可能的空格和特殊字符
    cleaned = cleaned.replace(/\s+[✅❌⚠️\*\*].*$/, '').trim();
    
    // 最终验证：确保路径以文件扩展名结尾
    const finalExtensionCheck = cleaned.match(new RegExp(`\\.(${extensionPattern})$`, 'i'));
    if (!finalExtensionCheck && cleaned.length > 0) {
      // 如果不以扩展名结尾，尝试找到最后一个扩展名
      const lastExtensionMatch = cleaned.match(new RegExp(`([\\s\\S]*\\.(${extensionPattern}))`, 'i'));
      if (lastExtensionMatch && lastExtensionMatch[1]) {
        cleaned = lastExtensionMatch[1].trim();
      }
    }
    
    console.log('🧹 清理文件路径，原始:', originalPath.substring(0, 150), '清理后:', cleaned);
    
    return cleaned;
  };

  // 处理文件点击事件
  const handleFileClick = (filePath: string) => {
    // 清理文件路径，确保不包含 [FILE] 标记
    const cleanedPath = cleanFilePath(filePath);
    if (cleanedPath) {
      setSelectedFilePath(cleanedPath);
      setIsSidebarOpen(true);
    } else {
      console.error('❌ 文件路径无效:', filePath);
    }
  };

  // 关闭侧边栏
  const handleCloseSidebar = () => {
    setIsSidebarOpen(false);
    setSelectedFilePath(null);
  };

  // 切换侧边栏
  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  // 渲染流式内容，包括文件链接
  const renderStreamingContent = (content: string) => {
    console.log('🎨 渲染流式内容，长度:', content.length, '内容预览:', content.substring(0, 200));
    // 检查是否包含文件标记
    // 匹配 [FILE]\n 后面直到换行符或字符串结束的内容
    // 使用非贪婪匹配，匹配 [FILE]\n 后面的内容
    // 允许文件路径后面有文本（会在cleanFilePath中清理）
    // 匹配到换行符、字符串结束或特殊标记之前
    const fileRegex = /\[FILE\]\n([^\n\r]*?)(?:\n|$|(?=[✅❌⚠️\*\*]))/g;
    const parts: Array<{type: 'text' | 'file'; content: string}> = [];
    let lastIndex = 0;
    let match;
    const matches: Array<{index: number; length: number; filePath: string; originalLength: number}> = [];

    // 收集所有匹配的文件标记
    while ((match = fileRegex.exec(content)) !== null) {
      let filePath = match[1] ? match[1].trim() : '';
      const originalPath = filePath;
      console.log('📁 正则匹配到文件路径，原始:', originalPath);
      // 使用cleanFilePath函数清理文件路径，确保不包含后续文本
      filePath = cleanFilePath(filePath);
      if (filePath) {
        console.log('📁 找到文件标记，原始路径:', originalPath, '清理后路径:', filePath);
        // 计算原始匹配的长度（包括[FILE]\n和原始文件路径）
        const originalLength = match[0].length;
        matches.push({
          index: match.index!,
          length: originalLength, // 使用原始长度，确保正确跳过后续文本
          filePath: filePath,
          originalLength: originalLength
        });
      } else {
        console.warn('⚠️ 文件路径清理后为空，原始路径:', originalPath);
      }
    }

    // 按顺序处理每个文件标记
    for (const fileMatch of matches) {
      // 添加文件前的文本
      if (fileMatch.index > lastIndex) {
        const textPart = content.substring(lastIndex, fileMatch.index).trim();
        if (textPart) {
          parts.push({ type: 'text', content: textPart });
        }
      }
      // 添加文件
      if (fileMatch.filePath) {
        parts.push({ type: 'file', content: fileMatch.filePath });
      }
      lastIndex = fileMatch.index + fileMatch.length;
    }

    // 添加剩余的文本（移除所有文件标记）
    if (lastIndex < content.length) {
      let remainingText = content.substring(lastIndex);
      // 移除剩余文本中可能存在的文件标记
      remainingText = remainingText.replace(/\[FILE\]\n[^\n\r]+/g, '').trim();
      if (remainingText) {
        parts.push({ type: 'text', content: remainingText });
      }
    }

    // 如果没有匹配到文件，检查是否整个内容都是文件标记
    if (parts.length === 0) {
      const fullFileMatch = content.match(/^\[FILE\]\n(.+)$/s);
      if (fullFileMatch && fullFileMatch[1].trim()) {
        const filePath = fullFileMatch[1].trim();
        return (
          <div className="mb-2">
            <span 
              className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-500 text-white rounded-lg cursor-pointer hover:bg-blue-600 transition-colors text-sm font-medium"
              onClick={() => handleFileClick(filePath)}
              title={filePath}
            >
              <Paperclip className="w-4 h-4" />
              {filePath.split('/').pop() || filePath}
            </span>
          </div>
        );
      }
      return <RichContent content={content} className="text-sm" />;
    }

    // 渲染parts
    return (
      <>
        {parts.map((part, index) => {
          if (part.type === 'file') {
            const fileName = part.content.split('/').pop() || part.content;
            return (
              <div key={index} className="mb-2">
                <span 
                  className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-500 text-white rounded-lg cursor-pointer hover:bg-blue-600 transition-colors text-sm font-medium"
                  onClick={() => handleFileClick(part.content)}
                  title={part.content}
                >
                  <Paperclip className="w-4 h-4" />
                  {fileName}
                </span>
              </div>
            );
          } else {
            return (
              <div key={index}>
                <RichContent content={part.content} className="text-sm" />
              </div>
            );
          }
        })}
      </>
    );
  };

  return (
    <div className="flex-1 flex flex-col bg-cyber-bg h-full relative">
      {/* 聊天消息区域 - 固定高度，可滚动 */}
      <div 
        className={`flex-1 overflow-y-auto p-6 space-y-4 cyber-scrollbar transition-all cyber-grid-bg ${isSidebarOpen ? 'pr-80' : ''}`}
        style={{ maxHeight: 'calc(100vh - 200px)' }}
      >
        {chatHistory.length === 0 && !streamingContent && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 bg-cyber-surface rounded-xl flex items-center justify-center cyber-float">
                <Sparkles className="w-8 h-8 text-cyber-accent" />
              </div>
              <p className="text-cyber-text-muted">开始新的对话吧</p>
            </div>
          </div>
        )}

        {chatHistory.map((message, index) => {
          // 处理消息内容，分离file类型和text类型的chunk
          const renderMessageContent = () => {
            if (Array.isArray(message.content)) {
              // 如果是数组格式，分别处理每个chunk
              return message.content.map((chunk, chunkIndex) => {
                if (chunk.type === 'file') {
                  // file类型：显示可点击的文件名
                  const fileName = chunk.content.split('/').pop() || chunk.content;
                  return (
                    <div key={chunkIndex} className="mb-2">
                      <span 
                        className="inline-flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-cyber-accent to-cyber-accent-purple text-white rounded-lg cursor-pointer hover:shadow-cyber-glow transition-all text-sm font-medium"
                        onClick={() => handleFileClick(chunk.content)}
                        title={chunk.content}
                      >
                        <Paperclip className="w-4 h-4" />
                        {fileName}
                      </span>
                    </div>
                  );
                } else {
                  // text类型：正常显示
                  return (
                    <div key={chunkIndex}>
                      <RichContent 
                        content={chunk.content} 
                        className="text-sm"
                      />
                    </div>
                  );
                }
              });
            } else {
              // 字符串格式：直接显示
              return <RichContent content={message.content} className="text-sm" />;
            }
          };

          return (
            <div
              key={index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} mb-4`}
            >
              {message.role === 'user' ? (
                <div className="flex items-end gap-3">
                  <div className="max-w-[66.67%] rounded-2xl px-4 py-3 bg-gradient-to-r from-cyber-accent to-cyber-accent-purple text-white shadow-cyber-glow" style={{ wordBreak: 'break-word', overflowWrap: 'break-word' }}>
                    {renderMessageContent()}
                  </div>
                  <div className="w-9 h-9 bg-gradient-to-r from-cyber-accent to-cyber-accent-purple rounded-xl flex items-center justify-center text-white flex-shrink-0 shadow-cyber-glow">
                    <User className="w-5 h-5" />
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 bg-cyber-surface-light border border-cyber-border rounded-xl flex items-center justify-center text-cyber-accent flex-shrink-0">
                    <Bot className="w-5 h-5" />
                  </div>
                  <div className="max-w-[66.67%] rounded-2xl px-4 py-3 bg-cyber-surface border border-cyber-border text-cyber-text" style={{ wordBreak: 'break-word', overflowWrap: 'break-word' }}>
                    {renderMessageContent()}
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {/* 流式消息 - 思考中状态 */}
        {isStreaming && !streamingContent && (
          <div className="flex justify-start mb-4">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 bg-cyber-surface-light border border-cyber-border rounded-xl flex items-center justify-center text-cyber-accent">
                <Bot className="w-5 h-5" />
              </div>
              <div className="max-w-[66.67%] rounded-2xl px-4 py-3 bg-cyber-surface border border-cyber-accent/30 text-cyber-text flex items-center gap-3 shadow-cyber-glow">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-cyber-accent rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-cyber-accent rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-cyber-accent rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-sm text-cyber-accent">正在思考中...</span>
              </div>
            </div>
          </div>
        )}

        {/* 流式消息 - 内容显示 */}
        {isStreaming && streamingContent && (
          <div className="flex justify-start mb-4">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 bg-cyber-surface-light border border-cyber-border rounded-xl flex items-center justify-center text-cyber-accent flex-shrink-0">
                <Bot className="w-5 h-5" />
              </div>
              <div className="max-w-[66.67%] rounded-2xl px-4 py-3 bg-cyber-surface border border-cyber-border text-cyber-text" style={{ wordBreak: 'break-word', overflowWrap: 'break-word' }}>
                {renderStreamingContent(streamingContent)}
                <div className="flex items-center gap-2 mt-2 pt-2 border-t border-cyber-border/50">
                  <Zap className="w-3 h-3 text-cyber-accent animate-pulse" />
                  <span className="text-xs text-cyber-accent">正在生成...</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 文件选择提示 */}
      {selectedFile && !isStreaming && (
        <div className="px-6 py-3 bg-cyber-accent/10 border-t border-cyber-accent/30">
          <p className="text-sm text-cyber-text">
            已选择文件: <span className="font-medium text-cyber-accent">{selectedFile.name}</span>
            <button
              onClick={() => {
                setSelectedFile(null);
                if (fileInputRef.current) {
                  fileInputRef.current.value = '';
                }
              }}
              className="ml-2 text-xs text-red-400 hover:text-red-300 underline transition-colors"
            >
              移除
            </button>
          </p>
          <p className="text-xs text-cyber-text-muted mt-1">请在下方输入框中输入您的要求，然后点击发送按钮</p>
        </div>
      )}

      {/* 输入区域 */}
      <div className="border-t border-cyber-border p-6 bg-cyber-surface">
        {knowledgeName && (
          <div className="mb-3 text-sm text-cyber-text-muted flex items-center gap-2">
            <span className="w-2 h-2 bg-cyber-accent-green rounded-full" />
            当前使用知识库: <span className="font-medium text-cyber-accent-green">{knowledgeName}</span>
          </div>
        )}
        {databaseName && (
          <div className="mb-3 text-sm text-cyber-text-muted flex items-center gap-2">
            <span className="w-2 h-2 bg-cyber-accent-purple rounded-full" />
            当前使用数据库: <span className="font-medium text-cyber-accent-purple">{databaseName}</span>
          </div>
        )}

        <div className="flex items-end gap-3">
          {/* 文件上传区域 - 垂直布局 */}
          <div className="flex flex-col gap-2">
            {/* 小型下拉框 */}
            <select
              value={choice}
              onChange={(e) => setChoice(e.target.value as 'ask' | 'discussion')}
              className="px-2 py-1 text-xs border border-cyber-border bg-cyber-surface-light text-cyber-text rounded-lg focus:ring-1 focus:ring-cyber-accent focus:border-cyber-accent outline-none transition-all"
              title="对话模式"
            >
              <option value="ask">ask</option>
              <option value="discussion">discussion</option>
            </select>

            {/* 上传文件按钮 */}
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleFileSelect}
              className="hidden"
            />

            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-3 text-cyber-text-muted hover:text-cyber-accent hover:bg-cyber-surface-light rounded-lg transition-all"
              title="上传文件"
            >
              <Paperclip className="w-5 h-5" />
            </button>
          </div>

          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="输入消息... (按 Enter 发送，Shift+Enter 换行)"
              className="cyber-input w-full resize-none"
              rows={3}
              disabled={isStreaming}
            />
          </div>

          <button
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
            className="p-3 bg-gradient-to-r from-cyber-accent to-cyber-accent-purple text-white rounded-lg hover:shadow-cyber-glow transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-none"
            title={selectedFile ? "发送消息（包含文件）" : "发送消息"}
          >
            {isStreaming ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>

      {/* FileSidebar组件 */}
      <FileSidebar
        isOpen={isSidebarOpen}
        onToggle={toggleSidebar}
        onClose={handleCloseSidebar}
        filePath={selectedFilePath}
        fileName={selectedFilePath ? selectedFilePath.split('/').pop() || null : null}
      />
    </div>
  );
};

export default ChatArea;

