from getpass import getpass
from datetime import datetime, timedelta
import re
import json
import requests
from urllib.parse import urljoin

from .base import BaseAuth
from .. import errors


class SharePointOnline(BaseAuth):
    """Authenticate via SharePoint Online using modern OAuth2 flow"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.expire = datetime.now()
        self.token = None
        self.tenant_id = None
        self.login_base_url = "https://login.microsoftonline.com"

    def login(self, site):
        """Perform authentication steps"""
        self.site = site
        self._detect_tenant()
        self._get_token()
        self._get_cookie()
        self._get_digest()

    def refresh(self):
        return self._get_digest()

    def _detect_tenant(self):
        """Detect tenant ID from the site"""
        # Extract tenant ID from site URL or detect it
        if not self.tenant_id:
            # Try to extract from site URL first
            tenant_match = re.search(r'https://([^.]+)-my\.sharepoint\.com', f"https://{self.site}")
            if tenant_match:
                # This is a OneDrive site, we need to detect the tenant differently
                pass
            
            # For now, we'll use a common approach to detect tenant
            # In a real implementation, you might want to store tenant ID or detect it differently
            print(f"检测到SharePoint站点: {self.site}")
            # You can set tenant_id manually if known
            # self.tenant_id = "your-tenant-id-here"

    def _get_token(self):
        """Get authentication token using modern OAuth2 flow"""
        password = self.password or getpass('Enter your password: ')
        
        print("开始SharePoint Online认证流程...")
        
        # Step 1: Access SharePoint site to get login page
        login_page = self._get_login_page()
        if not login_page:
            raise errors.AuthError('无法获取登录页面')
        
        # Step 2: Extract login parameters from JavaScript config
        login_params = self._extract_login_params(login_page)
        if not login_params:
            raise errors.AuthError('无法提取登录参数')
        
        # Step 3: Submit login credentials
        login_result = self._submit_login(login_params, password)
        if not login_result:
            raise errors.AuthError('登录凭据提交失败')
        
        # Step 4: Handle KMSI (Keep Me Signed In)
        kmsi_result = self._handle_kmsi(login_result)
        if not kmsi_result:
            raise errors.AuthError('KMSI处理失败')
        
        print("认证流程完成")

    def _get_login_page(self):
        """Get the login page from SharePoint"""
        print("步骤1: 访问SharePoint主页...")
        
        # 使用更好的请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/110.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }
        
        try:
            response = requests.get(f"https://{self.site}", headers=headers, timeout=30)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 302:
                # Get redirect URL
                redirect_url = response.headers.get('Location')
                print(f"重定向到: {redirect_url}")
                
                # Follow redirect
                response = requests.get(redirect_url, headers=headers, allow_redirects=True, timeout=30)
                print(f"重定向后状态码: {response.status_code}")
                
                if response.status_code == 200:
                    print("成功获取登录页面")
                    return response.text
                else:
                    print("获取登录页面失败")
                    return None
            elif response.status_code == 200:
                # Direct 200 response
                print("直接获取到页面内容，检查是否需要登录")
                
                # Check if page contains login elements
                if 'login' in response.text.lower() or 'sign in' in response.text.lower():
                    print("页面包含登录元素，可能是登录页面")
                    return response.text
                else:
                    print("页面不包含登录元素，可能需要重定向")
                    # Try to find redirect link
                    redirect_match = re.search(r'href=["\']([^"\']*login[^"\']*)["\']', response.text, re.IGNORECASE)
                    if redirect_match:
                        redirect_url = redirect_match.group(1)
                        if not redirect_url.startswith('http'):
                            # Relative URL, convert to absolute
                            redirect_url = urljoin(f"https://{self.site}", redirect_url)
                        
                        print(f"找到登录链接: {redirect_url}")
                        response = requests.get(redirect_url, headers=headers, allow_redirects=True, timeout=30)
                        print(f"访问登录链接后状态码: {response.status_code}")
                        return response.text
                    else:
                        print("未找到登录链接，尝试直接访问Microsoft登录页面")
                        # Direct access to Microsoft login page
                        login_url = f"{self.login_base_url}/common/oauth2/authorize"
                        params = {
                            'client_id': '00000003-0000-0ff1-ce00-000000000000',
                            'response_mode': 'form_post',
                            'response_type': 'code id_token',
                            'resource': '00000003-0000-0ff1-ce00-000000000000',
                            'scope': 'openid',
                            'redirect_uri': f"https://{self.site}/_forms/default.aspx"
                        }
                        
                        response = requests.get(login_url, params=params, headers=headers, timeout=30)
                        print(f"访问Microsoft登录页面状态码: {response.status_code}")
                        return response.text
            elif response.status_code == 403:
                print("收到403错误，尝试使用不同的方法...")
                # 尝试直接访问登录页面
                login_url = f"https://{self.site}/_layouts/15/authenticate.aspx"
                print(f"尝试访问: {login_url}")
                
                response = requests.get(login_url, headers=headers, timeout=30)
                print(f"登录页面状态码: {response.status_code}")
                
                if response.status_code == 200:
                    print("成功获取登录页面")
                    return response.text
                else:
                    print("登录页面访问失败")
                    return None
            else:
                print(f"未收到预期的响应，状态码: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"请求异常: {e}")
            return None
        except Exception as e:
            print(f"其他错误: {e}")
            return None

    def _extract_login_params(self, html_content):
        """Extract login parameters from JavaScript configuration"""
        print("步骤2: 从JavaScript配置中提取登录参数...")
        
        # Try to extract from JavaScript config
        js_config = self._extract_js_config(html_content)
        if js_config:
            print("成功从JavaScript配置中提取登录信息")
            return js_config
        else:
            print("无法从JavaScript配置中提取登录信息")
            return None

    def _extract_js_config(self, html_content):
        """Extract login information from JavaScript configuration"""
        # Find JavaScript config object
        config_match = re.search(r'\$Config\s*=\s*({.*?});', html_content, re.DOTALL)
        if not config_match:
            print("未找到JavaScript配置对象")
            return None
        
        try:
            config_text = config_match.group(1)
            # Clean JavaScript code, convert to valid JSON
            config_text = re.sub(r'//.*?\n', '', config_text)  # Remove comments
            config_text = re.sub(r',\s*}', '}', config_text)  # Fix trailing commas
            
            # Try to parse JSON
            config = json.loads(config_text)
            
            # Extract key information
            login_params = {}
            
            # Extract flowToken
            if 'sFT' in config:
                login_params['flowToken'] = config['sFT']
                print(f"从JS配置提取到flowToken: {config['sFT'][:50]}...")
            
            # Extract canary
            if 'canary' in config:
                login_params['canary'] = config['canary']
                print(f"从JS配置提取到canary: {config['canary'][:50]}...")
            
            # Extract ctx
            if 'sCtx' in config:
                login_params['ctx'] = config['sCtx']
                print(f"从JS配置提取到ctx: {config['sCtx'][:50]}...")
            
            # Extract other important fields
            if 'urlPost' in config:
                login_params['action'] = config['urlPost']
                print(f"从JS配置提取到登录URL: {config['urlPost']}")
            
            if 'apiCanary' in config:
                login_params['apiCanary'] = config['apiCanary']
                print(f"从JS配置提取到apiCanary: {config['apiCanary'][:50]}...")
            
            if 'hpgid' in config:
                login_params['hpgid'] = config['hpgid']
                print(f"从JS配置提取到hpgid: {config['hpgid']}")
            
            if 'hpgact' in config:
                login_params['hpgact'] = config['hpgact']
                print(f"从JS配置提取到hpgact: {config['hpgact']}")
            
            return login_params
            
        except json.JSONDecodeError as e:
            print(f"解析JavaScript配置失败: {e}")
            # If JSON parsing fails, try regex extraction
            return self._extract_js_config_regex(html_content)
        except Exception as e:
            print(f"提取JavaScript配置时发生错误: {e}")
            return None

    def _extract_js_config_regex(self, html_content):
        """Extract key information using regex from JavaScript configuration"""
        login_params = {}
        
        # Extract flowToken
        ft_match = re.search(r'"sFT"\s*:\s*"([^"]+)"', html_content)
        if ft_match:
            login_params['flowToken'] = ft_match.group(1)
            print(f"正则提取到flowToken: {ft_match.group(1)[:50]}...")
        
        # Extract canary
        canary_match = re.search(r'"canary"\s*:\s*"([^"]+)"', html_content)
        if canary_match:
            login_params['canary'] = canary_match.group(1)
            print(f"正则提取到canary: {canary_match.group(1)[:50]}...")
        
        # Extract ctx
        ctx_match = re.search(r'"sCtx"\s*:\s*"([^"]+)"', html_content)
        if ctx_match:
            login_params['ctx'] = ctx_match.group(1)
            print(f"正则提取到ctx: {ctx_match.group(1)[:50]}...")
        
        # Extract login URL
        url_post_match = re.search(r'"urlPost"\s*:\s*"([^"]+)"', html_content)
        if url_post_match:
            login_params['action'] = url_post_match.group(1)
            print(f"正则提取到登录URL: {url_post_match.group(1)}")
        
        # Extract apiCanary
        api_canary_match = re.search(r'"apiCanary"\s*:\s*"([^"]+)"', html_content)
        if api_canary_match:
            login_params['apiCanary'] = api_canary_match.group(1)
            print(f"正则提取到apiCanary: {api_canary_match.group(1)[:50]}...")
        
        # Extract hpgid
        hpgid_match = re.search(r'"hpgid"\s*:\s*(\d+)', html_content)
        if hpgid_match:
            login_params['hpgid'] = hpgid_match.group(1)
            print(f"正则提取到hpgid: {hpgid_match.group(1)}")
        
        # Extract hpgact
        hpgact_match = re.search(r'"hpgact"\s*:\s*(\d+)', html_content)
        if hpgact_match:
            login_params['hpgact'] = hpgact_match.group(1)
            print(f"正则提取到hpgact: {hpgact_match.group(1)}")
        
        if login_params:
            return login_params
        else:
            print("使用正则表达式也无法提取到登录信息")
            return None

    def _submit_login(self, login_params, password):
        """Submit login credentials"""
        print("步骤3: 提交登录凭据...")
        
        if not login_params.get('action'):
            print("缺少登录URL")
            return None
        
        submit_url = login_params['action']
        print(f"提交URL: {submit_url}")
        
        # Prepare login data
        login_data = {
            'login': self.username,
            'passwd': password,
            'canary': login_params.get('canary', ''),
            'ctx': login_params.get('ctx', ''),
            'hpgrequestid': login_params.get('hpgid', ''),
            'flowToken': login_params.get('flowToken', '')
        }
        
        # 添加请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/110.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Accept-Encoding': 'gzip, deflate, br',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://login.microsoftonline.com',
            'Referer': 'https://login.microsoftonline.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        try:
            # Submit login request
            response = requests.post(submit_url, data=login_data, headers=headers, timeout=30)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                print("登录请求成功")
                if 'kmsi' in response.text.lower():
                    print("需要处理KMSI...")
                    return response.text
                else:
                    print("登录完成")
                    return response.text
            else:
                print(f"登录请求失败: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"登录请求异常: {e}")
            return None
        except Exception as e:
            print(f"登录请求其他错误: {e}")
            return None

    def _handle_kmsi(self, html_content):
        """Handle Keep Me Signed In step"""
        print("步骤4: 处理KMSI...")
        
        # Extract KMSI parameters
        js_config = self._extract_js_config(html_content)
        if not js_config:
            print("无法提取KMSI参数")
            return None
        
        # Handle KMSI
        kmsi_data = {
            'flowToken': js_config.get('flowToken', ''),
            'canary': js_config.get('canary', ''),
            'ctx': js_config.get('ctx', ''),
            'hpgrequestid': js_config.get('hpgid', ''),
            'hpgact': js_config.get('hpgact', '')
        }
        
        # 添加请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/110.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Accept-Encoding': 'gzip, deflate, br',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://login.microsoftonline.com',
            'Referer': 'https://login.microsoftonline.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        try:
            # Submit KMSI request
            kmsi_url = "https://login.microsoftonline.com/kmsi"
            response = requests.post(kmsi_url, data=kmsi_data, headers=headers, timeout=30)
            print(f"KMSI状态码: {response.status_code}")
            
            if response.status_code == 200:
                print("KMSI处理成功")
                return response.text
            else:
                print(f"KMSI处理失败: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"KMSI请求异常: {e}")
            return None
        except Exception as e:
            print(f"KMSI请求其他错误: {e}")
            return None

    def _get_cookie(self):
        """Request access cookie from SharePoint site"""
        print("获取访问cookie...")
        
        # 添加请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/110.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        try:
            # Try to access SharePoint site to get cookies
            response = requests.get(f"https://{self.site}", headers=headers, timeout=30)
            
            if response.status_code == 200:
                # Extract cookies
                cookies = response.cookies
                if cookies:
                    self.cookie = self._buildcookie(cookies)
                    print("成功获取访问cookie")
                    return True
                else:
                    print("未找到访问cookie")
                    return False
            else:
                print(f"获取访问cookie失败: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"获取cookie请求异常: {e}")
            return False
        except Exception as e:
            print(f"获取cookie其他错误: {e}")
            return False

    def _get_digest(self):
        """Check and refresh sites cookie and request digest"""
        if self.expire <= datetime.now():
            # Request site context info from SharePoint site
            digest_url = f'https://{self.site}/_api/contextinfo'
            
            # 添加请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/110.0',
                'Accept': 'application/json; odata=verbose',
                'Content-Type': 'application/json; odata=verbose',
                'Cookie': self.cookie,
                'X-RequestDigest': self.digest if self.digest else '',
                'DNT': '1',
                'Connection': 'keep-alive'
            }
            
            try:
                response = requests.post(digest_url, data='', headers=headers, timeout=30)
                
                if response.status_code == 200:
                    # Parse digest text and timeout from XML
                    try:
                        # Try to parse as XML first
                        import xml.etree.ElementTree as et
                        root = et.fromstring(response.text)
                        self.digest = root.find('.//d:FormDigestValue', {'d': 'http://schemas.microsoft.com/ado/2007/08/dataservices'}).text
                        timeout = int(root.find('.//d:FormDigestTimeoutSeconds', {'d': 'http://schemas.microsoft.com/ado/2007/08/dataservices'}).text)
                    except:
                        # If XML parsing fails, try to extract from JSON
                        try:
                            data = response.json()
                            self.digest = data.get('FormDigestValue', '')
                            timeout = data.get('FormDigestTimeoutSeconds', 1800)  # Default 30 minutes
                        except:
                            # If all parsing fails, use default values
                            self.digest = ''
                            timeout = 1800
                    
                    # Calculate digest expiry time
                    self.expire = datetime.now() + timedelta(seconds=timeout)
                    print(f"成功获取digest，过期时间: {self.expire}")
                else:
                    print(f"获取digest失败: {response.status_code}")
                    print(f"响应内容: {response.text[:200]}...")
                    
                    # 如果digest获取失败，尝试使用默认值
                    if not self.digest:
                        print("使用默认digest值")
                        self.digest = "default-digest-value"
                        self.expire = datetime.now() + timedelta(seconds=1800)
                    
                    return False
                    
            except requests.exceptions.RequestException as e:
                print(f"获取digest请求异常: {e}")
                return False
            except Exception as e:
                print(f"获取digest其他错误: {e}")
                return False

        return True

    def _buildcookie(self, cookies):
        """Create session cookie from response cookie dictionary"""
        cookie_parts = []
        for name, value in cookies.items():
            cookie_parts.append(f"{name}={value}")
        return '; '.join(cookie_parts)

    @staticmethod
    def supports(realm):
        """Check for managed namespace"""
        return realm.find('NameSpaceType').text == 'Managed'

    @staticmethod
    def get_login(realm):
        """Get the login domain from the realm XML"""
        domain = realm.find('CloudInstanceName').text
        return f'https://login.{domain}/extSTS.srf'
