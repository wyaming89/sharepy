# SharePy 修改说明

## 概述

基于我们的SharePoint登录模拟经验，我们对原始的SharePy项目进行了重大修改，使其能够使用现代的OAuth2认证流程而不是旧的SAML流程。

## 主要修改

### 1. 认证流程现代化

**原始方法**: 使用SAML (Security Assertion Markup Language) 和 `extSTS.srf` 端点
**新方法**: 使用现代OAuth2流程，模拟真实的浏览器登录过程

### 2. 修改的文件

#### `src/sharepy/auth/spol.py`
- 完全重写了`SharePointOnline`类
- 移除了对SAML模板的依赖
- 实现了基于JavaScript配置的登录参数提取

### 3. 新的认证步骤

#### 步骤1: 获取登录页面
- 访问SharePoint站点
- 处理重定向
- 检测登录页面

#### 步骤2: 提取登录参数
- 从JavaScript `$Config` 对象中提取关键参数
- 支持多种提取方法（JSON解析 + 正则表达式）
- 提取的参数包括：
  - `flowToken`
  - `canary`
  - `ctx`
  - `hpgid`
  - `hpgact`
  - `apiCanary`

#### 步骤3: 提交登录凭据
- 使用提取的参数提交用户名和密码
- 添加适当的请求头
- 处理登录响应

#### 步骤4: 处理KMSI (Keep Me Signed In)
- 处理"保持登录状态"步骤
- 提取新的认证参数

#### 步骤5: 获取访问Cookie和Digest
- 建立认证会话
- 获取必要的安全令牌

### 4. 技术改进

#### 请求头优化
- 添加了完整的浏览器请求头
- 包括User-Agent、Accept、Referer等
- 模拟真实浏览器行为

#### 错误处理
- 添加了超时处理
- 改进了异常处理
- 添加了详细的调试信息

#### 兼容性
- 保持了与原始SharePy API的兼容性
- 支持会话保存和加载
- 支持所有原始的SharePoint API调用

## 使用方法

### 基本用法

```python
import sharepy

# 连接到SharePoint
s = sharepy.connect("your-site.sharepoint.com", username="user@company.com")

# 使用API
response = s.get("https://your-site.sharepoint.com/_api/web")
```

### 手动认证

```python
from sharepy.auth.spol import SharePointOnline

auth = SharePointOnline(username="user@company.com")
auth.login("your-site.sharepoint.com")

# 使用认证对象
session = requests.Session()
session.auth = auth
```

## 测试

### 运行测试

```bash
# 基本测试
python3 test_modified_sharepy.py

# 完整演示
python3 demo_modified_sharepy.py
```

### 测试结果

✅ 成功完成认证流程
✅ 成功获取访问Cookie
✅ 成功建立认证会话
✅ 支持会话保存和加载

## 优势

1. **现代认证**: 使用最新的OAuth2流程
2. **更好的兼容性**: 与Microsoft的最新认证系统兼容
3. **更强的稳定性**: 改进了错误处理和重试机制
4. **保持兼容**: 与原始SharePy API完全兼容

## 注意事项

1. **依赖**: 需要`requests`库
2. **网络**: 需要能够访问Microsoft登录服务
3. **权限**: 用户需要有SharePoint访问权限
4. **安全**: 密码输入使用`getpass`，不会在控制台显示

## 故障排除

### 常见问题

1. **403错误**: 检查用户名和密码是否正确
2. **网络错误**: 检查网络连接和防火墙设置
3. **认证失败**: 确保用户有SharePoint访问权限

### 调试

启用详细日志输出，查看每个步骤的执行情况。

## 贡献

这些修改基于实际的SharePoint登录流程分析，使SharePy能够适应现代的认证要求。

## 许可证

遵循原始项目的GPL-3.0许可证。
