import React, { useEffect, useRef, useState, useMemo } from 'react';

// 🎯 ECharts配置修复函数
const fixEChartsOption = (option: any): any => {
  if (!option || typeof option !== 'object') {
    console.warn('⚠️ ECharts配置无效，返回默认配置');
    return {
      title: { text: '图表配置错误' },
      series: [{ type: 'bar', data: [10, 20, 30] }]
    };
  }

  const fixedOption = { ...option };

  // 🎯 修复 xAxis 配置
  if (fixedOption.xAxis) {
    if (Array.isArray(fixedOption.xAxis)) {
      fixedOption.xAxis = fixedOption.xAxis.map((axis: any) => fixAxis(axis));
    } else {
      fixedOption.xAxis = fixAxis(fixedOption.xAxis);
    }
  } else {
    // 如果没有xAxis，添加默认的
    fixedOption.xAxis = { type: 'category', data: ['A', 'B', 'C'] };
  }

  // 🎯 修复 yAxis 配置
  if (fixedOption.yAxis) {
    if (Array.isArray(fixedOption.yAxis)) {
      fixedOption.yAxis = fixedOption.yAxis.map((axis: any) => fixAxis(axis));
    } else {
      fixedOption.yAxis = fixAxis(fixedOption.yAxis);
    }
  } else {
    // 如果没有yAxis，添加默认的
    fixedOption.yAxis = { type: 'value' };
  }

  // 🎯 修复 series 配置
  if (fixedOption.series) {
    if (Array.isArray(fixedOption.series)) {
      fixedOption.series = fixedOption.series.map((series: any) => fixSeries(series));
    } else {
      fixedOption.series = [fixSeries(fixedOption.series)];
    }
  } else {
    // 如果没有series，添加默认的
    fixedOption.series = [{ type: 'bar', data: [10, 20, 30] }];
  }

  // 🎯 确保有title
  if (!fixedOption.title) {
    fixedOption.title = { text: '数据图表' };
  }

  // 🎯 确保有tooltip
  if (!fixedOption.tooltip) {
    fixedOption.tooltip = {};
  }

  console.log('✅ ECharts配置修复完成:', {
    xAxisType: fixedOption.xAxis?.type,
    seriesCount: Array.isArray(fixedOption.series) ? fixedOption.series.length : 1,
    hasData: Array.isArray(fixedOption.series) ? fixedOption.series.some(s => s.data && s.data.length > 0) : false
  });

  return fixedOption;
};

// 🎯 修复坐标轴配置
const fixAxis = (axis: any): any => {
  const fixedAxis = { ...axis };

  // 修复 type
  if (!fixedAxis.type || fixedAxis.type === null || typeof fixedAxis.type !== 'string') {
    // 根据数据类型推断axis类型
    if (fixedAxis.data && Array.isArray(fixedAxis.data)) {
      const firstData = fixedAxis.data[0];
      if (typeof firstData === 'string') {
        fixedAxis.type = 'category';
      } else if (typeof firstData === 'number') {
        fixedAxis.type = 'value';
      } else {
        fixedAxis.type = 'category';
      }
    } else {
      fixedAxis.type = 'category';
    }
  }

  // 修复 data
  if (!fixedAxis.data || !Array.isArray(fixedAxis.data) || fixedAxis.data.length === 0) {
    if (fixedAxis.type === 'category') {
      fixedAxis.data = ['A', 'B', 'C', 'D', 'E'];
    } else {
      fixedAxis.data = [];
    }
  }

  return fixedAxis;
};

// 🎯 修复系列配置
const fixSeries = (series: any): any => {
  const fixedSeries = { ...series };

  // 修复 type - 将中文描述转换为有效的ECharts类型
  const typeMapping: { [key: string]: string } = {
    '时间序列分析图、学习曲线图': 'line',
    '柱状图': 'bar',
    '折线图': 'line',
    '饼图': 'pie',
    '散点图': 'scatter',
    '面积图': 'line',
    '堆叠图': 'bar',
    '百分比堆叠图': 'bar'
  };

  if (fixedSeries.type && typeof fixedSeries.type === 'string') {
    // 检查是否是中文描述
    if (typeMapping[fixedSeries.type]) {
      fixedSeries.type = typeMapping[fixedSeries.type];
    } else if (!['bar', 'line', 'pie', 'scatter', 'effectScatter', 'radar', 'tree', 'treemap', 'sunburst', 'boxplot', 'candlestick', 'heatmap', 'map', 'parallel', 'lines', 'graph', 'sankey', 'funnel', 'gauge', 'pictorialBar', 'themeRiver', 'custom'].includes(fixedSeries.type)) {
      // 如果不是有效的ECharts类型，默认使用bar
      console.warn(`⚠️ 无效的series类型: ${fixedSeries.type}，使用默认类型 bar`);
      fixedSeries.type = 'bar';
    }
  } else {
    fixedSeries.type = 'bar';
  }

  // 修复 data
  if (!fixedSeries.data || !Array.isArray(fixedSeries.data) || fixedSeries.data.length === 0) {
    if (fixedSeries.type === 'pie') {
      fixedSeries.data = [
        { name: '类别A', value: 10 },
        { name: '类别B', value: 20 },
        { name: '类别C', value: 30 }
      ];
    } else {
      fixedSeries.data = [10, 20, 15, 25, 18];
    }
  }

  // 确保有name
  if (!fixedSeries.name) {
    fixedSeries.name = '数据系列';
  }

  return fixedSeries;
};

// ECharts图表渲染组件
interface EChartsRendererProps {
  eChartsConfig: EChartsConfig;
}

// ECharts表格展示组件
interface EChartsTableProps {
  data: any;
}

const EChartsRenderer: React.FC<EChartsRendererProps> = ({ eChartsConfig }) => {
  console.log('🎨 EChartsRenderer 组件渲染，接收配置:', eChartsConfig);

  // 防御性检查：确保配置有效
  if (!eChartsConfig || !eChartsConfig.option) {
    console.error('❌ EChartsRenderer 接收到无效配置:', eChartsConfig);
    return (
      <div className="my-4 bg-red-50 rounded-lg border border-red-200 p-4">
        <div className="text-red-600 text-sm">
          <p className="font-medium">图表配置错误</p>
          <p>ECharts配置无效或为空</p>
        </div>
      </div>
    );
  }

  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const optionStringRef = useRef<string>('');
  const isMountedRef = useRef(true);

  // 使用 useMemo 缓存 option 的字符串表示，避免频繁变化
  const optionString = useMemo(() => {
    try {
      return JSON.stringify(eChartsConfig.option);
    } catch (e) {
      console.error('❌ 序列化ECharts配置失败:', e);
      return '';
    }
  }, [eChartsConfig.option]);

  useEffect(() => {
    console.log('🎨 EChartsRenderer useEffect 触发，配置变化检测:', {
      currentOptionString: optionStringRef.current,
      newOptionString: optionString,
      hasInstance: !!chartInstance.current,
      hasRef: !!chartRef.current,
      hasEcharts: !!window.echarts,
      hasOption: !!eChartsConfig.option
    });

    // 如果配置没有实质性变化，跳过重新初始化
    if (optionStringRef.current === optionString && chartInstance.current && optionString) {
      console.log('⏭️ ECharts配置未变化，跳过重新初始化');
      setIsLoading(false);
      return;
    }

    // 如果配置为空或无效，跳过初始化
    if (!optionString || !eChartsConfig.option) {
      console.log('⚠️ ECharts配置无效，跳过初始化');
      setError('ECharts配置无效');
      setIsLoading(false);
      return;
    }

    // 简化逻辑：每次配置变化时都重新初始化
    const initializeChart = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // 等待DOM准备就绪
        if (!chartRef.current) {
          console.log('⏳ 等待DOM元素准备就绪...');
          return;
        }

        // 检查ECharts库是否加载
        if (!window.echarts) {
          console.log('⏳ 等待ECharts库加载...');
          // 等待ECharts加载
          await new Promise((resolve, reject) => {
            const checkECharts = () => {
              if (window.echarts) {
                resolve(void 0);
              } else {
                setTimeout(checkECharts, 100);
              }
            };
            checkECharts();

            // 10秒超时
            setTimeout(() => reject(new Error('ECharts库加载超时')), 10000);
          });
        }

        console.log('📊 开始初始化ECharts图表');

        // 清理现有实例 - 更安全的方式
        if (chartInstance.current) {
          try {
            // 检查实例是否仍然有效
            if (typeof chartInstance.current.dispose === 'function') {
              // 在dispose之前先检查DOM节点是否存在
              try {
                const domElement = chartInstance.current.getDom();
                if (domElement && document.contains(domElement)) {
                  chartInstance.current.dispose();
                } else {
                  console.log('⏭️ DOM节点已被移除，跳过dispose');
                }
              } catch (domCheckError) {
                // 如果无法检查DOM，直接dispose
                chartInstance.current.dispose();
              }
            }
          } catch (err) {
            console.warn('清理旧实例时出错（可忽略）:', err);
          } finally {
            chartInstance.current = null;
          }
        }

        // 🎯 验证和修复ECharts配置
        const fixedOption = fixEChartsOption(eChartsConfig.option);
        console.log('📊 修复后的ECharts配置:', fixedOption);

        // 创建新实例
        chartInstance.current = window.echarts.init(chartRef.current, null, {
          renderer: 'canvas'
        });

        console.log('📊 设置ECharts配置:', fixedOption);
        chartInstance.current.setOption(fixedOption, true);

        console.log('✅ ECharts图表初始化成功');

        // 检查组件是否仍然挂载
        if (isMountedRef.current) {
          setIsLoading(false);
          // 更新引用
          optionStringRef.current = optionString;
        }

        // 处理窗口大小变化
        const handleResize = () => {
          if (chartInstance.current && isMountedRef.current) {
            chartInstance.current.resize();
          }
        };

        window.addEventListener('resize', handleResize);

        return () => {
          window.removeEventListener('resize', handleResize);
        };

      } catch (error) {
        console.error('❌ ECharts初始化失败:', error);
        if (isMountedRef.current) {
          setError(`ECharts错误: ${error instanceof Error ? error.message : '未知错误'}`);
          setIsLoading(false);
        }
      }
    };

    // 执行初始化
    initializeChart();

    // 清理函数 - 组件卸载时的安全清理
    return () => {
      console.log('🧹 EChartsRenderer 组件卸载，开始清理');
      isMountedRef.current = false; // 标记组件已卸载

      if (chartInstance.current) {
        try {
          // 检查实例和DOM状态
          if (typeof chartInstance.current.dispose === 'function') {
            try {
              const domElement = chartInstance.current.getDom();
              if (domElement && document.contains(domElement)) {
                console.log('🧹 执行dispose清理DOM');
                chartInstance.current.dispose();
              } else {
                console.log('⏭️ DOM节点不存在，跳过dispose');
              }
            } catch (domCheckError) {
              // 如果无法检查DOM状态，尝试直接dispose
              console.log('⚠️ 无法检查DOM状态，尝试直接dispose');
              chartInstance.current.dispose();
            }
          }
        } catch (err) {
          console.warn('组件卸载时清理实例出错（可忽略）:', err);
        } finally {
          chartInstance.current = null;
          console.log('✅ EChartsRenderer 清理完成');
        }
      }
    };
  }, [optionString, eChartsConfig]); // 依赖配置变化


  const chartStyle = {
    width: eChartsConfig.width || '100%',
    height: eChartsConfig.height || '600px', // 增大默认高度
    minHeight: '400px', // 增大最小高度
    maxHeight: '800px', // 添加最大高度限制
    overflow: 'auto' // 添加滚动
  };

  if (error) {
    return (
      <div className="my-4 bg-red-50 rounded-lg border border-red-200 p-4">
          <div className="text-red-600 text-sm">
            <p className="font-medium">图表渲染错误</p>
            <p>{error}</p>
          </div>
        </div>
    );
  }

  if (isLoading) {
    return (
      <div className="my-4 bg-gray-50 rounded-lg border p-4">
        <div className="w-full overflow-x-auto overflow-y-auto" style={{ maxHeight: '600px' }}>
          <div
            ref={chartRef}
            style={chartStyle}
            className="w-full min-w-[600px] flex items-center justify-center"
          >
            <div className="text-gray-500">正在加载图表...</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="my-4 bg-white rounded-lg border p-4 max-w-full">
      <div className="w-full overflow-x-auto overflow-y-auto" style={{ maxHeight: '600px', maxWidth: '100%' }}>
        <div
          ref={chartRef}
          style={chartStyle}
          className="w-full min-w-[600px]" // 确保最小宽度，防止图表被压缩太小
        />
      </div>
    </div>
  );
};

// ECharts数据表格展示组件
const EChartsTable: React.FC<EChartsTableProps> = ({ data }) => {
  console.log('📊 EChartsTable 组件渲染，接收数据:', data);

  if (!data || !data.series || !Array.isArray(data.series)) {
    return (
      <div className="my-4 bg-red-50 rounded-lg border border-red-200 p-4">
        <div className="text-red-600 text-sm">
          <p className="font-medium">数据格式错误</p>
          <p>ECharts数据无效或不包含series</p>
        </div>
      </div>
    );
  }

  const title = data.title?.text || '数据表';
  const xAxisData = data.xAxis?.data || [];
  const series = data.series;

  // 构建表格数据
  const tableData: any[][] = [];

  // 添加表头
  const headers = ['类别', ...series.map((s: any) => s.name || `系列${series.indexOf(s) + 1}`)];
  tableData.push(headers);

  // 添加数据行
  xAxisData.forEach((xValue: any, index: number) => {
    const row = [String(xValue)];
    series.forEach((s: any) => {
      const value = s.data && s.data[index] !== undefined ? s.data[index] : '-';
      row.push(String(value));
    });
    tableData.push(row);
  });

  return (
    <div className="my-4 bg-white rounded-lg border border-gray-200 overflow-hidden max-w-full">
      <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
        {data.xAxis?.name && (
          <p className="text-sm text-gray-600 mt-1">X轴: {data.xAxis.name}</p>
        )}
        {data.yAxis?.name && (
          <p className="text-sm text-gray-600">Y轴: {data.yAxis.name}</p>
        )}
      </div>
      <div className="overflow-x-auto overflow-y-auto" style={{ maxHeight: '600px', maxWidth: '100%' }}>
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {headers.map((header, index) => (
                <th
                  key={index}
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {tableData.slice(1).map((row, rowIndex) => (
              <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                {row.map((cell, cellIndex) => (
                  <td
                    key={cellIndex}
                    className={`px-6 py-4 whitespace-nowrap text-sm ${
                      cellIndex === 0
                        ? 'font-medium text-gray-900'
                        : 'text-gray-500'
                    }`}
                  >
                    {cellIndex === 0 ? cell : Number(cell).toLocaleString()}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 text-sm text-gray-600">
        <p>共 {tableData.length - 1} 行数据 × {headers.length} 列</p>
      </div>
    </div>
  );
};

interface RichContentProps {
  content: string | Array<{type: string; content: string}>;
  className?: string;
}

interface ImageConfig {
  src: string;
  alt?: string;
  width?: string | number;
  height?: string | number;
}

interface EChartsConfig {
  option: any;
  width?: string | number;
  height?: string | number;
}

const RichContent: React.FC<RichContentProps> = ({ content, className = '' }) => {
  // 将列表格式的 content 转换为字符串格式
  const normalizeContent = (content: string | Array<{type: string; content: string}>): string => {
    console.log('🔄 RichContent normalizeContent 输入:', {
      isString: typeof content === 'string',
      isArray: Array.isArray(content),
      contentType: typeof content,
      contentLength: Array.isArray(content) ? content.length : 'N/A'
    });
    
    // 如果已经是字符串，直接返回
    if (typeof content === 'string') {
      console.log('✅ 内容已经是字符串格式，直接返回');
      return content;
    }
    
    // 如果是列表格式，将其转换为字符串
    if (Array.isArray(content)) {
      console.log('🔄 内容为列表格式，开始转换，列表长度:', content.length);
      const normalized = content.map(item => {
        const { type, content: itemContent } = item;
        console.log('🔄 处理列表项:', { type, contentLength: typeof itemContent === 'string' ? itemContent.length : 'N/A' });
        // 根据类型添加相应的前缀标记
        if (type === 'echarts') {
          return `[ECHARTS]\n${itemContent}`;
        } else if (type === 'html_table') {
          return `[HTML_TABLE]\n${itemContent}`;
        } else if (type === 'text') {
          return itemContent;
        } else {
          return itemContent;
        }
      }).join('\n\n');
      console.log('✅ 列表格式转换完成，结果长度:', normalized.length);
      return normalized;
    }
    
    console.log('⚠️ 内容格式未知，转换为字符串');
    return String(content);
  };

  // 解析消息内容，支持图片、HTML表格和echarts图表
  const parseContent = (text: string): { type: 'echarts' | 'echarts_table' | 'image' | 'html' | 'text' | 'echarts_with_text' | 'html_with_text' | 'mixed'; data: any; textContent?: string; parts?: Array<{type: string; data: any}> } => {
    // 如果内容为空，返回空文本
    if (!text || typeof text !== 'string') {
      return { type: 'text', data: '' };
    }

    console.log('🔍 开始解析内容，原始文本长度:', text.length);
    console.log('🔍 原始文本预览:', text.substring(0, 300) + (text.length > 300 ? '...' : ''));
    console.log('🔍 检查是否包含option关键字:', text.includes('option'));
    console.log('🔍 检查是否包含代码块:', text.includes('```'));

    const trimmedText = text.trim();

    // 检查是否可能是流式内容（包含流式标记或不完整的JSON）
    const isStreamingContent = text.includes('正在生成') ||
                               text.includes('[object Object]') ||
                               (trimmedText.includes('{') && !trimmedText.includes('}'));

    // 首先检查是否包含多个类型标记（混合内容）
    const allTypeMatches = Array.from(text.matchAll(/\[(SCHEMA|ECHARTS|HTML_TABLE)\]/gi));
    if (allTypeMatches.length > 1) {
      console.log('🎯 检测到多个类型标记，数量:', allTypeMatches.length);
      // 解析多个内容块
      const parts: Array<{type: string; data: any}> = [];
      
      // 检查第一个标记之前是否有未标记的文本
      const firstMatch = allTypeMatches[0];
      const beforeFirstText = text.substring(0, firstMatch.index!).trim();
      if (beforeFirstText && beforeFirstText.length > 0) {
        console.log('📝 检测到第一个标记之前的文本，长度:', beforeFirstText.length);
        // 添加标记前的文本（无论是否有markdown特征，只要有内容就添加）
        parts.push({ type: 'text', data: beforeFirstText });
      }
      
      for (let i = 0; i < allTypeMatches.length; i++) {
        const match = allTypeMatches[i];
        const type = match[1].toLowerCase();
        const startIndex = match.index! + match[0].length;
        const endIndex = i < allTypeMatches.length - 1 ? allTypeMatches[i + 1].index! : text.length;
        const content = text.substring(startIndex, endIndex).trim();
        
        // 解析每个内容块
        if (type === 'echarts') {
          try {
            let config = null;
            let remainingText = '';
            if (content.startsWith('option=')) {
              const dictStr = content.replace(/^option=\s*/, '');
              // 找到完整的字典结束位置
              let braceCount = 0;
              let foundStart = false;
              let optionEnd = -1;
              for (let j = 0; j < dictStr.length; j++) {
                if (dictStr[j] === '{') {
                  braceCount++;
                  foundStart = true;
                } else if (dictStr[j] === '}') {
                  braceCount--;
                  if (foundStart && braceCount === 0) {
                    optionEnd = j + 1;
                    break;
                  }
                }
              }
              if (optionEnd > 0) {
                const optionStr = dictStr.substring(0, optionEnd);
                const jsonStr = optionStr
                  .replace(/'/g, '"')
                  .replace(/True/g, 'true')
                  .replace(/False/g, 'false')
                  .replace(/None/g, 'null');
                config = JSON.parse(jsonStr);
                // 🎯 修复双重包装：如果解析的JSON已经包含option字段，直接使用它
                if (config && typeof config === 'object' && config.option) {
                  parts.push({ type: 'echarts', data: { option: config.option } });
                } else {
                  parts.push({ type: 'echarts', data: { option: config } });
                }
                
                // 提取剩余文本（markdown等）
                remainingText = content.substring(content.indexOf('option=') + 7 + optionEnd).trim();
                if (remainingText && remainingText.length > 0) {
                  // 检查剩余文本是否包含markdown特征或足够长
                  const hasMarkdown = /^#{1,6}\s+|^\*\s+|^\d+\.\s+|^\-\s+|\*\*[^*]+\*\*|`[^`]+`/m.test(remainingText);
                  if (hasMarkdown || remainingText.length > 20) {
                    parts.push({ type: 'text', data: remainingText });
                  }
                }
              } else {
                // 如果没有找到完整的option配置，检查整个内容是否是文本
                const trimmedContent = content.trim();
                if (trimmedContent && trimmedContent.length > 0) {
                  const hasMarkdown = /^#{1,6}\s+|^\*\s+|^\d+\.\s+|^\-\s+|\*\*[^*]+\*\*|`[^`]+`/m.test(trimmedContent);
                  if (hasMarkdown || trimmedContent.length > 20) {
                    parts.push({ type: 'text', data: trimmedContent });
                  }
                }
              }
            } else {
              // 🎯 如果没有option=前缀，尝试解析为JSON（可能是{"option": {...}}格式）
              try {
                const trimmedContent = content.trim();
                if (trimmedContent && trimmedContent.length > 0) {
                  // 尝试解析为JSON
                  const parsedJson = JSON.parse(trimmedContent);
                  // 如果解析成功且包含option字段，作为ECharts处理
                  if (parsedJson && typeof parsedJson === 'object' && parsedJson.option) {
                    console.log('✅ 混合内容中检测到ECharts JSON（已包含option字段）');
                    parts.push({ type: 'echarts', data: { option: parsedJson.option } });
                  } else {
                    // 否则作为文本处理
                    const hasMarkdown = /^#{1,6}\s+|^\*\s+|^\d+\.\s+|^\-\s+|\*\*[^*]+\*\*|`[^`]+`/m.test(trimmedContent);
                    if (hasMarkdown || trimmedContent.length > 20) {
                      parts.push({ type: 'text', data: trimmedContent });
                    }
                  }
                }
              } catch (jsonParseError) {
                // JSON解析失败，作为文本处理
                const trimmedContent = content.trim();
                if (trimmedContent && trimmedContent.length > 0) {
                  const hasMarkdown = /^#{1,6}\s+|^\*\s+|^\d+\.\s+|^\-\s+|\*\*[^*]+\*\*|`[^`]+`/m.test(trimmedContent);
                  if (hasMarkdown || trimmedContent.length > 20) {
                    parts.push({ type: 'text', data: trimmedContent });
                  }
                }
              }
            }
          } catch (e) {
            console.warn('解析ECharts块失败:', e);
            // 如果解析失败，尝试将内容作为文本处理
            const trimmedContent = content.trim();
            if (trimmedContent && trimmedContent.length > 0) {
              const hasMarkdown = /^#{1,6}\s+|^\*\s+|^\d+\.\s+|^\-\s+|\*\*[^*]+\*\*|`[^`]+`/m.test(trimmedContent);
              if (hasMarkdown || trimmedContent.length > 20) {
                parts.push({ type: 'text', data: trimmedContent });
              }
            }
          }
        } else if (type === 'html_table') {
          // 查找HTML表格的结束位置（找到第一个完整的表格，包括可能的<p>标签）
          // 使用正则表达式匹配完整的表格结构
          const tableMatch = content.match(/<table[\s\S]*?<\/table>/i);
          if (tableMatch) {
            const tableEndIndex = content.indexOf(tableMatch[0]) + tableMatch[0].length;
            // 检查表格后面是否有<p>标签（如"注：数据共..."）
            const afterTable = content.substring(tableEndIndex).trim();
            const pTagMatch = afterTable.match(/^<p[^>]*>[\s\S]*?<\/p>/i);
            let htmlEndIndex = tableEndIndex;
            if (pTagMatch) {
              htmlEndIndex += pTagMatch[0].length;
            }
            const htmlContent = content.substring(0, htmlEndIndex).trim();
            if (htmlContent) {
              parts.push({ type: 'html', data: htmlContent });
            }
            
            // 检查是否有剩余文本（markdown等）
            const remainingText = content.substring(htmlEndIndex).trim();
            if (remainingText && remainingText.length > 0) {
              // 检查剩余文本是否包含markdown特征
              const hasMarkdown = /^#{1,6}\s+|^\*\s+|^\d+\.\s+|^\-\s+|\*\*[^*]+\*\*|`[^`]+`/m.test(remainingText);
              if (hasMarkdown || remainingText.length > 50) {
                parts.push({ type: 'text', data: remainingText });
              }
            }
          } else {
            // 如果没有找到表格标签，整个内容作为HTML处理
            if (content.trim()) {
              parts.push({ type: 'html', data: content.trim() });
            }
          }
        } else if (type === 'schema') {
          parts.push({ type: 'text', data: content });
        }
      }
      
      // 检查最后是否有未标记的文本
      const lastMatch = allTypeMatches[allTypeMatches.length - 1];
      const lastMatchEnd = lastMatch.index! + lastMatch[0].length;
      const lastContent = text.substring(lastMatchEnd).trim();
      if (lastContent && lastContent.length > 0) {
        // 检查是否包含HTML表格（无标记）
        const tableMatch = lastContent.match(/<table[\s\S]*?<\/table>/i);
        if (tableMatch) {
          const tableEndIndex = lastContent.indexOf(tableMatch[0]) + tableMatch[0].length;
          // 检查表格后面是否有<p>标签
          const afterTable = lastContent.substring(tableEndIndex).trim();
          const pTagMatch = afterTable.match(/^<p[^>]*>[\s\S]*?<\/p>/i);
          let htmlEndIndex = tableEndIndex;
          if (pTagMatch) {
            htmlEndIndex += pTagMatch[0].length;
          }
          const htmlContent = lastContent.substring(0, htmlEndIndex).trim();
          if (htmlContent) {
            parts.push({ type: 'html', data: htmlContent });
          }
          const remainingText = lastContent.substring(htmlEndIndex).trim();
          if (remainingText && remainingText.length > 0) {
            // 检查剩余文本是否包含markdown特征
            const hasMarkdown = /^#{1,6}\s+|^\*\s+|^\d+\.\s+|^\-\s+|\*\*[^*]+\*\*|`[^`]+`/m.test(remainingText);
            if (hasMarkdown || remainingText.length > 20) {
              parts.push({ type: 'text', data: remainingText });
            }
          }
        } else {
          // 没有表格，检查是否是markdown或其他文本
          // 检查是否包含markdown特征
          const hasMarkdown = /^#{1,6}\s+|^\*\s+|^\d+\.\s+|^\-\s+|\*\*[^*]+\*\*|`[^`]+`/m.test(lastContent);
          // 或者内容较长（可能是文本内容）
          if (hasMarkdown || lastContent.length > 20) {
            parts.push({ type: 'text', data: lastContent });
          }
        }
      }
      
      // 检查标记之间的未标记文本（markdown等）
      // 注意：由于每个标记后的内容已经包含了到下一个标记之前的所有内容，
      // 所以这里主要处理的是在解析echarts/html_table时可能遗漏的文本
      // 实际上，这部分逻辑已经在解析每个类型时处理了剩余文本
      
      if (parts.length > 0) {
        console.log('✅ 解析到混合内容，parts数量:', parts.length);
        return { type: 'mixed', data: null, parts };
      }
    }
    
    // 检查是否包含单个类型标记（新的流式格式）
    const typeMatch = text.match(/\[SCHEMA\]|\[ECHARTS\]|\[HTML_TABLE\]/i);
    if (typeMatch) {
      const type = typeMatch[0].toLowerCase().replace(/\[|\]/g, '');
      console.log('🎯 检测到单个类型标记:', type);

      // 检查标记之前是否有文本
      const beforeText = text.substring(0, typeMatch.index!).trim();
      const contentStart = text.indexOf(typeMatch[0]) + typeMatch[0].length;
      let content = text.substring(contentStart).trim();
      
      // 如果标记之前有文本，需要返回混合类型
      if (beforeText && beforeText.length > 0) {
        console.log('📝 检测到单个标记之前的文本，长度:', beforeText.length);
        const parts: Array<{type: string; data: any}> = [];
        // 添加标记前的文本
        parts.push({ type: 'text', data: beforeText });
        
        // 处理标记后的内容
        if (type === 'html_table') {
          // HTML表格类型
          const tableMatch = content.match(/<table[\s\S]*?<\/table>/i);
          if (tableMatch) {
            const tableEndIndex = content.indexOf(tableMatch[0]) + tableMatch[0].length;
            const afterTable = content.substring(tableEndIndex).trim();
            const pTagMatch = afterTable.match(/^<p[^>]*>[\s\S]*?<\/p>/i);
            let htmlEndIndex = tableEndIndex;
            if (pTagMatch) {
              htmlEndIndex += pTagMatch[0].length;
            }
            const htmlContent = content.substring(0, htmlEndIndex).trim();
            if (htmlContent) {
              parts.push({ type: 'html', data: htmlContent });
            }
            // 检查表格后是否有剩余文本
            const remainingText = content.substring(htmlEndIndex).trim();
            if (remainingText && remainingText.length > 0) {
              const hasMarkdown = /^#{1,6}\s+|^\*\s+|^\d+\.\s+|^\-\s+|\*\*[^*]+\*\*|`[^`]+`/m.test(remainingText);
              if (hasMarkdown || remainingText.length > 20) {
                parts.push({ type: 'text', data: remainingText });
              }
            }
          } else {
            if (content.trim()) {
              parts.push({ type: 'html', data: content.trim() });
            }
          }
        } else if (type === 'echarts') {
          // ECharts类型，尝试解析
          try {
            if (content.startsWith('option=')) {
              const dictStr = content.replace(/^option=\s*/, '');
              let braceCount = 0;
              let foundStart = false;
              let optionEnd = -1;
              for (let j = 0; j < dictStr.length; j++) {
                if (dictStr[j] === '{') {
                  braceCount++;
                  foundStart = true;
                } else if (dictStr[j] === '}') {
                  braceCount--;
                  if (foundStart && braceCount === 0) {
                    optionEnd = j + 1;
                    break;
                  }
                }
              }
              if (optionEnd > 0) {
                const optionStr = dictStr.substring(0, optionEnd);
                const jsonStr = optionStr
                  .replace(/'/g, '"')
                  .replace(/True/g, 'true')
                  .replace(/False/g, 'false')
                  .replace(/None/g, 'null');
                const config = JSON.parse(jsonStr);
                // 🎯 修复双重包装：如果解析的JSON已经包含option字段，直接使用它
                if (config && typeof config === 'object' && config.option) {
                  parts.push({ type: 'echarts', data: { option: config.option } });
                } else {
                  parts.push({ type: 'echarts', data: { option: config } });
                }
                
                const remainingText = content.substring(content.indexOf('option=') + 7 + optionEnd).trim();
                if (remainingText && remainingText.length > 0) {
                  const hasMarkdown = /^#{1,6}\s+|^\*\s+|^\d+\.\s+|^\-\s+|\*\*[^*]+\*\*|`[^`]+`/m.test(remainingText);
                  if (hasMarkdown || remainingText.length > 20) {
                    parts.push({ type: 'text', data: remainingText });
                  }
                }
              } else {
                // 解析失败，作为文本处理
                if (content.trim()) {
                  parts.push({ type: 'text', data: content.trim() });
                }
              }
            } else {
              // 🎯 没有option=前缀，尝试解析为JSON（可能是{"option": {...}}格式）
              try {
                const trimmedContent = content.trim();
                if (trimmedContent && trimmedContent.length > 0) {
                  const parsedJson = JSON.parse(trimmedContent);
                  // 如果解析成功且包含option字段，作为ECharts处理
                  if (parsedJson && typeof parsedJson === 'object' && parsedJson.option) {
                    console.log('✅ 单个标记中检测到ECharts JSON（已包含option字段）');
                    parts.push({ type: 'echarts', data: { option: parsedJson.option } });
                  } else {
                    // 否则作为文本处理
                    parts.push({ type: 'text', data: trimmedContent });
                  }
                }
              } catch (jsonParseError) {
                // JSON解析失败，作为文本处理
                if (content.trim()) {
                  parts.push({ type: 'text', data: content.trim() });
                }
              }
            }
          } catch (e) {
            console.warn('解析ECharts块失败:', e);
            // 🎯 即使解析失败，也尝试直接解析JSON（可能是{"option": {...}}格式）
            try {
              const trimmedContent = content.trim();
              if (trimmedContent && trimmedContent.length > 0) {
                const parsedJson = JSON.parse(trimmedContent);
                if (parsedJson && typeof parsedJson === 'object' && parsedJson.option) {
                  console.log('✅ 解析失败后检测到ECharts JSON（已包含option字段）');
                  parts.push({ type: 'echarts', data: { option: parsedJson.option } });
                } else {
                  parts.push({ type: 'text', data: trimmedContent });
                }
              }
            } catch (finalError) {
              // 最终解析失败，作为文本处理
              if (content.trim()) {
                parts.push({ type: 'text', data: content.trim() });
              }
            }
          }
        } else if (type === 'schema') {
          parts.push({ type: 'text', data: content });
        }
        
        if (parts.length > 0) {
          console.log('✅ 解析到混合内容（单个标记+前置文本），parts数量:', parts.length);
          return { type: 'mixed', data: null, parts };
        }
      }

      if (type === 'html_table') {
        // HTML表格类型，检查后面是否还有markdown内容
        console.log('📊 检测到HTML表格内容');
        
        // 查找HTML表格的结束位置（包括可能的</table>和后续的<p>标签）
        // HTML表格通常以</table>结束，后面可能跟着<p>标签
        let htmlEndIndex = -1;
        let htmlContent = '';
        let remainingText = '';
        
        // 查找最后一个</table>标签的位置
        const lastTableEnd = content.lastIndexOf('</table>');
        if (lastTableEnd !== -1) {
          // 查找</table>后面可能的<p>标签
          const afterTable = content.substring(lastTableEnd + 8).trim();
          const pTagMatch = afterTable.match(/^<p[^>]*>[\s\S]*?<\/p>/);
          
          if (pTagMatch) {
            // 包含<p>标签，HTML内容到</p>结束
            htmlEndIndex = lastTableEnd + 8 + pTagMatch[0].length;
            htmlContent = content.substring(0, htmlEndIndex).trim();
            remainingText = content.substring(htmlEndIndex).trim();
          } else {
            // 只有</table>，HTML内容到</table>结束
            htmlEndIndex = lastTableEnd + 8;
            htmlContent = content.substring(0, htmlEndIndex).trim();
            remainingText = content.substring(htmlEndIndex).trim();
          }
        } else {
          // 如果没有找到</table>，尝试查找其他HTML标签的结束
          // 或者整个内容都是HTML
          htmlContent = content;
        }
        
        // 检查剩余文本是否包含markdown内容
        if (remainingText && remainingText.length > 0) {
          // 检查是否包含markdown特征（标题、列表等）
          const hasMarkdown = /^#{1,6}\s+|^\*\s+|^\d+\.\s+|^\-\s+|\*\*[^*]+\*\*|`[^`]+`/m.test(remainingText);
          if (hasMarkdown) {
            console.log('📝 检测到HTML表格后的Markdown内容，长度:', remainingText.length);
            return { 
              type: 'html_with_text', 
              data: htmlContent,
              textContent: remainingText
            };
          }
        }
        
        // 只有HTML表格，没有markdown内容
        return { type: 'html', data: htmlContent || content };
      } else if (type === 'echarts') {
        // 如果是echarts类型，尝试解析多种格式
        try {
          let config = null;
          let echartsContentEnd = -1;
          let remainingText = '';

          // 检查内容是否为空或只是空对象
          if (!content || content.trim() === '' || content.trim() === 'option={}' || content.trim() === 'option={}') {
            console.log('⚠️ ECharts内容为空或无效，跳过');
            return { type: 'text', data: '' };
          }

          // 查找 ECharts 配置的结束位置（option=...} 的结束位置）
          if (content.startsWith('option=')) {
            // 找到完整的字典结束位置（匹配最外层的 {}）
            let braceCount = 0;
            let foundStart = false;
            let optionStart = content.indexOf('option=') + 7; // 'option=' 的长度
            
            // 从 option= 后面开始查找
            for (let i = optionStart; i < content.length; i++) {
              if (content[i] === '{') {
                braceCount++;
                foundStart = true;
              } else if (content[i] === '}') {
                braceCount--;
                if (foundStart && braceCount === 0) {
                  echartsContentEnd = i + 1;
                  break;
                }
              }
            }
            
            // 提取 ECharts 配置部分
            let echartsStr = '';
            if (echartsContentEnd > 0) {
              echartsStr = content.substring(0, echartsContentEnd).trim();
              // 提取剩余文本部分
              if (echartsContentEnd < content.length) {
                remainingText = content.substring(echartsContentEnd).trim();
              }
            } else {
              // 如果没有找到完整的结束位置，尝试使用整个内容（可能是流式传输中）
              echartsStr = content;
            }
            
            // 移除option=前缀
            const dictStr = echartsStr.replace(/^option=\s*/, '');
            
            // 检查是否为空对象
            if (dictStr.trim() === '{}' || dictStr.trim() === '') {
              console.log('⚠️ ECharts配置为空对象，跳过');
              // 如果有剩余文本，返回文本类型
              if (remainingText && remainingText.length > 0) {
                return { type: 'text', data: remainingText };
              }
              return { type: 'text', data: '' };
            }
            
            // 转换Python字典语法为JSON
            const jsonStr = dictStr
              .replace(/'/g, '"')  // 单引号转双引号
              .replace(/True/g, 'true')  // Python True转true
              .replace(/False/g, 'false')  // Python False转false
              .replace(/None/g, 'null');  // Python None转null

            config = JSON.parse(jsonStr);
            
            // 验证配置是否有效（至少包含一些ECharts属性）
            if (!config || (typeof config === 'object' && Object.keys(config).length === 0)) {
              console.log('⚠️ ECharts配置为空对象，跳过');
              if (remainingText && remainingText.length > 0) {
                return { type: 'text', data: remainingText };
              }
              return { type: 'text', data: '' };
            }
            
            console.log('✅ Python字典格式解析成功');
            
            // 如果有剩余文本，返回组合类型
            if (remainingText && remainingText.length > 0) {
              console.log('📝 检测到ECharts配置后的文本内容，长度:', remainingText.length);
              return { 
                type: 'echarts_with_text', 
                data: { option: config },
                textContent: remainingText
              };
            } else {
              return { type: 'echarts', data: { option: config } };
            }
          } else {
            // 尝试直接JSON解析
            try {
              config = JSON.parse(content);
              // 🎯 修复双重包装：如果解析的JSON已经包含option字段，直接使用它
              if (config && typeof config === 'object' && config.option) {
                console.log('✅ ECharts配置解析成功（已包含option字段）:', config.option?.title?.text || '无标题');
                return { type: 'echarts', data: { option: config.option } };
              }
              // 验证配置是否有效
              if (!config || (typeof config === 'object' && Object.keys(config).length === 0)) {
                console.log('⚠️ ECharts配置为空对象，跳过');
                return { type: 'text', data: '' };
              }
              console.log('✅ ECharts配置解析成功:', config.title?.text || '无标题');
              return { type: 'echarts', data: { option: config } };
            } catch (jsonError) {
              throw new Error('不支持的格式');
            }
          }
        } catch (e) {
          console.log('⚠️ ECharts内容解析失败，回退到文本:', e);
          return { type: 'text', data: content };
        }
      } else if (type === 'schema') {
        // schema类型直接显示为文本
        console.log('📊 Schema内容，显示为文本');
        return { type: 'text', data: content };
      }
    }

    // 检查是否包含明确的ECharts关键字
    const hasEChartsKeywords = /\b(option|echarts?|chart|series|xAxis|yAxis|tooltip|legend|grid)\b/i.test(trimmedText);

    // 特殊处理：检查是否包含option=格式的ECharts数据（历史记录兼容）
    if (trimmedText.includes('option=')) {
      console.log('🎯 检测到option=格式的ECharts数据');

      // 尝试提取option=...}部分（找到最后一个完整的字典）
      const optionMatch = trimmedText.match(/option=\s*(\{[\s\S]*\})(?:\s*\}?\s*)?/);
      if (optionMatch) {
        let optionStr = optionMatch[1];
        console.log('📄 提取的option字符串长度:', optionStr.length);
        console.log('📄 原始option字符串预览:', optionStr.substring(0, 100) + '...');

        // 清理字符串：移除末尾可能的多余字符
        optionStr = optionStr.trim();

        try {
          // 转换Python字典语法为JSON
          const jsonStr = optionStr
            .replace(/'/g, '"')  // 单引号转双引号
            .replace(/True/g, 'true')  // Python True转true
            .replace(/False/g, 'false')  // Python False转false
            .replace(/None/g, 'null');  // Python None转null

          console.log('🔧 转换后的JSON预览:', jsonStr.substring(0, 100) + '...');

          const config = JSON.parse(jsonStr);
          // 🎯 修复双重包装：如果解析的JSON已经包含option字段，直接使用它
          if (config && typeof config === 'object' && config.option) {
            console.log('✅ 历史记录ECharts配置解析成功（已包含option字段）:', config.option?.title?.text || '无标题');
            console.log('📊 将显示为完整的ECharts图表');
            return { type: 'echarts', data: { option: config.option } };
          }
          console.log('✅ 历史记录ECharts配置解析成功:', config.title?.text || '无标题');

          // 总是显示为完整的ECharts图表，而不是表格
          console.log('📊 将显示为完整的ECharts图表');
          return { type: 'echarts', data: { option: config } };
        } catch (e) {
          console.log('⚠️ 历史记录ECharts解析失败:', e);
          // 如果解析失败，继续其他解析逻辑
        }
      } else {
        console.log('⚠️ 未能匹配option字符串模式');
      }
    }

    // 检查是否包含HTML表格（没有标记的情况）
    // 查找 <table> 标签
    const tableMatch = trimmedText.match(/<table[\s\S]*?<\/table>/i);
    if (tableMatch) {
      console.log('📊 检测到HTML表格（无标记）');
      const tableEndIndex = trimmedText.indexOf(tableMatch[0]) + tableMatch[0].length;
      
      // 检查表格后面是否有<p>标签（如"注：数据共..."）
      let htmlEndIndex = tableEndIndex;
      const afterTable = trimmedText.substring(tableEndIndex).trim();
      const pTagMatch = afterTable.match(/^<p[^>]*>[\s\S]*?<\/p>/i);
      if (pTagMatch) {
        htmlEndIndex = tableEndIndex + pTagMatch[0].length;
      }
      
      const htmlContent = trimmedText.substring(0, htmlEndIndex).trim();
      const remainingText = trimmedText.substring(htmlEndIndex).trim();
      
      // 检查剩余文本是否包含markdown内容
      if (remainingText && remainingText.length > 0) {
        const hasMarkdown = /^#{1,6}\s+|^\*\s+|^\d+\.\s+|^\-\s+|\*\*[^*]+\*\*|`[^`]+`/m.test(remainingText);
        if (hasMarkdown) {
          console.log('📝 检测到HTML表格后的Markdown内容（无标记），长度:', remainingText.length);
          return { 
            type: 'html_with_text', 
            data: htmlContent,
            textContent: remainingText
          };
        }
      }
      
      // 只有HTML表格，没有markdown内容
      return { type: 'html', data: htmlContent };
    }

    // 如果不包含ECharts关键字，且内容较长（可能是结构化文本），直接返回文本
    if (!hasEChartsKeywords && trimmedText.length > 1000) {
      console.log('📄 检测到长文本且无ECharts关键字，返回文本格式');
      return { type: 'text', data: text };
    }

    if (isStreamingContent) {
      console.log('🔄 检测到流式内容，跳过ECharts解析');
      return { type: 'text', data: text };
    }

    // 1. 检测ECharts配置
    try {
      let config = null;
      let extractedConfig = null;

      console.log('🔍 开始检测ECharts配置，文本长度:', trimmedText.length);

      // 方法1：查找代码块中的完整配置
      const codeBlockMatch = trimmedText.match(/```(?:json|echarts|javascript)?\s*([\s\S]*?)\s*```/);
      if (codeBlockMatch) {
        console.log('🔍 检测到代码块');
        const codeContent = codeBlockMatch[1].trim();

        // 检查代码块是否包含option = {...}格式
        const optionInBlock = codeContent.match(/option\s*=\s*({[\s\S]*?});?\s*$/);
        if (optionInBlock) {
          console.log('🚀 代码块中找到option格式');
          extractedConfig = optionInBlock[1];
        } else if (codeContent.startsWith('{') && codeContent.endsWith('}')) {
          console.log('📄 代码块中找到JSON对象');
          extractedConfig = codeContent;
        }
      }

      // 方法2：查找文本中的option = {...}格式
      if (!extractedConfig) {
        const optionMatch = trimmedText.match(/option\s*=\s*({[\s\S]*?});?\s*$/);
        if (optionMatch) {
          console.log('🚀 文本中找到option格式');
          extractedConfig = optionMatch[1];
        }
      }

      // 方法3：查找纯JSON对象
      if (!extractedConfig) {
        if (trimmedText.startsWith('{') && trimmedText.endsWith('}')) {
          console.log('📄 检测到纯JSON格式');
          extractedConfig = trimmedText.replace(/;+\s*$/, '');
        } else {
          // 查找文本中的JSON对象
          const jsonMatch = trimmedText.match(/{[\s\S]*?}(?:\s*;?\s*$)?/);
          if (jsonMatch) {
            console.log('🔍 找到可能的JSON对象');
            extractedConfig = jsonMatch[0].replace(/;+\s*$/, '');
          }
        }
      }

      // 如果找到了配置，尝试解析
      if (extractedConfig) {
        console.log('📝 准备解析配置，长度:', extractedConfig.length);

        // 清理JSON：为未引用的键添加引号
        let cleanedJson = extractedConfig
          .replace(/([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:/g, '$1"$2":')
          .replace(/;\s*$/, ''); // 移除末尾分号

        console.log('🧹 清理后的JSON预览:', cleanedJson.substring(0, 200) + '...');

        try {
          config = JSON.parse(cleanedJson);
          console.log('✅ JSON解析成功，配置对象:', config);
        } catch (parseErr) {
          console.log('⚠️ JSON解析失败:', parseErr);
          console.log('❌ 失败的内容:', cleanedJson);

          // 尝试更简单的清理
          try {
            const simplerJson = extractedConfig
              .replace(/([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:/g, '$1"$2":')
              .replace(/,\s*}/g, '}') // 移除尾随逗号
              .replace(/;\s*$/, '');

            config = JSON.parse(simplerJson);
            console.log('✅ 简化清理后解析成功');
          } catch (simpleErr) {
            console.log('❌ 简化清理也失败:', simpleErr);
          }
        }
      }

      // 检查配置是否为ECharts
      if (config) {
        const hasEChartsProperties = (
          (config.title && typeof config.title === 'object') ||
          (config.series && Array.isArray(config.series)) ||
          config.xAxis || config.yAxis ||
          config.legend || config.tooltip ||
          config.grid || config.dataZoom
        );

        const hasMultipleEChartsProps = [
          config.title, config.series, config.xAxis, config.yAxis,
          config.legend, config.tooltip, config.grid
        ].filter(prop => prop !== undefined).length >= 2;

        if (hasEChartsProperties && hasMultipleEChartsProps) {
          // 🎯 修复双重包装：如果解析的JSON已经包含option字段，直接使用它
          if (config && typeof config === 'object' && config.option) {
            console.log('✅ 检测到有效的ECharts配置（已包含option字段）:', config.option?.title?.text || '无标题');
            return { type: 'echarts', data: { option: config.option } };
          }
          console.log('✅ 检测到有效的ECharts配置:', config.title?.text || '无标题');
          console.log('📊 ECharts属性检查:', {
            hasTitle: !!config.title,
            hasSeries: !!config.series,
            hasXAxis: !!config.xAxis,
            hasYAxis: !!config.yAxis,
            hasLegend: !!config.legend,
            hasTooltip: !!config.tooltip,
            hasGrid: !!config.grid
          });
          return { type: 'echarts', data: { option: config } };
        } else {
          console.log('⚠️ 配置不完整或不符合ECharts格式，显示为文本');
        }
      } else {
        console.log('⚠️ 未解析到配置对象，尝试的方法都失败了');
      }
    } catch (e) {
      console.log('⚠️ ECharts解析过程中出错:', e);
    }

    // 检测图片配置
    const imageMatch = text.match(/```image\s*([\s\S]*?)\s*```/);
    if (imageMatch) {
      try {
        const imageConfig: ImageConfig = JSON.parse(imageMatch[1]);
        return { type: 'image', data: imageConfig };
      } catch (e) {
        console.error('解析图片配置失败:', e);
      }
    }

    // 检测图片URL（直接URL或base64）
    const imageUrlMatch = text.match(/(https?:\/\/[^\s]+\.(jpg|jpeg|png|gif|webp|svg)|data:image\/[^;]+;base64,[^\s]+)/i);
    if (imageUrlMatch) {
      return { 
        type: 'image', 
        data: { src: imageUrlMatch[0], alt: '图片' } 
      };
    }

    // 检测HTML表格（直接HTML标签）
    if (/<table[\s\S]*?>[\s\S]*?<\/table>/i.test(trimmedText) ||
        /<div[\s\S]*?>[\s\S]*?<\/div>/i.test(trimmedText) ||
        /<img[\s\S]*?\/>/i.test(trimmedText)) {
      try {
        const htmlContent = trimmedText
          .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '') // 移除script标签
          .replace(/javascript:/gi, '') // 移除javascript伪协议
          .trim();
        return { type: 'html', data: htmlContent };
      } catch (e) {
        console.error('解析HTML配置失败:', e);
      }
    }
    
    // 检测HTML表格（代码块格式）
    const htmlMatch = text.match(/```html\s*([\s\S]*?)\s*```/);
    if (htmlMatch) {
      try {
        // 清理HTML内容并确保安全
        const htmlContent = htmlMatch[1]
          .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '') // 移除script标签
          .replace(/javascript:/gi, '') // 移除javascript伪协议
          .trim();
        return { type: 'html', data: htmlContent };
      } catch (e) {
        console.error('解析HTML配置失败:', e);
      }
    }

    return { type: 'text', data: text };
  };

  const renderImage = (imageConfig: ImageConfig) => {
    return (
      <div className="my-2 max-w-full overflow-x-auto overflow-y-auto" style={{ maxHeight: '600px' }}>
        <img
          src={imageConfig.src}
          alt={imageConfig.alt || '图片'}
          width={imageConfig.width}
          height={imageConfig.height}
          className="max-w-full h-auto rounded-lg shadow-sm border"
          style={{
            maxWidth: '100%',
            height: 'auto',
            ...(imageConfig.width && { width: imageConfig.width }),
            ...(imageConfig.height && { height: imageConfig.height })
          }}
          onError={(e) => {
            console.error('图片加载失败:', imageConfig.src);
            e.currentTarget.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjE1MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjNmNGY2Ii8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OTk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuWbvueJh+WKoOi9veS4rTwvdGV4dD48L3N2Zz4=';
          }}
        />
      </div>
    );
  };

  const renderHTML = (htmlContent: string) => {
    // 为表格添加基本样式
    const styledHTML = htmlContent
      .replace(/<table/g, '<table class="min-w-full border-collapse border border-gray-300"')
      .replace(/<th/g, '<th class="border border-gray-300 px-4 py-2 bg-gray-50 font-semibold text-left"')
      .replace(/<td/g, '<td class="border border-gray-300 px-4 py-2 text-sm"')
      .replace(/<img/g, '<img class="max-w-full h-auto rounded-lg"')
      .replace(/<h1/g, '<h1 class="text-xl font-bold mb-2"')
      .replace(/<h2/g, '<h2 class="text-lg font-semibold mb-2"')
      .replace(/<h3/g, '<h3 class="text-base font-medium mb-1"');

    return (
      <div 
        className="my-2 overflow-x-auto overflow-y-auto bg-white rounded-lg border p-4 max-w-full"
        style={{ maxHeight: '600px', quotes: 'none' } as React.CSSProperties}
        dangerouslySetInnerHTML={{ __html: styledHTML }}
      />
    );
  };


  // 检测是否为 Markdown 格式
  const isMarkdown = (text: string): boolean => {
    // 检测常见的 Markdown 语法特征
    const markdownPatterns = [
      /^#{1,6}\s+.+$/m,           // 标题 (# ## ###)
      /^\*\s+.+$/m,               // 无序列表 (*)
      /^\d+\.\s+.+$/m,            // 有序列表 (1. 2.)
      /\*\*[^*]+\*\*/g,           // 粗体 (**text**)
      /\*[^*]+\*/g,               // 斜体 (*text*)
      /`[^`]+`/g,                 // 行内代码 (`code`)
      /```[\s\S]*?```/g,          // 代码块 (```code```)
      /^---$/m,                   // 分隔线 (---)
      /^\|.+\|$/m,                // 表格 (| col |)
      /\[.+\]\(.+\)/g,            // 链接 ([text](url))
    ];
    
    return markdownPatterns.some(pattern => pattern.test(text));
  };

  // 渲染 Markdown 内容
  const renderMarkdown = (text: string) => {
    let html = text;
    
    // 转义 HTML 特殊字符（防止 XSS）
    const escapeHtml = (str: string) => {
      const map: { [key: string]: string } = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;',
      };
      return str.replace(/[&<>"']/g, (m) => map[m]);
    };

    // 处理代码块（先处理，避免被其他规则影响）
    html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (_match, lang, code) => {
      const escapedCode = escapeHtml(code.trim());
      return `<pre class="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto my-4" style="word-break: break-all; white-space: pre-wrap; overflow-wrap: break-word; max-width: 100%;"><code class="language-${lang || 'text'}" style="word-break: break-all; white-space: pre-wrap; overflow-wrap: break-word;">${escapedCode}</code></pre>`;
    });

    // 处理行内代码
    html = html.replace(/`([^`]+)`/g, '<code class="bg-gray-100 text-red-600 px-1.5 py-0.5 rounded text-sm font-mono" style="word-break: break-all; overflow-wrap: break-word;">$1</code>');

    // 处理标题（从最多#开始，避免匹配错误）
    html = html.replace(/^###### (.*$)/gim, '<h6 class="text-sm font-semibold mt-4 mb-2 text-gray-700">$1</h6>');
    html = html.replace(/^##### (.*$)/gim, '<h5 class="text-base font-semibold mt-4 mb-2 text-gray-700">$1</h5>');
    html = html.replace(/^#### (.*$)/gim, '<h4 class="text-base font-semibold mt-5 mb-2 text-gray-800">$1</h4>');
    html = html.replace(/^### (.*$)/gim, '<h3 class="text-lg font-semibold mt-6 mb-3 text-gray-800">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 class="text-xl font-bold mt-6 mb-4 text-gray-900">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold mt-6 mb-4 text-gray-900">$1</h1>');

    // 处理粗体
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong class="font-bold">$1</strong>');
    html = html.replace(/__([^_]+)__/g, '<strong class="font-bold">$1</strong>');

    // 处理斜体
    html = html.replace(/\*([^*]+)\*/g, '<em class="italic">$1</em>');
    html = html.replace(/_([^_]+)_/g, '<em class="italic">$1</em>');

    // 处理列表（先按行分割，然后分组处理）
    const lines = html.split('\n');
    const processedLines: string[] = [];
    let inUnorderedList = false;
    let inOrderedList = false;
    let listItems: string[] = [];
    
    const flushList = () => {
      if (listItems.length > 0) {
        if (inOrderedList) {
          processedLines.push(`<ol class="list-decimal list-inside my-2 space-y-1">${listItems.join('')}</ol>`);
        } else if (inUnorderedList) {
          processedLines.push(`<ul class="list-disc list-inside my-2 space-y-1">${listItems.join('')}</ul>`);
        }
        listItems = [];
        inUnorderedList = false;
        inOrderedList = false;
      }
    };
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      
      // 检查是否是有序列表项
      const orderedMatch = line.match(/^(\d+)\.\s+(.+)$/);
      if (orderedMatch) {
        flushList();
        inOrderedList = true;
        listItems.push(`<li class="ml-4 mb-1">${orderedMatch[2]}</li>`);
        continue;
      }
      
      // 检查是否是无序列表项
      const unorderedMatch = line.match(/^[\*\-\+]\s+(.+)$/);
      if (unorderedMatch) {
        flushList();
        inUnorderedList = true;
        listItems.push(`<li class="ml-4 mb-1">${unorderedMatch[1]}</li>`);
        continue;
      }
      
      // 如果不是列表项，先刷新列表
      flushList();
      
      // 检查是否是已处理的 HTML 标签
      if (line.trim().startsWith('<') && (line.includes('</') || line.match(/<[^>]+>$/))) {
        processedLines.push(line);
      } else if (line.trim() === '') {
        processedLines.push('');
      } else {
        // 普通文本行，保留原样（后续会处理为段落）
        processedLines.push(line);
      }
    }
    
    // 处理最后剩余的列表
    flushList();
    
    html = processedLines.join('\n');

    // 处理分隔线
    html = html.replace(/^---$/gm, '<hr class="my-4 border-gray-300" />');
    html = html.replace(/^\*\*\*$/gm, '<hr class="my-4 border-gray-300" />');

    // 处理链接
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-blue-600 hover:text-blue-800 underline" target="_blank" rel="noopener noreferrer">$1</a>');

    // 处理表格
    const tableRegex = /^\|(.+)\|\n\|[-\s|:]+\|\n((?:\|.+\|\n?)+)/gm;
    html = html.replace(tableRegex, (_match, header, rows) => {
      const headerCells = header.split('|').filter((cell: string) => cell.trim()).map((cell: string) => 
        `<th class="border border-gray-300 px-4 py-2 bg-gray-50 font-semibold text-left">${cell.trim()}</th>`
      ).join('');
      
      const rowLines = rows.trim().split('\n');
      const tableRows = rowLines.map((row: string) => {
        const cells = row.split('|').filter((cell: string) => cell.trim()).map((cell: string) => 
          `<td class="border border-gray-300 px-4 py-2 text-sm">${cell.trim()}</td>`
        ).join('');
        return `<tr>${cells}</tr>`;
      }).join('');
      
      return `<table class="min-w-full border-collapse border border-gray-300 my-4">
        <thead><tr>${headerCells}</tr></thead>
        <tbody>${tableRows}</tbody>
      </table>`;
    });

    // 处理段落（将连续的非空行作为段落）
    const paragraphLines = html.split('\n');
    const paragraphProcessedLines: string[] = [];
    let currentParagraph: string[] = [];
    
    for (let i = 0; i < paragraphLines.length; i++) {
      let line = paragraphLines[i].trim();
      
      // 如果行是 HTML 标签（已处理的元素），直接添加
      if (line.startsWith('<') && (line.includes('</') || line.match(/<[^>]+>$/))) {
        // 如果有待处理的段落，先包装并添加
        if (currentParagraph.length > 0) {
          paragraphProcessedLines.push(`<p class="mb-3" style="quotes: none;">${currentParagraph.join(' ')}</p>`);
          currentParagraph = [];
        }
        paragraphProcessedLines.push(line);
      } else if (line === '') {
        // 空行，如果有待处理的段落，包装并添加
        if (currentParagraph.length > 0) {
          const paragraphText = currentParagraph.join(' ').trim();
          // 只有当段落内容不为空且不只是 > 符号时才创建段落
          if (paragraphText && paragraphText !== '>' && paragraphText !== '&gt;') {
            paragraphProcessedLines.push(`<p class="mb-3" style="quotes: none;">${paragraphText}</p>`);
          }
          currentParagraph = [];
        }
        paragraphProcessedLines.push('');
      } else {
        // 普通文本行，添加到当前段落
        // 跳过只包含 > 符号或空白字符的行
        if (line === '>' || line === '&gt;' || line.trim() === '') {
          continue;
        }
        
        // 确保不会将单独的 > 符号误识别为引用块
        // 如果行以 > 开头但不是引用块语法（需要 > 后面有空格），则转义它
        if (line.startsWith('>') && !line.match(/^>\s+/)) {
          // 如果只是单独的 > 符号，转义它
          line = line.replace(/^>/, '&gt;');
          // 如果转义后只剩下 &gt;，跳过这一行
          if (line.trim() === '&gt;') {
            continue;
          }
        }
        currentParagraph.push(line);
      }
    }
    
    // 处理最后剩余的段落
    if (currentParagraph.length > 0) {
      const paragraphText = currentParagraph.join(' ').trim();
      // 只有当段落内容不为空且不只是 > 符号时才创建段落
      if (paragraphText && paragraphText !== '>' && paragraphText !== '&gt;') {
        paragraphProcessedLines.push(`<p class="mb-3" style="quotes: none;">${paragraphText}</p>`);
      }
    }
    
    html = paragraphProcessedLines.join('\n');
    
    // 清理：移除只包含 > 或 &gt; 的空段落
    html = html.replace(/<p[^>]*>\s*(>|&gt;)\s*<\/p>/g, '');

    return (
      <>
        <style>{`
          .markdown-content,
          .markdown-content * {
            quotes: none !important;
          }
          .markdown-content blockquote::before,
          .markdown-content blockquote::after,
          .markdown-content q::before,
          .markdown-content q::after {
            content: none !important;
            display: none !important;
          }
          .markdown-content blockquote,
          .markdown-content q {
            border-left: none !important;
            padding-left: 0 !important;
            margin-left: 0 !important;
            quotes: none !important;
          }
          .markdown-content p::before,
          .markdown-content p::after,
          .markdown-content div::before,
          .markdown-content div::after {
            content: none !important;
          }
          .markdown-content > *::before,
          .markdown-content > *::after {
            content: none !important;
          }
          .markdown-content *::before,
          .markdown-content *::after {
            content: none !important;
            quotes: none !important;
          }
        `}</style>
        <div 
          className="markdown-content max-w-none"
          style={{
            // 自定义样式，避免 prose 类的自动引用块处理
            fontSize: '0.875rem',
            lineHeight: '1.7142857',
            quotes: 'none',
          } as React.CSSProperties}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </>
    );
  };

  const renderText = (text: string) => {
    // 检测是否为 Markdown 格式
    if (isMarkdown(text)) {
      return renderMarkdown(text);
    }
    
    // 简单的格式化：支持换行和基本的文本格式，文本可以加长显示，不需要滚动
    return (
      <div className="whitespace-pre-wrap break-words w-full" style={{ wordBreak: 'break-word', overflowWrap: 'break-word', maxWidth: '100%' }}>
        {text.split('\n').map((line, index) => (
          <div key={index} className={index > 0 ? 'mt-1' : ''} style={{ wordBreak: 'break-word', overflowWrap: 'break-word' }}>
            {line}
          </div>
        ))}
      </div>
    );
  };

  // 使用 useMemo 缓存解析结果，避免频繁重新解析
  const normalizedContent = useMemo(() => {
    return normalizeContent(content);
  }, [content]);

  const parsedContent = useMemo(() => {
    try {
      return parseContent(normalizedContent);
    } catch (parseError) {
      console.error('RichContent 解析错误:', parseError);
      return { type: 'text' as const, data: normalizedContent };
    }
  }, [normalizedContent]);

  // 根据类型渲染内容
  try {
    switch (parsedContent.type) {
      case 'echarts':
        console.log('🎯 渲染ECharts组件，parsedContent.data:', parsedContent.data);
        console.log('🎯 EChartsConfig类型检查:', {
          hasData: !!parsedContent.data,
          hasOption: !!(parsedContent.data as any)?.option,
          dataType: typeof parsedContent.data
        });
        return (
          <div className={className}>
            <EChartsRenderer eChartsConfig={parsedContent.data as EChartsConfig} />
          </div>
        );
      case 'echarts_with_text':
        console.log('🎯 渲染ECharts组件+文本，parsedContent.data:', parsedContent.data);
        console.log('📝 文本内容:', parsedContent.textContent);
        return (
          <div className={className}>
            <EChartsRenderer eChartsConfig={parsedContent.data as EChartsConfig} />
            {parsedContent.textContent && (
              <div className="mt-4">
                {renderText(parsedContent.textContent)}
              </div>
            )}
          </div>
        );
      case 'echarts_table':
        console.log('📊 渲染ECharts表格，parsedContent.data:', parsedContent.data);
        return (
          <div className={className}>
            <EChartsTable data={parsedContent.data} />
          </div>
        );
      case 'image':
        return (
          <div className={className}>
            {renderImage(parsedContent.data as ImageConfig)}
          </div>
        );
      case 'html':
        return (
          <div className={className}>
            {renderHTML(parsedContent.data as string)}
          </div>
        );
      case 'html_with_text':
        console.log('🎯 渲染HTML表格+文本，parsedContent.data:', parsedContent.data);
        console.log('📝 文本内容:', parsedContent.textContent);
        return (
          <div className={className} style={{ quotes: 'none' } as React.CSSProperties}>
            {renderHTML(parsedContent.data as string)}
            {parsedContent.textContent && (
              <div className="mt-4" style={{ quotes: 'none' } as React.CSSProperties}>
                {renderText(parsedContent.textContent)}
              </div>
            )}
          </div>
        );
      case 'mixed':
        console.log('🎯 渲染混合内容，parts数量:', parsedContent.parts?.length);
        console.log('🎯 混合内容parts详情:', parsedContent.parts?.map(p => ({ type: p.type, dataLength: typeof p.data === 'string' ? p.data.length : 'object' })));
        return (
          <div className={className}>
            {parsedContent.parts?.map((part, index) => {
              console.log(`🎯 渲染part ${index}:`, { type: part.type, hasData: !!part.data });
              switch (part.type) {
                case 'html':
                  if (!part.data || (typeof part.data === 'string' && !part.data.trim())) {
                    console.warn(`⚠️ Part ${index} HTML数据为空，跳过`);
                    return null;
                  }
                  return (
                    <div key={index} className={index > 0 ? 'mt-4' : ''}>
                      {renderHTML(part.data as string)}
                    </div>
                  );
                case 'echarts':
                  if (!part.data || !(part.data as any)?.option) {
                    console.warn(`⚠️ Part ${index} ECharts数据无效，跳过`);
                    return null;
                  }
                  return (
                    <div key={index} className={index > 0 ? 'mt-4' : ''}>
                      <EChartsRenderer eChartsConfig={part.data as EChartsConfig} />
                    </div>
                  );
                case 'text':
                  if (!part.data || (typeof part.data === 'string' && !part.data.trim())) {
                    console.warn(`⚠️ Part ${index} 文本数据为空，跳过`);
                    return null;
                  }
                  return (
                    <div key={index} className={index > 0 ? 'mt-4' : ''} style={{ quotes: 'none' } as React.CSSProperties}>
                      {renderText(part.data as string)}
                    </div>
                  );
                default:
                  console.warn(`⚠️ Part ${index} 未知类型: ${part.type}`);
                  return null;
              }
            })}
          </div>
        );
      default:
        return (
          <div className={className}>
            {renderText(parsedContent.data as string)}
          </div>
        );
    }
  } catch (renderErr) {
    console.error('RichContent 渲染错误:', renderErr);
    return (
      <div className={className}>
        <div className="text-red-600 text-sm mb-2">
          渲染出错: {renderErr instanceof Error ? renderErr.message : '未知错误'}
        </div>
        <div className="whitespace-pre-wrap break-words text-gray-600 text-sm">
          {normalizedContent}
        </div>
      </div>
    );
  }
};

// 声明全局echarts类型
declare global {
  interface Window {
    echarts: any;
  }
}

export default RichContent;


