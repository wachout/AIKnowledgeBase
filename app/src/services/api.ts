import { ApiResponse, SessionMessage, SessionDetail, Database, TableListResponse } from '../types';

// 从环境变量获取API基础URL，如果未设置则使用默认的本地地址
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:6199/api';

// 在开发环境中打印API地址，便于调试
if (import.meta.env.DEV) {
  console.log('API Base URL:', API_BASE_URL);
}

// 用户登录
export const userLogin = async (user_name: string, password: string): Promise<ApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/user_login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ user_name, password }),
  });
  return response.json();
};

// 用户注册
export const userRegister = async (
  user_name: string,
  password: string,
  confirm_password: string
): Promise<ApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ user_name, password, confirm_password }),
  });
  return response.json();
};

// 删除用户
export const deleteUser = async (user_name: string, password: string): Promise<ApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/delete_user`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ user_name, password }),
  });
  return response.json();
};

// 用户登出
export const userLogout = async (session_id: string): Promise<ApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/user_logout`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ session_id }),
  });
  return response.json();
};

// 创建会话
export const createSession = async (
  user_name: string,
  password: string,
  session_name: string,
  knowledge_name?: string,
  knowledge_id?: string,
  user_id?: string
): Promise<ApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/create_session`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_name,
      password,
      session_name,
      knowledge_name,
      knowledge_id,
      user_id,
    }),
  });
  return response.json();
};

// 获取会话列表
export const getSessionMessages = async (
  user_name: string,
  password: string,
  user_id?: string
): Promise<ApiResponse<SessionMessage[]>> => {
  const response = await fetch(`${API_BASE_URL}/get_user_session_messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ user_name, password, user_id }),
  });
  return response.json();
};

// 根据ID获取会话详情
export const getSessionById = async (session_id: string): Promise<ApiResponse<SessionDetail[]>> => {
  const response = await fetch(`${API_BASE_URL}/get_sessions_by_id`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ session_id }),
  });
  return response.json();
};

// 删除会话
export const deleteSession = async (session_id: string): Promise<ApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/delete_sessions_by_session_id`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ session_id }),
  });
  return response.json();
};

// 获取知识库列表
export const getKnowledgeBase = async (
  user_name: string,
  password: string,
  knowledge_id?: string
): Promise<ApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/get_knowledge_base`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_name,
      password,
      knowledge_id,
    }),
  });
  return response.json();
};

// 创建知识库
export const createKnowledgeBase = async (
  user_name: string,
  password: string,
  name: string,
  description: string,
  valid_start_time?: string,
  valid_end_time?: string
): Promise<ApiResponse<{ knowledge_name: string }>> => {
  const response = await fetch(`${API_BASE_URL}/create_knowledge_base`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_name,
      password,
      name,
      description,
      valid_start_time,
      valid_end_time,
    }),
  });
  return response.json();
};

// 删除知识库
export const deleteKnowledgeBase = async (
  user_name: string,
  password: string,
  user_id: string,
  knowledge_id?: string,
  knowledge_name?: string
): Promise<ApiResponse> => {
  const requestBody: any = {
    user_name,
    password,
    user_id,
  };
  
  if (knowledge_id) {
    requestBody.knowledge_id = knowledge_id;
  }
  if (knowledge_name) {
    requestBody.knowledge_name = knowledge_name;
  }
  
  const response = await fetch(`${API_BASE_URL}/delete_knowledge_base`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(requestBody),
  });
  return response.json();
};

// 获取知识库文件列表
export const getKnowledgeBaseFileList = async (
  knowledge_id: string
): Promise<ApiResponse<Array<{
  file_id: string;
  file_name: string;
  file_path: string;
  file_size: string;
  upload_time: string;
  upload_user_id: string;
  permission_level: string;
  url: string;
}>>> => {
  const response = await fetch(`${API_BASE_URL}/get_knowledge_base_file_list`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ knowledge_id }),
  });
  return response.json();
};

// 删除文件
export const deleteFile = async (
  user_name: string,
  password: string,
  file_id: string
): Promise<ApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/delete_file`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_name,
      password,
      file_id,
    }),
  });
  return response.json();
};

// 上传文件
export const addFile = async (
  user_name: string,
  password: string,
  file: File,
  permission_level: 'public' | 'private',
  knowledge_id?: string,
  knowledge_name?: string
): Promise<ApiResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('user_name', user_name);
  formData.append('password', password);
  formData.append('permission_level', permission_level);
  
  // 如果提供了knowledge_id或knowledge_name，添加到FormData
  if (knowledge_id) {
    formData.append('knowledge_id', knowledge_id);
  }
  if (knowledge_name) {
    formData.append('knowledge_name', knowledge_name);
  }
  
  const response = await fetch(`${API_BASE_URL}/add_file`, {
    method: 'POST',
    body: formData,
  });
  return response.json();
};

// 流式聊天
export const chatStream = async (
  user_name: string,
  password: string,
  query: string,
  session_id: string,
  knowledge_name?: string,
  knowledge_id?: string,
  sql_id?: string,
  file?: File,
  choice?: 'ask' | 'discussion',
  onChunk?: (content: string) => void,
  onComplete?: () => void,
  onError?: (error: Error) => void
): Promise<void> => {
  let hasCompleted = false;
  let shouldStopReading = false;
  
  try {
    let response: Response;
    
    if (file) {
      // 如果有文件，使用 FormData
      const formData = new FormData();
      formData.append('user_name', user_name);
      formData.append('password', password);
      formData.append('session_id', session_id);
      formData.append('query', query);
      formData.append('stream_chat', 'true');
      formData.append('stream_chat_type', 'default');
      formData.append('file', file);
      if (knowledge_name) formData.append('knowledge_name', knowledge_name);
      if (knowledge_id) formData.append('knowledge_id', knowledge_id);
      if (sql_id) formData.append('sql_id', sql_id);
      if (choice) formData.append('choice', choice);
      
      response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          // FormData 不需要设置 Content-Type，浏览器会自动设置 multipart/form-data
          'Accept': 'application/json, text/plain, */*',
        },
        body: formData,
      });
    } else {
      // 没有文件，使用 JSON
      response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json, text/plain, */*',
        },
        body: JSON.stringify({
          user_name,
          password,
          session_id,
          query,
          stream_chat: true,
          stream_chat_type: 'default',
          knowledge_name,
          knowledge_id,
          sql_id,
          choice,
        }),
      });
    }

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Unknown error');
      console.error('HTTP错误:', response.status, response.statusText, errorText);
      throw new Error(`HTTP ${response.status}: ${response.statusText}. 响应: ${errorText}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('无法获取响应流');
    }

    while (!shouldStopReading) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      
      // 尝试解析流式数据
      try {
        // 按行分割处理（可能有多行JSON）
        const lines = chunk.split('\n').filter(line => line.trim());
        
        for (const line of lines) {
          try {
            // 处理SSE格式（data: {...}）
            let cleanLine = line.replace(/^data:\s*/, '');
            
            // 如果行以 data: 开头但后面是空，跳过
            if (cleanLine === '' || cleanLine === '[DONE]') {
              if (cleanLine === '[DONE]') {
                hasCompleted = true;
                shouldStopReading = true;
                onComplete?.();
                break;
              }
              continue;
            }
            
            // 解析JSON
            const data = JSON.parse(cleanLine);
            
            console.log('📥 收到流式数据:', {
              hasData: !!data.data,
              hasChoices: !!data.choices,
              finishReason: data.data?.choices?.[0]?.finish_reason || data.choices?.[0]?.finish_reason,
              hasContent: !!(data.data?.choices?.[0]?.delta?.content || data.choices?.[0]?.delta?.content),
              deltaEmpty: !data.data?.choices?.[0]?.delta || Object.keys(data.data?.choices?.[0]?.delta || {}).length === 0,
            });
            
            // 处理流式结束信号
            const finishReason = data.data?.choices?.[0]?.finish_reason || data.choices?.[0]?.finish_reason;
            if (finishReason === 'stop') {
              hasCompleted = true;
              shouldStopReading = true;
              onComplete?.();
              break; // 结束流式读取
            }
            
            // 提取 content 和 type
            let content: string | undefined;
            let contentType: string | undefined;

            // 处理标准OpenAI格式（data.choices[0].delta.content）
            if (data.data?.choices?.[0]?.delta?.content !== undefined) {
              content = data.data.choices[0].delta.content;
              contentType = data.data.choices[0].delta.type;
              console.log('📥 标准格式，content:', content, 'type:', contentType);
            }
            // 处理直接的choices格式（choices[0].delta.content）
            else if (data.choices?.[0]?.delta?.content !== undefined) {
              content = data.choices[0].delta.content;
              contentType = data.choices[0].delta.type;
              console.log('📥 直接格式，content:', content, 'type:', contentType);
            }
            // 处理普通响应格式
            else if (data.success && data.content) {
              content = data.content;
              console.log('📥 普通格式，content:', content);
            }

            // 根据 type 处理内容
            // 对于 file 类型，优先处理（即使 content 为空也要处理）
            if (contentType === 'file' || contentType === 'FILE') {
              // File类型，使用特殊格式标识文件路径
              // 确保 content 是字符串类型
              const filePath = (content !== undefined && content !== null) ? String(content).trim() : '';
              console.log('📁 检测到文件类型chunk，contentType:', contentType, 'content:', content, 'filePath:', filePath);
              if (filePath) {
                const formattedContent = `[FILE]\n${filePath}`;
                console.log('📁 发送文件chunk:', formattedContent);
                onChunk?.(formattedContent);
              } else {
                console.warn('⚠️ 文件类型chunk但文件路径为空，content:', content, 'contentType:', contentType);
              }
              // file类型处理完毕，不再继续处理其他类型
            } else if (content && content.trim()) {
              // 如果有类型标识，根据类型格式化内容
              if (contentType === 'echarts') {
                // ECharts类型，检查内容是否已经包含[ECHARTS]前缀
                if (content.trim().startsWith('[ECHARTS]')) {
                  // 已经包含前缀，直接传递
                  onChunk?.(content);
                } else {
                  // 添加前缀标识
                  const formattedContent = `[ECHARTS]\n${content}`;
                  onChunk?.(formattedContent);
                }
              } else if (contentType === 'html_table') {
                // HTML表格类型，检查内容是否已经包含[HTML_TABLE]前缀
                if (content.trim().startsWith('[HTML_TABLE]')) {
                  // 已经包含前缀，直接传递
                  onChunk?.(content);
                } else {
                  // 添加前缀标识
                  const formattedContent = `[HTML_TABLE]\n${content}`;
                  onChunk?.(formattedContent);
                }
              } else if (contentType === 'schema') {
                // Schema类型，检查内容是否已经包含[SCHEMA]前缀
                if (content.trim().startsWith('[SCHEMA]')) {
                  // 已经包含前缀，直接传递
                  onChunk?.(content);
                } else {
                  // 添加前缀标识
                  const formattedContent = `[SCHEMA]\n${content}`;
                  onChunk?.(formattedContent);
                }
              } else {
                // 普通文本或其他类型，直接传递
                onChunk?.(content);
              }
            } else {
              // content 为空，不调用 onChunk，保持当前状态（显示"正在思考中"）
              console.log('⏳ content为空，保持"正在思考中"状态，contentType:', contentType);
            }
          } catch (lineError) {
            // 如果单行解析失败，尝试解析整个chunk
            try {
              const data = JSON.parse(chunk.trim());
              
              // 处理流式结束信号
              const finishReason = data.data?.choices?.[0]?.finish_reason || data.choices?.[0]?.finish_reason;
              if (finishReason === 'stop') {
                hasCompleted = true;
                shouldStopReading = true;
                onComplete?.();
                break;
              }
              
              // 提取 content 和 type
              let content: string | undefined;
              let contentType: string | undefined;
              if (data.data?.choices?.[0]?.delta?.content !== undefined) {
                content = data.data.choices[0].delta.content;
                contentType = data.data.choices[0].delta.type;
                console.log('📥 标准格式(catch)，content:', content, 'type:', contentType);
              } else if (data.choices?.[0]?.delta?.content !== undefined) {
                content = data.choices[0].delta.content;
                contentType = data.choices[0].delta.type;
                console.log('📥 直接格式(catch)，content:', content, 'type:', contentType);
              } else if (data.success && data.content) {
                content = data.content;
                console.log('📥 普通格式(catch)，content:', content);
              }

              // 对于 file 类型，优先处理（即使 content 为空也要处理）
              if (contentType === 'file' || contentType === 'FILE') {
                // File类型，使用特殊格式标识文件路径
                // 确保 content 是字符串类型
                const filePath = (content !== undefined && content !== null) ? String(content).trim() : '';
                console.log('📁 检测到文件类型chunk (catch块)，contentType:', contentType, 'content:', content, 'filePath:', filePath);
                if (filePath) {
                  const formattedContent = `[FILE]\n${filePath}`;
                  console.log('📁 发送文件chunk (catch块):', formattedContent);
                  onChunk?.(formattedContent);
                } else {
                  console.warn('⚠️ 文件类型chunk但文件路径为空 (catch块)，content:', content, 'contentType:', contentType);
                }
                // file类型处理完毕，不再继续处理其他类型
              } else if (content && content.trim()) {
                // 根据 type 处理内容
                if (contentType === 'echarts') {
                  // ECharts类型，检查内容是否已经包含[ECHARTS]前缀
                  if (content.trim().startsWith('[ECHARTS]')) {
                    // 已经包含前缀，直接传递
                    onChunk?.(content);
                  } else {
                    // 添加前缀标识
                    const formattedContent = `[ECHARTS]\n${content}`;
                    onChunk?.(formattedContent);
                  }
                } else if (contentType === 'html_table') {
                  // HTML表格类型，检查内容是否已经包含[HTML_TABLE]前缀
                  if (content.trim().startsWith('[HTML_TABLE]')) {
                    // 已经包含前缀，直接传递
                    onChunk?.(content);
                  } else {
                    // 添加前缀标识
                    const formattedContent = `[HTML_TABLE]\n${content}`;
                    onChunk?.(formattedContent);
                  }
                } else if (contentType === 'schema') {
                  // Schema类型，检查内容是否已经包含[SCHEMA]前缀
                  if (content.trim().startsWith('[SCHEMA]')) {
                    // 已经包含前缀，直接传递
                    onChunk?.(content);
                  } else {
                    // 添加前缀标识
                    const formattedContent = `[SCHEMA]\n${content}`;
                    onChunk?.(formattedContent);
                  }
                } else {
                  // 普通文本或其他类型，直接传递
                  onChunk?.(content);
                }
              } else {
                // content 为空，不调用 onChunk，保持当前状态（显示"正在思考中"）
                console.log('⏳ content为空 (catch块)，保持"正在思考中"状态，contentType:', contentType);
              }
            } catch (chunkError) {
              // 忽略无法解析的行和chunk
              console.warn('⚠️ 无法解析的流式数据:', line.substring(0, 100));
            }
          }
        }
      } catch (e) {
        console.error('流式数据解析错误:', e);
      }
    }

    // 确保至少调用一次onComplete（在没有显式结束信号的情况下）
    if (!hasCompleted) {
      onComplete?.();
    }
  } catch (error) {
    console.error('流式聊天详细错误:', {
      message: error instanceof Error ? error.message : 'Unknown error',
      stack: error instanceof Error ? error.stack : undefined,
      type: typeof error,
      value: error,
    });
    
    // 提供更友好的错误信息
    let friendlyError: Error;
    if (error instanceof TypeError && error.message.includes('fetch')) {
      friendlyError = new Error('网络连接失败，请检查：1) 后端服务是否启动；2) CORS配置；3) 网络连接');
    } else if (error instanceof Error) {
      friendlyError = error;
    } else {
      friendlyError = new Error(`未知错误: ${String(error)}`);
    }
    
    onError?.(friendlyError);
  }
};

// 插入数据库信息
export const insertSqlInfo = async (
  user_name: string,
  password: string,
  ip: string,
  port: string,
  sql_type: 'mysql' | 'postgresql',
  sql_name: string,
  sql_user_name: string,
  sql_user_password: string,
  sql_description: string,
  user_id: string
): Promise<ApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/insert_sql_info`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_name,
      password,
      ip,
      port,
      sql_type,
      sql_name,
      sql_user_name,
      sql_user_password,
      sql_description,
      user_id,
    }),
  });
  return response.json();
};

// 获取数据库列表
export const getSqlInfoList = async (
  user_name: string,
  password: string,
  user_id?: string
): Promise<ApiResponse<Database[]>> => {
  const response = await fetch(`${API_BASE_URL}/get_sql_info_list`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ user_name, password, user_id }),
  });
  return response.json();
};

// 获取表信息
export const getTableInfo = async (
  ip: string,
  port: string,
  sql_type: 'mysql' | 'postgresql',
  sql_name: string,
  user_id: string,
  sql_id?: string
): Promise<TableListResponse> => {
  const username = localStorage.getItem('user_name') || '';
  const password = localStorage.getItem('password') || '';
  
  const requestBody: any = {
    user_name: username,
    password: password,
    ip,
    port,
    sql_type,
    sql_name,
    user_id,
  };
  
  if (sql_id) {
    requestBody.sql_id = sql_id;
  }
  
  const response = await fetch(`${API_BASE_URL}/get_table_info`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(requestBody),
  });
  return response.json();
};

// 更新数据库信息
export const updateSqlInfo = async (
  user_id: string,
  sql_id: string,
  data: {
    tables?: Array<{
      table_name: string;
      table_description?: string;
    }>;
    columns?: Array<{
      table_name: string;
      column_name: string;
      comment: string;
    }>;
    relations?: Array<{
      from_table: string;
      from_col: string;
      to_table: string;
      to_col: string;
    }>;
    sql_description?: string;
    sql_list?: Array<{
      sql: string;
      des: string;
    }>;
  }
): Promise<ApiResponse> => {
  const username = localStorage.getItem('user_name') || '';
  const password = localStorage.getItem('password') || '';
  
  const response = await fetch(`${API_BASE_URL}/update_sql_info`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_name: username,
      password: password,
      user_id,
      sql_id,
      ...data,
    }),
  });
  return response.json();
};

// 删除数据库信息
export const deleteSqlInfo = async (
  user_name: string,
  password: string,
  sql_id: string
): Promise<ApiResponse> => {
  const response = await fetch(`${API_BASE_URL}/delete_sql_info`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_name,
      password,
      sql_id,
    }),
  });
  return response.json();
};

