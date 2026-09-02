"""
LoginApi：登录模块接口封装。

覆盖接口：
    POST  /login        登录：OAuth2 表单参数（username/password），
                        验证码关闭时无需传 code/uuid
    GET   /getInfo      获取当前登录用户信息：无 token 时 HTTP 401；
                        token 无效时 HTTP 200 + 业务 code 401
    GET   /getRouters   获取当前用户动态路由（前端侧边栏菜单的数据来源）
    POST  /logout       退出登录：注销指定 token，退出后原 token 立即失效

设计要点：
    - login 以 data=kwargs 传表单参数——后端接收 OAuth2PasswordRequestForm，而非 JSON
    - get_info 的 token 参数默认 None：不传 token 时后端返回 401，用于"无 token"反向用例
    - 认证方式为 Authorization: Bearer <token>，由 utils.function.auth() 生成
"""
from utils.function import auth


class LoginApi:
    """登录模块接口封装：URL 与认证头组装集中管理，用例层仅传入业务参数。"""

    def __init__(self, client):
        # 登录接口是获取 token 的入口，本身无需认证头，故构造函数仅依赖 HTTP 客户端
        self.client = client

    def login(self, **kwargs):
        """登录系统：OAuth2 表单参数（username/password/code/uuid）。"""
        return self.client.post("login", data=kwargs)

    def get_info(self, token=None):
        """获取当前登录用户信息；token 为 None 时不携带 Authorization 头（用于无 token → 401 反向用例）。"""
        headers = auth(token) if token else None
        return self.client.get(
            "getInfo",
            headers=headers
        )

    def get_routers(self, token):
        """获取当前用户动态路由（前端侧边栏菜单数据来源），需携带有效 token。"""
        return self.client.get(
            "getRouters",
            headers=auth(token)
        )

    def logout(self, token):
        """退出登录：注销指定 token，退出后该 token 立即失效。"""
        return self.client.post(
            "logout",
            headers=auth(token)
        )
