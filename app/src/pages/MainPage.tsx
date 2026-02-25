import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { SessionMessage, ChatMessage, Knowledge, Database } from '../types';
import { getSessionMessages, getSessionById, deleteSession, createSession, getKnowledgeBase, getKnowledgeBaseFileList, deleteFile, addFile, getSqlInfoList } from '../services/api';
import ChatArea from '../components/ChatArea';
import DatabaseAddModal from '../components/DatabaseAddModal';
import DatabaseDetailModal from '../components/DatabaseDetailModal';
import KnowledgeBaseAddModal from '../components/KnowledgeBaseAddModal';
import KnowledgeBaseDeleteModal from '../components/KnowledgeBaseDeleteModal';
import { LogOut, Plus, Trash2, Upload, File, Database as DatabaseIcon, MessageSquare, BookOpen, HardDrive, Sparkles } from 'lucide-react';

const MainPage: React.FC = () => {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<SessionMessage[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<Knowledge[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [selectedKnowledge, setSelectedKnowledge] = useState<Knowledge | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingKnowledge, setLoadingKnowledge] = useState(true);
  const [newSessionName, setNewSessionName] = useState('');
  const [showNewSessionInput, setShowNewSessionInput] = useState(false);
  const [fileList, setFileList] = useState<Array<{
    file_id: string;
    file_name: string;
    file_path: string;
    file_size: string;
    upload_time: string;
    upload_user_id: string;
    permission_level: string;
    url: string;
  }>>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [selectedPermission, setSelectedPermission] = useState<'public' | 'private'>('public');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 数据库相关状态
  const [databases, setDatabases] = useState<Database[]>([]);
  const [selectedDatabase, setSelectedDatabase] = useState<Database | null>(null);
  const [loadingDatabases, setLoadingDatabases] = useState(false);
  const [showDatabaseAddModal, setShowDatabaseAddModal] = useState(false);
  const [showDatabaseDetailModal, setShowDatabaseDetailModal] = useState(false);
  const [contextMenuDatabase, setContextMenuDatabase] = useState<Database | null>(null);
  const [showKnowledgeBaseAddModal, setShowKnowledgeBaseAddModal] = useState(false);
  const [showKnowledgeBaseDeleteModal, setShowKnowledgeBaseDeleteModal] = useState(false);
  const [contextMenuKnowledgeBase, setContextMenuKnowledgeBase] = useState<Knowledge | null>(null);

  // 使用 useRef 来防止重复加载数据
  const dataLoadedRef = useRef(false);

  const username = localStorage.getItem('user_name') || '';
  const password = localStorage.getItem('password') || '';
  const userId = localStorage.getItem('user_id') || '';

  useEffect(() => {
    if (!username || !password) {
      navigate('/');
      return;
    }

    // 只有在数据还没有加载过的情况下才加载
    if (!dataLoadedRef.current) {
      dataLoadedRef.current = true;
      console.log('MainPage: 加载初始数据');
      loadSessions();
      loadKnowledgeBases();
      loadDatabases();
    }
  }, [username, password, navigate]);

  // 组件卸载时重置加载标志，这样如果用户重新登录可以重新加载
  useEffect(() => {
    return () => {
      dataLoadedRef.current = false;
    };
  }, []);

  const loadSessions = async () => {
    try {
      setLoading(true);
      const result = await getSessionMessages(username, password, userId);
      if (result.success && result.messages) {
        setSessions(result.messages);
        console.log('会话列表刷新成功，共', result.messages.length, '个会话');
      } else {
        console.error('获取会话列表失败:', result.message);
      }
    } catch (err) {
      console.error('加载会话列表失败', err);
    } finally {
      setLoading(false);
    }
  };

  const loadKnowledgeBases = async () => {
    try {
      setLoadingKnowledge(true);
      const result = await getKnowledgeBase(username, password);
      if (result.success) {
        // 处理返回的知识库数据，可能是单个对象或数组
        let knowledgeList: Knowledge[] = [];
        if (result.knowledge_base) {
          if (Array.isArray(result.knowledge_base)) {
            knowledgeList = result.knowledge_base.map((kb: any) => ({
              knowledge_id: kb.knowledge_id,
              knowledge_name: kb.name || kb.knowledge_name,
              name: kb.name,
              description: kb.description,
              create_time: kb.create_time,
              valid_start_time: kb.valid_start_time,
              valid_end_time: kb.valid_end_time,
              create_user_id: kb.create_user_id,
              file_num: kb.file_num,
            }));
          } else {
            // 单个知识库对象
            knowledgeList = [{
              knowledge_id: result.knowledge_base.knowledge_id,
              knowledge_name: result.knowledge_base.name || result.knowledge_base.knowledge_name,
              name: result.knowledge_base.name,
              description: result.knowledge_base.description,
              create_time: result.knowledge_base.create_time,
              valid_start_time: result.knowledge_base.valid_start_time,
              valid_end_time: result.knowledge_base.valid_end_time,
              create_user_id: result.knowledge_base.create_user_id,
              file_num: result.knowledge_base.file_num,
            }];
          }
        }

        // 按知识库id去重，只保留每个knowledge_id的第一个记录
        const uniqueKnowledgeBases = knowledgeList.reduce((acc: Knowledge[], current) => {
          const existingIndex = acc.findIndex(kb => kb.knowledge_id === current.knowledge_id);
          if (existingIndex === -1) {
            // 如果还没有这个knowledge_id，添加它
            acc.push(current);
          } else {
            // 如果已经存在，保留第一个（或者可以根据需要选择最新的）
            console.log(`发现重复的知识库ID: ${current.knowledge_id}, 保留第一个记录`);
          }
          return acc;
        }, []);

        console.log(`知识库去重: 原始数量 ${knowledgeList.length}, 去重后数量 ${uniqueKnowledgeBases.length}`);
        setKnowledgeBases(uniqueKnowledgeBases);
      } else {
        console.error('获取知识库失败:', result.message);
      }
    } catch (err) {
      console.error('加载知识库列表失败', err);
    } finally {
      setLoadingKnowledge(false);
    }
  };

  const loadDatabases = async () => {
    try {
      setLoadingDatabases(true);
      const result = await getSqlInfoList(username, password, userId);
      if (result.success && result.data) {
        setDatabases(result.data);
      } else {
        console.error('获取数据库列表失败:', result.message);
      }
    } catch (err) {
      console.error('加载数据库列表失败', err);
    } finally {
      setLoadingDatabases(false);
    }
  };

  const handleDatabaseDoubleClick = (database: Database) => {
    setSelectedDatabase(database);
  };

  const handleDatabaseRightClick = (e: React.MouseEvent, database: Database) => {
    e.preventDefault();
    setContextMenuDatabase(database);
    setShowDatabaseDetailModal(true);
  };

  const handleDatabaseAddSuccess = () => {
    loadDatabases();
  };

  const handleKnowledgeBaseAddSuccess = () => {
    loadKnowledgeBases();
  };

  const handleKnowledgeBaseDeleteSuccess = () => {
    loadKnowledgeBases();
    // 如果删除的是当前选中的知识库，清除选中状态
    if (contextMenuKnowledgeBase && selectedKnowledge?.knowledge_id === contextMenuKnowledgeBase.knowledge_id) {
      setSelectedKnowledge(null);
      setFileList([]);
    }
  };

  const handleSessionDoubleClick = async (sessionId: string) => {
    try {
      const result = await getSessionById(sessionId);
      console.log('📥 获取会话详情返回结果:', result);
      if (result.success && result.messages && Array.isArray(result.messages) && result.messages.length > 0) {
        const sessionData = result.messages[0] as any;
        console.log('📥 使用 messages 格式，消息数量:', sessionData.messages?.length || 0);
        setSelectedSession(sessionId);
        setChatHistory(sessionData.messages || []);
      } else if (result.success && result.session) {
        // 兼容另一种返回格式
        const sessionData = result.session as any;
        console.log('📥 使用 session 格式，消息数量:', sessionData.messages?.length || 0);
        console.log('📥 消息内容示例:', sessionData.messages?.[0]);
        setSelectedSession(sessionId);
        setChatHistory(sessionData.messages || []);
      } else {
        // 即使没有历史消息，也要设置选中状态，允许开始新对话
        console.log('⚠️ 没有找到历史消息');
        setSelectedSession(sessionId);
        setChatHistory([]);
      }
    } catch (err) {
      console.error('加载会话详情失败', err);
    }
  };

  const handleSessionRightClick = (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault();
    const confirmDelete = window.confirm('确定要删除此会话吗？');
    if (confirmDelete) {
      handleDeleteSession(sessionId);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      const result = await deleteSession(sessionId);
      if (result.success) {
        setSessions(sessions.filter(s => s.session_id !== sessionId));
        if (selectedSession === sessionId) {
          setSelectedSession(null);
          setChatHistory([]);
        }
        alert('会话删除成功');
      } else {
        alert(result.message || '删除会话失败');
      }
    } catch (err) {
      console.error('删除会话失败', err);
      alert('删除会话失败');
    }
  };

  const handleKnowledgeDoubleClick = async (knowledge: Knowledge) => {
    setSelectedKnowledge(knowledge);
    // 加载知识库文件列表
    await loadFileList(knowledge.knowledge_id);
  };

  const handleKnowledgeRightClick = (e: React.MouseEvent, knowledge: Knowledge) => {
    e.preventDefault();
    setContextMenuKnowledgeBase(knowledge);
    setShowKnowledgeBaseDeleteModal(true);
  };

  const loadFileList = async (knowledgeId: string) => {
    try {
      setLoadingFiles(true);
      const result = await getKnowledgeBaseFileList(knowledgeId);
      if (result.success && result.file_list) {
        setFileList(result.file_list);
      } else {
        console.error('获取文件列表失败:', result.message);
        setFileList([]);
      }
    } catch (err) {
      console.error('加载文件列表失败', err);
      setFileList([]);
    } finally {
      setLoadingFiles(false);
    }
  };

  const handleFileRightClick = async (e: React.MouseEvent, fileId: string, fileName: string) => {
    e.preventDefault();
    const confirmDelete = window.confirm(`确定要删除文件 "${fileName}" 吗？`);
    if (confirmDelete) {
      try {
        const result = await deleteFile(username, password, fileId);
        if (result.success) {
          alert('文件删除成功');
          // 重新加载文件列表
          if (selectedKnowledge) {
            await loadFileList(selectedKnowledge.knowledge_id);
          }
        } else {
          alert(result.message || '删除文件失败');
        }
      } catch (err) {
        console.error('删除文件失败', err);
        alert('删除文件失败');
      }
    }
  };

  const handleFileUploadClick = () => {
    setShowFileUpload(true);
    fileInputRef.current?.click();
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!selectedKnowledge) {
      alert('请先选择知识库');
      return;
    }

    try {
      // 传递选中的知识库ID或名称到上传接口
      const result = await addFile(
        username, 
        password, 
        file, 
        selectedPermission,
        selectedKnowledge.knowledge_id,
        selectedKnowledge.knowledge_name
      );
      if (result.success) {
        alert('文件上传成功');
        // 重新加载文件列表
        await loadFileList(selectedKnowledge.knowledge_id);
      } else {
        alert(result.message || '文件上传失败');
      }
    } catch (err) {
      console.error('文件上传失败', err);
      alert('文件上传失败');
    } finally {
      setShowFileUpload(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };



  const handleCreateSession = async () => {
    if (!newSessionName.trim()) {
      alert('请输入会话名称');
      return;
    }

    const sessionNameToCreate = newSessionName.trim();
    
    try {
      const result = await createSession(
        username,
        password,
        sessionNameToCreate,
        selectedKnowledge?.knowledge_name,
        selectedKnowledge?.knowledge_id,
        userId
      );

      console.log('创建会话API响应:', result);

      // 无论成功还是失败，都先关闭创建窗口并重置输入
      setNewSessionName('');
      setShowNewSessionInput(false);

      if (result.success && result.session_id) {
        // 重新加载会话列表
        await loadSessions();
        
        // 自动加载并显示新创建的对话
        try {
          const sessionDetail = await getSessionById(result.session_id);
          if (sessionDetail.success) {
            if (sessionDetail.messages && Array.isArray(sessionDetail.messages) && sessionDetail.messages.length > 0) {
              const sessionData = sessionDetail.messages[0] as any;
              setSelectedSession(result.session_id);
              setChatHistory(sessionData.messages || []);
            } else if (sessionDetail.session) {
              const sessionData = sessionDetail.session as any;
              setSelectedSession(result.session_id);
              setChatHistory(sessionData.messages || []);
            } else {
              setSelectedSession(result.session_id);
              setChatHistory([]);
            }
          } else {
            setSelectedSession(result.session_id);
            setChatHistory([]);
          }
        } catch (loadErr) {
          console.error('加载会话详情失败', loadErr);
          // 即使加载失败，也设置选中状态
          setSelectedSession(result.session_id);
          setChatHistory([]);
        }
        
        alert('会话创建成功！');
      } else {
        // 即使创建失败，也刷新会话列表（可能部分成功）
        await loadSessions();
        alert(result.message || '创建会话失败');
      }
    } catch (err) {
      console.error('创建会话失败', err);
      // 发生错误时也要关闭窗口并刷新列表
      setNewSessionName('');
      setShowNewSessionInput(false);
      await loadSessions();
      alert('创建会话失败，请检查网络连接或稍后重试');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('user_name');
    localStorage.removeItem('password');
    localStorage.removeItem('user_id');
    navigate('/');
  };

  return (
    <div className="h-screen flex flex-col bg-cyber-bg">
      {/* 顶部导航栏 */}
      <div className="bg-cyber-surface border-b border-cyber-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-br from-cyber-accent to-cyber-accent-purple p-2 rounded-lg">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-xl font-bold cyber-glow-text">
            AI 智能助手
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-cyber-text-muted">欢迎，<span className="text-cyber-accent">{username}</span></span>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-4 py-2 text-sm text-cyber-text-muted hover:text-cyber-accent hover:bg-cyber-surface-light rounded-lg transition-all"
          >
            <LogOut className="w-4 h-4" />
            退出登录
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* 左侧边栏 */}
        <div className="w-72 bg-cyber-surface border-r border-cyber-border flex flex-col cyber-scrollbar">
          {/* 会话列表 */}
          <div className="flex flex-col overflow-hidden border-b border-cyber-border" style={{ maxHeight: '40%' }}>
            <div className="p-4 flex items-center justify-between border-b border-cyber-border">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-cyber-accent" />
                <h2 className="text-sm font-semibold text-cyber-text">会话列表</h2>
              </div>
              <button
                onClick={() => setShowNewSessionInput(true)}
                className="p-1.5 hover:bg-cyber-surface-light rounded-lg transition-all group"
                title="创建新会话"
              >
                <Plus className="w-4 h-4 text-cyber-text-muted group-hover:text-cyber-accent transition-colors" />
              </button>
            </div>

            {showNewSessionInput && (
              <div className="p-4 border-b border-cyber-border bg-cyber-surface-light/50">
                <input
                  type="text"
                  value={newSessionName}
                  onChange={(e) => setNewSessionName(e.target.value)}
                  placeholder="输入会话名称"
                  className="cyber-input w-full text-sm mb-3"
                  onKeyPress={(e) => e.key === 'Enter' && handleCreateSession()}
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleCreateSession}
                    className="flex-1 px-3 py-2 text-xs bg-gradient-to-r from-cyber-accent to-cyber-accent-purple text-white rounded-lg hover:shadow-cyber-glow transition-all"
                  >
                    创建
                  </button>
                  <button
                    onClick={() => {
                      setShowNewSessionInput(false);
                      setNewSessionName('');
                    }}
                    className="flex-1 px-3 py-2 text-xs bg-cyber-surface-light text-cyber-text-muted rounded-lg hover:text-cyber-text transition-all"
                  >
                    取消
                  </button>
                </div>
              </div>
            )}

            <div 
              className="flex-1 overflow-y-auto p-3 space-y-2 cyber-scrollbar"
            >
              {loading ? (
                <div className="flex items-center justify-center py-4">
                  <div className="cyber-loader w-6 h-6" />
                </div>
              ) : sessions.length === 0 ? (
                <p className="text-sm text-cyber-text-muted text-center py-4">暂无会话，请创建新会话</p>
              ) : (
                sessions.map((session) => (
                  <div
                    key={session.session_id}
                    onDoubleClick={() => handleSessionDoubleClick(session.session_id)}
                    onContextMenu={(e) => handleSessionRightClick(e, session.session_id)}
                    className={`group p-3 rounded-lg cursor-pointer transition-all ${
                      selectedSession === session.session_id
                        ? 'bg-cyber-accent/10 border border-cyber-accent/50 shadow-cyber-glow'
                        : 'bg-cyber-surface-light/50 hover:bg-cyber-surface-light border border-transparent hover:border-cyber-border'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <p className={`text-sm font-medium truncate flex-1 ${
                        selectedSession === session.session_id ? 'text-cyber-accent' : 'text-cyber-text'
                      }`}>
                        {session.session_name}
                      </p>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSessionRightClick(e, session.session_id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 rounded transition-all"
                      >
                        <Trash2 className="w-3 h-3 text-red-400" />
                      </button>
                    </div>
                    {session.session_desc && (
                      <p className="text-xs text-cyber-text-muted mt-1 truncate">{session.session_desc}</p>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* 知识库列表 */}
          <div className="p-4 border-b border-cyber-border flex-shrink-0">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-cyber-accent-green" />
                <h2 className="text-sm font-semibold text-cyber-text">知识库</h2>
              </div>
              <button
                onClick={() => setShowKnowledgeBaseAddModal(true)}
                className="p-1.5 hover:bg-cyber-surface-light rounded-lg transition-all group"
                title="创建知识库"
              >
                <Plus className="w-4 h-4 text-cyber-text-muted group-hover:text-cyber-accent-green transition-colors" />
              </button>
            </div>
            <div 
              className="space-y-2 overflow-y-auto cyber-scrollbar"
              style={{ maxHeight: '200px' }}
            >
              {loadingKnowledge ? (
                <div className="flex items-center justify-center py-4">
                  <div className="cyber-loader w-6 h-6" />
                </div>
              ) : knowledgeBases.length === 0 ? (
                <p className="text-sm text-cyber-text-muted text-center py-2">暂无知识库</p>
              ) : (
                knowledgeBases.map((kb) => (
                  <div
                    key={kb.knowledge_id}
                    onDoubleClick={() => handleKnowledgeDoubleClick(kb)}
                    onContextMenu={(e) => handleKnowledgeRightClick(e, kb)}
                    className={`p-3 rounded-lg cursor-pointer transition-all ${
                      selectedKnowledge?.knowledge_id === kb.knowledge_id
                        ? 'bg-cyber-accent-green/10 border border-cyber-accent-green/50 shadow-cyber-green'
                        : 'bg-cyber-surface-light/50 hover:bg-cyber-surface-light border border-transparent hover:border-cyber-border'
                    }`}
                  >
                    <div className="flex items-center">
                      <p className={`text-sm font-medium truncate flex-1 ${
                        selectedKnowledge?.knowledge_id === kb.knowledge_id ? 'text-cyber-accent-green' : 'text-cyber-text'
                      }`}>{kb.knowledge_name}</p>
                    </div>
                    {kb.description && (
                      <p className="text-xs text-cyber-text-muted mt-1 truncate">{kb.description}</p>
                    )}
                    {kb.file_num !== undefined && (
                      <p className="text-xs text-cyber-text-muted/60 mt-1">文件数: {kb.file_num}</p>
                    )}
                  </div>
                ))
              )}
            </div>
            {selectedKnowledge && (
              <button
                onClick={() => {
                  setSelectedKnowledge(null);
                  setFileList([]);
                }}
                className="mt-3 w-full text-xs text-cyber-text-muted hover:text-cyber-accent-green transition-colors"
              >
                取消选择知识库
              </button>
            )}
          </div>

          {/* 数据库列表 */}
          <div className="p-4 border-b border-cyber-border flex-shrink-0">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-cyber-accent-purple" />
                <h2 className="text-sm font-semibold text-cyber-text">数据库</h2>
              </div>
              <button
                onClick={() => setShowDatabaseAddModal(true)}
                className="p-1.5 hover:bg-cyber-surface-light rounded-lg transition-all group"
                title="添加数据库"
              >
                <Plus className="w-4 h-4 text-cyber-text-muted group-hover:text-cyber-accent-purple transition-colors" />
              </button>
            </div>
            <div 
              className="space-y-2 overflow-y-auto cyber-scrollbar"
              style={{ maxHeight: '200px' }}
            >
              {loadingDatabases ? (
                <div className="flex items-center justify-center py-4">
                  <div className="cyber-loader w-6 h-6" />
                </div>
              ) : databases.length === 0 ? (
                <p className="text-sm text-cyber-text-muted text-center py-2">暂无数据库</p>
              ) : (
                databases.map((db) => (
                  <div
                    key={db.sql_id}
                    onDoubleClick={() => handleDatabaseDoubleClick(db)}
                    onContextMenu={(e) => handleDatabaseRightClick(e, db)}
                    className={`p-3 rounded-lg cursor-pointer transition-all ${
                      selectedDatabase?.sql_id === db.sql_id
                        ? 'bg-cyber-accent-purple/10 border border-cyber-accent-purple/50 shadow-cyber-purple'
                        : 'bg-cyber-surface-light/50 hover:bg-cyber-surface-light border border-transparent hover:border-cyber-border'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <DatabaseIcon className={`w-4 h-4 flex-shrink-0 ${
                        selectedDatabase?.sql_id === db.sql_id ? 'text-cyber-accent-purple' : 'text-cyber-text-muted'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-medium truncate ${
                          selectedDatabase?.sql_id === db.sql_id ? 'text-cyber-accent-purple' : 'text-cyber-text'
                        }`}>
                          {db.sql_name}
                        </p>
                        <p className="text-xs text-cyber-text-muted/60 truncate">{db.ip}:{db.port}</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
            {selectedDatabase && (
              <button
                onClick={() => {
                  setSelectedDatabase(null);
                }}
                className="mt-3 w-full text-xs text-cyber-text-muted hover:text-cyber-accent-purple transition-colors"
              >
                取消选择数据库
              </button>
            )}
          </div>

          {/* 文件列表 */}
          {selectedKnowledge && (
            <div className="flex-1 flex flex-col overflow-hidden border-t border-cyber-border">
              <div className="p-4 border-b border-cyber-border">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <File className="w-4 h-4 text-cyber-accent" />
                    <h2 className="text-sm font-semibold text-cyber-text">文件列表</h2>
                  </div>
                  <button
                    onClick={handleFileUploadClick}
                    className="p-1.5 hover:bg-cyber-surface-light rounded-lg transition-all group"
                    title="上传文件"
                  >
                    <Upload className="w-4 h-4 text-cyber-text-muted group-hover:text-cyber-accent transition-colors" />
                  </button>
                </div>
                {showFileUpload && (
                  <div className="mb-3 p-3 bg-cyber-surface-light/50 rounded-lg border border-cyber-border">
                    <div className="flex gap-2 mb-2">
                      <button
                        onClick={() => setSelectedPermission('public')}
                        className={`flex-1 px-2 py-1.5 text-xs rounded-lg transition-all ${
                          selectedPermission === 'public'
                            ? 'bg-cyber-accent text-white shadow-cyber-glow'
                            : 'bg-cyber-surface text-cyber-text-muted hover:text-cyber-text'
                        }`}
                      >
                        共享权限
                      </button>
                      <button
                        onClick={() => setSelectedPermission('private')}
                        className={`flex-1 px-2 py-1.5 text-xs rounded-lg transition-all ${
                          selectedPermission === 'private'
                            ? 'bg-cyber-accent-purple text-white shadow-cyber-purple'
                            : 'bg-cyber-surface text-cyber-text-muted hover:text-cyber-text'
                        }`}
                      >
                        私有权限
                      </button>
                    </div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      onChange={handleFileSelect}
                      className="hidden"
                    />
                  </div>
                )}
              </div>
              <div 
                className="p-3 overflow-y-auto cyber-scrollbar"
                style={{ maxHeight: 'calc(3 * (48px + 8px))' }}
              >
                {loadingFiles ? (
                  <div className="flex items-center justify-center py-4">
                    <div className="cyber-loader w-6 h-6" />
                  </div>
                ) : fileList.length === 0 ? (
                  <p className="text-sm text-cyber-text-muted text-center py-2">暂无文件</p>
                ) : (
                  <div className="space-y-2">
                    {fileList.map((file) => (
                      <div
                        key={file.file_id}
                        onContextMenu={(e) => handleFileRightClick(e, file.file_id, file.file_name)}
                        className="group p-3 rounded-lg bg-cyber-surface-light/50 hover:bg-cyber-surface-light cursor-pointer transition-all border border-transparent hover:border-cyber-border flex items-center justify-between"
                        title={file.file_name}
                      >
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          <File className="w-4 h-4 text-cyber-text-muted flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-cyber-text truncate" title={file.file_name}>
                              {file.file_name}
                            </p>
                            <p className={`text-xs mt-0.5 ${
                              file.permission_level === 'public' ? 'text-cyber-accent-green/70' : 'text-cyber-accent-purple/70'
                            }`}>
                              {file.permission_level === 'public' ? '共享' : '私有'}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 右侧聊天区域 */}
        <div className="flex-1 flex flex-col bg-cyber-bg">
          {selectedSession ? (
            <ChatArea
              sessionId={selectedSession}
              chatHistory={chatHistory}
              setChatHistory={setChatHistory}
              knowledgeId={selectedKnowledge?.knowledge_id}
              knowledgeName={selectedKnowledge?.knowledge_name}
              databaseName={selectedDatabase?.sql_name}
              sqlId={selectedDatabase?.sql_id}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="w-20 h-20 mx-auto mb-6 bg-cyber-surface rounded-2xl flex items-center justify-center cyber-float">
                  <MessageSquare className="w-10 h-10 text-cyber-accent" />
                </div>
                <p className="text-lg text-cyber-text mb-2">请选择或创建一个会话开始对话</p>
                <p className="text-sm text-cyber-text-muted">双击左侧会话列表中的会话即可开始</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 添加数据库弹窗 */}
      <DatabaseAddModal
        isOpen={showDatabaseAddModal}
        onClose={() => setShowDatabaseAddModal(false)}
        onSuccess={handleDatabaseAddSuccess}
        user_name={username}
        password={password}
        user_id={userId}
      />

      {/* 数据库详情弹窗 */}
      <DatabaseDetailModal
        isOpen={showDatabaseDetailModal}
        onClose={() => {
          setShowDatabaseDetailModal(false);
          setContextMenuDatabase(null);
        }}
        onSuccess={() => {
          handleDatabaseAddSuccess();
          setShowDatabaseDetailModal(false);
          setContextMenuDatabase(null);
        }}
        database={contextMenuDatabase}
        user_name={username}
        password={password}
        user_id={userId}
      />

      {/* 创建知识库弹窗 */}
      <KnowledgeBaseAddModal
        isOpen={showKnowledgeBaseAddModal}
        onClose={() => setShowKnowledgeBaseAddModal(false)}
        onSuccess={handleKnowledgeBaseAddSuccess}
        user_name={username}
        password={password}
      />

      {/* 删除知识库弹窗 */}
      <KnowledgeBaseDeleteModal
        isOpen={showKnowledgeBaseDeleteModal}
        onClose={() => {
          setShowKnowledgeBaseDeleteModal(false);
          setContextMenuKnowledgeBase(null);
        }}
        onSuccess={handleKnowledgeBaseDeleteSuccess}
        knowledgeBase={contextMenuKnowledgeBase ? {
          knowledge_id: contextMenuKnowledgeBase.knowledge_id,
          knowledge_name: contextMenuKnowledgeBase.knowledge_name
        } : null}
        user_name={username}
        password={password}
        user_id={userId}
      />
    </div>
  );
};

export default MainPage;

