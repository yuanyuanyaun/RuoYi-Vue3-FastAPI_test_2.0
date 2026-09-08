"""
APIClient：全局唯一的 HTTP 请求封装层（requests 二次封装）。

职责：
    1. 统一 URL 拼接：base_url + 相对路径，用例层只写相对路径（如 "system/user/list"）
    2. 统一超时时间与请求/响应日志，避免每个用例重复设置公共参数
    3. 统一异常处理：超时 / 连接失败 / HTTP 4xx/5xx 均抛异常并记录日志，保证失败现场可追溯
    4. 记录最近一次请求与响应（last_request / last_response），
       供 conftest 的 pytest_runtest_makereport 钩子在用例失败时 attach 现场

使用约定：
    - 内部通过 resp.raise_for_status() 使 4xx/5xx 抛出 requests.HTTPError，
      因此测试中"期望 404/422"的用例须用 pytest.raises(requests.exceptions.HTTPError) 捕获
    - 后端业务错误（响应体 code=500/601）时 HTTP 状态码仍为 200，不会抛异常，
      此类用例直接断言 resp.json()["code"] 即可
"""
import logging
import requests
from config.setting import BASE_URL, TIMEOUT, LOG_LEVEL

# 全局日志格式：时间/模块名/级别/消息，便于按日志定位失败请求
logging.basicConfig(level=LOG_LEVEL,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 记录最近一次请求与响应，供 conftest 的 pytest_runtest_makereport 钩子在用例失败时 attach 现场
last_request = None
last_response = None


class APIClient:
    """APIClient：requests 封装类，统一 URL 拼接、超时、日志与异常处理。"""

    def __init__(self, base_url=BASE_URL, timeout=TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout
        # 会话级连接复用：跨请求保持 TCP 连接与 Cookie，降低多次握手开销，提升整体执行效率
        self.session = requests.Session()

    def _request(self, method, path, **kwargs):
        """内部通用请求方法：所有公开方法统一经此发送请求、记录日志并处理异常。"""
        global last_request, last_response
        url = f"{self.base_url}{path}"  # 统一拼接 base_url 与相对路径，用例层只传相对路径
        kwargs.setdefault("timeout", self.timeout)  # 未显式指定超时时兜底全局默认值，避免请求无界挂起
        logger.info(f"{method} {url}")
        try:
            # TCP长连接，在Windows中存在缺陷
            resp = self.session.request(method, url, **kwargs)
            # 自建短连接，每条用例绝对干净但会增加TCP握手次数，从而影响效率（本地部署几乎无影响）
            # resp = requests.request(method, url, **kwargs)
            last_request = f"{method} {url}"
            last_response = resp
            resp.raise_for_status()  # 4xx/5xx 状态码自动抛出 HTTPError，统一交由下方异常分支记录
            logger.info(f"返回码: {resp.status_code}")
            return resp
        except requests.exceptions.Timeout:
            logger.error(f"请求超时: {url}")
            raise
        except requests.exceptions.ConnectionError:
            # 连接被服务端重置/关闭时自动重试一次（requests 会新建连接），
            # 兜底规避 Windows 下连接异常导致的偶发失败
            logger.warning(f"连接失败，自动重试一次: {url}")
            try:
                resp = self.session.request(method, url, **kwargs)
                last_request = f"{method} {url}"
                last_response = resp
                resp.raise_for_status()
                logger.info(f"返回码(重试成功): {resp.status_code}")
                return resp
            except requests.exceptions.ConnectionError:
                logger.error(f"连接失败（重试后仍失败）: {url}")
                raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP错误: 响应码 {e.response.status_code}, 响应体 {e.response.text}")
            raise

    def get(self, path, params=None, **kwargs):
        """GET 请求：path 为相对路径，params 为查询参数字典。"""
        return self._request("GET", path, params=params, **kwargs)

    def post(self, path, json=None, **kwargs):
        """POST 请求：json 为请求体字典（传 data 表单时经 kwargs 透传）。"""
        return self._request("POST", path, json=json, **kwargs)

    def put(self, path, json=None, **kwargs):
        """PUT 请求：json 为请求体字典。"""
        return self._request("PUT", path, json=json, **kwargs)

    def delete(self, path, **kwargs):
        """DELETE 请求：path 可携带路径参数（如逗号分隔的 id 列表）。"""
        return self._request("DELETE", path, **kwargs)
