import React from 'react';
import { User, Bot, FileText } from 'lucide-react';
import './Message.css';

const Message = ({ message, onFileClick }) => {
  const isUser = message.role === 'user';
  
  // 处理文件类型的chunk
  const renderContent = () => {
    if (message.chunks && Array.isArray(message.chunks)) {
      return message.chunks.map((chunk, index) => {
        if (chunk.type === 'file') {
          // 文件类型：显示可点击的文件名
          const fileName = chunk.content.split('/').pop() || chunk.content;
          return (
            <div key={index} className="file-chunk">
              <span 
                className="file-link" 
                onClick={() => onFileClick && onFileClick(chunk.content)}
                title={chunk.content}
              >
                <FileText size={16} />
                {fileName}
              </span>
            </div>
          );
        } else {
          // 文本类型：正常显示
          return (
            <div key={index} className="text-chunk" dangerouslySetInnerHTML={{ __html: formatText(chunk.content) }} />
          );
        }
      });
    }
    
    // 兼容旧格式：直接显示content
    return <div className="text-chunk" dangerouslySetInnerHTML={{ __html: formatText(message.content) }} />;
  };

  const formatText = (content) => {
    if (!content) return '';
    
    return content
      .replace(/\n/g, '<br />')
      .replace(/```([\s\S]*?)```/g, (match, code) => {
        return `<pre><code>${code.trim()}</code></pre>`;
      })
      .replace(/`([^`]+)`/g, '<code>$1</code>');
  };

  return (
    <div className={`message ${isUser ? 'user-message' : 'ai-message'}`}>
      <div className="message-avatar">
        {isUser ? <User size={20} /> : <Bot size={20} />}
      </div>
      <div className="message-content">
        <div className="message-text">
          {renderContent()}
        </div>
        <div className="message-time">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
};

export default Message;