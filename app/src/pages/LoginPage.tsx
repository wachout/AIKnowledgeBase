import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { userLogin, userRegister, deleteUser } from '../services/api';
import { MessageSquare, Zap, Shield, Cpu } from 'lucide-react';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register' | 'delete'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (mode === 'login') {
        const result = await userLogin(username, password);
        if (result.success) {
          localStorage.setItem('user_name', username);
          localStorage.setItem('password', password);
          localStorage.setItem('user_id', result.user_id || '');
          navigate('/main');
        } else {
          setError(result.message || '登录失败');
        }
      } else if (mode === 'register') {
        if (password !== confirmPassword) {
          setError('两次输入的密码不一致');
          setLoading(false);
          return;
        }
        const result = await userRegister(username, password, confirmPassword);
        if (result.success) {
          setError('');
          setMode('login');
          alert('注册成功，请登录');
        } else {
          setError(result.message || '注册失败');
        }
      } else if (mode === 'delete') {
        const confirmDelete = window.confirm('确定要删除此账户吗？此操作不可恢复！');
        if (confirmDelete) {
          const result = await deleteUser(username, password);
          if (result.success) {
            alert('账户已删除');
            setUsername('');
            setPassword('');
            setMode('login');
          } else {
            setError(result.message || '删除失败');
          }
        }
      }
    } catch (err) {
      setError('操作失败，请检查网络连接');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-cyber-bg cyber-grid-bg cyber-particles flex items-center justify-center p-4 relative overflow-hidden">
      {/* 背景装饰元素 */}
      <div className="absolute top-20 left-20 w-32 h-32 border border-cyber-accent/20 rounded-full cyber-float" style={{ animationDelay: '0s' }} />
      <div className="absolute bottom-32 right-32 w-24 h-24 border border-cyber-accent-purple/20 rounded-full cyber-float" style={{ animationDelay: '1s' }} />
      <div className="absolute top-1/3 right-20 w-16 h-16 border border-cyber-accent-green/20 rounded-full cyber-float" style={{ animationDelay: '2s' }} />
      
      {/* 发光线条 */}
      <div className="absolute top-0 left-1/4 w-px h-40 bg-gradient-to-b from-transparent via-cyber-accent/30 to-transparent" />
      <div className="absolute bottom-0 right-1/3 w-px h-60 bg-gradient-to-t from-transparent via-cyber-accent-purple/30 to-transparent" />

      <div className="w-full max-w-md relative z-10">
        {/* 登录卡片 */}
        <div className="cyber-card p-8 backdrop-blur-xl bg-cyber-surface/80 shadow-cyber-glow">
          {/* Logo 和标题 */}
          <div className="flex flex-col items-center mb-8">
            <div className="relative mb-4">
              <div className="bg-gradient-to-br from-cyber-accent to-cyber-accent-purple p-4 rounded-2xl cyber-pulse">
                <MessageSquare className="w-10 h-10 text-white" />
              </div>
              {/* 光晕效果 */}
              <div className="absolute inset-0 bg-cyber-accent/20 rounded-2xl blur-xl" />
            </div>
            
            <h1 className="text-3xl font-bold cyber-glow-text mb-2">
              AI 智能助手
            </h1>
            <p className="text-cyber-text-muted text-sm">
              {mode === 'login' && '登录您的账户'}
              {mode === 'register' && '创建新账户'}
              {mode === 'delete' && '删除账户'}
            </p>
          </div>

          {/* 功能图标 */}
          <div className="flex justify-center gap-8 mb-8">
            <div className="flex flex-col items-center text-cyber-text-muted">
              <Zap className="w-5 h-5 text-cyber-accent mb-1" />
              <span className="text-xs">极速响应</span>
            </div>
            <div className="flex flex-col items-center text-cyber-text-muted">
              <Shield className="w-5 h-5 text-cyber-accent-green mb-1" />
              <span className="text-xs">安全可靠</span>
            </div>
            <div className="flex flex-col items-center text-cyber-text-muted">
              <Cpu className="w-5 h-5 text-cyber-accent-purple mb-1" />
              <span className="text-xs">智能分析</span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-cyber-text-muted mb-2">
                用户名
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="cyber-input w-full"
                placeholder="请输入用户名"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-cyber-text-muted mb-2">
                密码
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="cyber-input w-full"
                placeholder="请输入密码"
                required
              />
            </div>

            {mode === 'register' && (
              <div>
                <label className="block text-sm font-medium text-cyber-text-muted mb-2">
                  确认密码
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="cyber-input w-full"
                  placeholder="请再次输入密码"
                  required
                />
              </div>
            )}

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg text-sm flex items-center gap-2">
                <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="cyber-btn w-full flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="cyber-loader w-5 h-5" />
                  <span>处理中...</span>
                </>
              ) : (
                <span>
                  {mode === 'login' ? '登 录' : mode === 'register' ? '注 册' : '删除账户'}
                </span>
              )}
            </button>
          </form>

          {/* 切换模式链接 */}
          <div className="mt-6 flex justify-center gap-4 text-sm">
            {mode !== 'login' && (
              <button
                onClick={() => {
                  setMode('login');
                  setError('');
                  setConfirmPassword('');
                }}
                className="text-cyber-accent hover:text-cyber-accent/80 font-medium transition-colors"
              >
                返回登录
              </button>
            )}
            {mode === 'login' && (
              <>
                <button
                  onClick={() => {
                    setMode('register');
                    setError('');
                  }}
                  className="text-cyber-accent hover:text-cyber-accent/80 font-medium transition-colors"
                >
                  注册新账户
                </button>
                <span className="text-cyber-border">|</span>
                <button
                  onClick={() => {
                    setMode('delete');
                    setError('');
                  }}
                  className="text-red-400 hover:text-red-300 font-medium transition-colors"
                >
                  删除账户
                </button>
              </>
            )}
          </div>
        </div>

        {/* 底部装饰文字 */}
        <div className="text-center mt-6 text-cyber-text-muted text-xs">
          <p>Powered by Advanced AI Technology</p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;

