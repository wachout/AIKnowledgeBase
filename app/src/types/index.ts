// 用户类型
export interface User {
  user_id: string;
  user_name: string;
}

// 会话消息类型
export interface SessionMessage {
  session_id: string;
  session_name: string;
  session_desc: string;
}

// 聊天消息类型
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string | Array<{type: string; content: string}>;
}

// 会话详情类型
export interface SessionDetail {
  session_id: string;
  session_name: string;
  session_desc: string;
  messages: ChatMessage[];
}

// 知识库类型
export interface Knowledge {
  knowledge_id: string;
  knowledge_name: string;
  name?: string;
  description?: string;
  create_time?: string;
  valid_start_time?: string;
  valid_end_time?: string;
  create_user_id?: string;
  file_num?: number;
}

// API响应类型
export interface ApiResponse<T = any> {
  success: boolean;
  message: string;
  data?: T;
  user_id?: string;
  session_id?: string;
  messages?: T;
  session?: T;
  knowledge_base?: T | T[];
  file_list?: T;  // 用于文件列表API响应
}

// 聊天流式响应
export interface ChatStreamChunk {
  success: boolean;
  message: string;
  data: {
    id: string;
    object: string;
    created: number;
    model: string;
    choices: Array<{
      index: number;
      delta: {
        content: string;
      };
      finish_reason: string | null;
    }>;
  };
}

// 数据库类型
export interface Database {
  sql_id: string;
  user_id: string;
  ip: string;
  port: string;
  sql_type: 'mysql' | 'postgresql';
  sql_name: string;
  sql_user_name: string;
  sql_user_password?: string; // 不返回密码，仅用于输入
  sql_description?: string;
}

// 表信息类型
export interface TableInfo {
  table_id?: string;
  sql_id?: string;
  table_name: string;
  table_description?: string;
  columns?: ColumnInfo[];
}

// 列信息类型
export interface ColumnInfo {
  col_id?: string;
  table_id?: string;
  col_name: string;
  col_type?: string;
  col_info?: any; // JSON格式存储列的详细信息
}

// 列关联关系类型
export interface RelationInfo {
  rel_id?: string;
  sql_id?: string;
  from_table: string;
  from_col: string;
  to_table: string;
  to_col: string;
}

// 表列表响应类型
export interface SqlItem {
  sql: string;
  des: string;
}

export interface TableListResponse {
  success: boolean;
  message: string;
  table_list?: TableInfo[];
  relations?: RelationInfo[];
  sql_list?: SqlItem[];
}

